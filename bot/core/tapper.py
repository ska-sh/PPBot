import asyncio
import random
import string
from time import time
from urllib.parse import unquote, quote

import aiohttp
import json
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestWebView
from pyrogram.raw import types
from .agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from .helper import format_duration


class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.start_param = None
        self.peer = None
        self.first_run = None

        self.session_ug_dict = self.load_user_agents() or []

        headers['User-Agent'] = self.check_user_agent()

    async def generate_random_user_agent(self):
        return generate_random_user_agent(device_type='android', browser_type='chrome')

    def info(self, message):
        from bot.utils import info
        info(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def debug(self, message):
        from bot.utils import debug
        debug(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def warning(self, message):
        from bot.utils import warning
        warning(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def error(self, message):
        from bot.utils import error
        error(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def critical(self, message):
        from bot.utils import critical
        critical(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def success(self, message):
        from bot.utils import success
        success(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.session_name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.session_name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            logger.success(f"<light-yellow>{self.session_name}</light-yellow> | User agent saved successfully")

            return user_agent_str

    def load_user_agents(self):
        user_agents_file_name = "user_agents.json"

        try:
            with open(user_agents_file_name, 'r') as user_agents:
                session_data = json.load(user_agents)
                if isinstance(session_data, list):
                    return session_data

        except FileNotFoundError:
            logger.warning("User agents file not found, creating...")

        except json.JSONDecodeError:
            logger.warning("User agents file is empty or corrupted.")

        return []

    def check_user_agent(self):
        load = next(
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.session_name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            if settings.REF_ID == '':
                self.start_param = 'share_6168926126'
            else:
                self.start_param = settings.REF_ID

            #https://t.me/PiggyPiggyofficialbot/game?startapp=share_6168926126
            #https://t.me/BlumCryptoBot/app?startapp=ref_v7cnI85reb
            peer = await self.tg_client.resolve_peer('PiggyPiggyofficialbot')
            InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="game")

            web_view = await self.tg_client.invoke(RequestWebView(
                peer=peer,
                bot=peer,
                platform='android',
                from_bot_menu=False,
                url='https://api.prod.piggypiggy.io'
            ))

            auth_url = web_view.url
            #print(auth_url)
            # self.success(f"auth_url:{auth_url}")
            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

            try:
                if self.user_id == 0:
                    information = await self.tg_client.get_me()
                    self.user_id = information.id
                    self.first_name = information.first_name or ''
                    self.last_name = information.last_name or ''
                    self.username = information.username or ''
            except Exception as e:
                print(e)

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, initdata):
        try:
            if settings.USE_REF is False:

                resp = await http_client.get("https://api.prod.piggypiggy.io/tgBot/login?"+initdata, ssl=False)
                # self.debug(f'login text {await resp.text()}')
                resp_json = await resp.json()

                return resp_json.get("data").get("token")

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Login error {error}")

    async def claim_task(self, http_client: aiohttp.ClientSession, task):
        try:
            resp = await http_client.post(f'https://game-domain.blum.codes/api/v1/tasks/{task["id"]}/claim',
                                          ssl=False)
            resp_json = await resp.json()

            #logger.debug(f"{self.session_name} | claim_task response: {resp_json}")

            return resp_json.get('status') == "CLAIMED"
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Claim task error {error}")

    async def start_complete_task(self, http_client: aiohttp.ClientSession, task):
        try:
            resp = await http_client.post(f'https://game-domain.blum.codes/api/v1/tasks/{task["id"]}/start',
                                          ssl=False)
            resp_json = await resp.json()

            #logger.debug(f"{self.session_name} | start_complete_task response: {resp_json}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Start complete error {error}")

    async def get_tasks(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.get('https://game-domain.blum.codes/api/v1/tasks', ssl=False)
            resp_json = await resp.json()

            #logger.debug(f"{self.session_name} | get_tasks response: {resp_json}")

            if isinstance(resp_json, list):
                return resp_json
            else:
                logger.error(f"{self.session_name} | Unexpected response format in get_tasks: {resp_json}")
                return []
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Get tasks error {error}")

    async def play_game(self, http_client: aiohttp.ClientSession, play_passes):
        try:
            while play_passes:
                game_id = await self.start_game(http_client=http_client)

                if not game_id or game_id == "cannot start game":
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Couldn't start play in game!"
                                f" play_passes: {play_passes}")
                    break
                else:
                    self.success("Started playing game")

                await asyncio.sleep(random.uniform(30, 40))

                msg, points = await self.claim_game(game_id=game_id, http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Finish play in game!"
                                f" reward: {points}")
                else:
                    logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Couldn't play game,"
                                f" msg: {msg} play_passes: {play_passes}")
                    break

                await asyncio.sleep(random.uniform(30, 40))

                play_passes -= 1
        except Exception as e:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Error occurred during play game: {e}")
            await asyncio.sleep(random.randint(0, 5))

    async def start_game(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/play", ssl=False)
            response_data = await resp.json()
            if "gameId" in response_data:
                return response_data.get("gameId")
            elif "message" in response_data:
                return response_data.get("message")
        except Exception as e:
            self.error(f"Error occurred during start game: {e}")

    async def claim_game(self, game_id: str, http_client: aiohttp.ClientSession):
        try:
            points = random.randint(settings.POINTS[0], settings.POINTS[1])
            json_data = {"gameId": game_id, "points": points}

            resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data,
                                          ssl=False)
            if resp.status != 200:
                resp = await http_client.post("https://game-domain.blum.codes/api/v1/game/claim", json=json_data,
                                              ssl=False)

            txt = await resp.text()

            return True if txt == 'OK' else txt, points
        except Exception as e:
            self.error(f"Error occurred during claim game: {e}")

    async def claim(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/claim", ssl=False)
            if resp.status != 200:
                resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/claim", ssl=False)

            resp_json = await resp.json()

            return int(resp_json.get("timestamp") / 1000), resp_json.get("availableBalance")
        except Exception as e:
            self.error(f"Error occurred during claim: {e}")

    async def start(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/start", ssl=False)

            if resp.status != 200:
                resp = await http_client.post("https://game-domain.blum.codes/api/v1/farming/start", ssl=False)
        except Exception as e:
            self.error(f"Error occurred during start: {e}")

    async def get_7day_info(self, http_client: aiohttp.ClientSession):
        try:
            json_data = {"PlayerID": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/Get7DayInfo", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get("msg")
            if msg == u'success':
                data = resp_json.get("data")
                crt_id = data.get("crtID")
                signs = data.get("signs").get(str(crt_id))
                if signs == 0:
                    json_data = {"PlayerID": 0, "Type": 0}
                    resp = await http_client.post("https://api.prod.piggypiggy.io/game/Sign7Day", json=json_data, ssl=False)
                    resp_json = await resp.json()
                    msg = resp_json.get("msg")
                    if msg == u'success':
                        self.success(f"get_7day_info success")
                else:
                    self.success(f"get_7day_info already success")
            await self.balance(http_client=http_client)
            return True
        except Exception as e:
            self.error(f"Error get_7day_info: {e}")

    async def complete_achievement(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetAchievementInfo", ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get("msg")
            for task in settings.BLACKLIST_TASK:
                if msg == u'success':
                    map_info = resp_json.get("data").get("mapInfo")
                    resp_task = map_info.get(task)
                    if resp_task is None:
                        json_data = {"PlayerID": 0, "Type": 2, "Id": int(task)}
                        resp = await http_client.post("https://api.prod.piggypiggy.io/game/AddSchedule",
                                                      json=json_data, ssl=False)
                        resp_json = await resp.json()
                        msg = resp_json.get("msg")
                        if msg == u'success':
                            self.success(f"AddSchedule success:{task}")
                        else:
                            self.error(f"AddSchedule error:{task}")

            await self.do_complete_achievement(http_client=http_client)
            return True
        except Exception as e:
            self.error(f"complete achievement: {e}")

    async def do_complete_achievement(self, http_client: aiohttp.ClientSession):
        resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetAchievementInfo", ssl=False)
        resp_json = await resp.json()
        msg = resp_json.get("msg")
        if msg == u'success':
            map_info = resp_json.get("data").get("mapInfo")
            for info in map_info:
                przie = map_info.get(str(info)).get("przie")
                if przie is None:
                    self.info(f"AchievementID:{info}")
                    json_data = {"PlayerID": 0, "AchievementID": int(info)}
                    resp = await http_client.post("https://api.prod.piggypiggy.io/game/CompleteAchievement",
                                                  json=json_data, ssl=False)
                    resp_json = await resp.json()
                    msg = resp_json.get("msg")
                    if msg == u'success':
                        self.success(f"complete achievement: {info}")
                    else:
                        self.error(f"{resp_json}")
                else:
                    self.success(f"complete achievement already success: {info}")

    async def balance(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetPlayerBase", ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')

            if msg == u'success':
                currency = resp_json.get('data').get('currency')
                self.success(f"balance:{currency}")
        except Exception as e:
            self.error(f"Error occurred during balance: {e}")

    async def do_daily_task_info(self, http_client: aiohttp.ClientSession):
        try:
            json_data = {"PlayerID": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetDailyTaskInfo", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')
            if msg == u'success':
                map_task = resp_json.get('data').get('mapTask')
                for task in map_task:
                    await self.take_task(http_client=http_client, task_id=int(task))
            return True
        except Exception as e:
            self.error(f"do_daily_task_info: {e}")

    async def take_task(self, http_client: aiohttp.ClientSession, task_id: int):
        try:
            json_data = {"PlayerID": 0, "TaskID": task_id}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/TakeTask", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')
            if msg == u'success':
                self.success(f"take task：{task_id} success")
                self.success(f"<lc>[Tasking]</lc> Sleep 20S")
                await asyncio.sleep(20)
                await self.complete_task(http_client=http_client, task_id=task_id)
            else:
                self.info(f"take_task {resp_json}")
            return True
        except Exception as e:
            self.error(f"{self.session_name} take task : {e}")

    async def complete_task(self, http_client: aiohttp.ClientSession, task_id: int):
        try:
            json_data = {"PlayerID": 0, "TaskID": task_id}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/CompleteTask", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')
            if msg == u'success':
                self.success(f"complete task：{task_id} success")
        except Exception as e:
            self.error(f"complete task : {e}")

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Proxy: {proxy} | Error: {error}")

    async def run(self, proxy: str | None) -> None:
        access_token = None
        login_need = True

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await self.check_proxy(http_client=http_client, proxy=proxy)

        while True:
            try:
                if login_need:
                    if "Authorization" in http_client.headers:
                        del http_client.headers["Authorization"]

                    init_data = await self.get_tg_web_data(proxy=proxy)

                    access_token = await self.login(http_client=http_client, initdata=init_data)

                    http_client.headers["Authorization"] = f"bearer {access_token}"

                    if self.first_run is not True:
                        self.success("Logged in successfully")
                        self.first_run = True

                    login_need = False

                msg = await self.get_7day_info(http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.success(f"<light-yellow>{self.session_name}</light-yellow> | get_7day_info!")

                msg = await self.do_daily_task_info(http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.success(f"<light-yellow>{self.session_name}</light-yellow> | do_daily_task_info!")

                msg = await self.complete_achievement(http_client=http_client)
                if isinstance(msg, bool) and msg:
                    logger.success(f"<light-yellow>{self.session_name}</light-yellow> | complete_achievement!")
                #
                # timestamp, start_time, end_time, play_passes = await self.balance(http_client=http_client)
                #
                # if isinstance(play_passes, int):
                #     self.info(f'You have {play_passes} play passes')
                #
                # claim_amount, is_available = await self.friend_balance(http_client=http_client)
                #
                # if claim_amount != 0 and is_available:
                #     amount = await self.friend_claim(http_client=http_client)
                #     self.success(f"Claimed friend ref reward {amount}")
                #
                # if play_passes and play_passes > 0 and settings.PLAY_GAMES is True:
                #     await self.play_game(http_client=http_client, play_passes=play_passes)
                #
                # #await asyncio.sleep(random.uniform(1, 3))
                #
                try:
                    await self.balance(http_client=http_client)
                    self.info(f"<lc>[PiggyPiggy]</lc> Sleep 300S")
                    login_need = False
                    await asyncio.sleep(300)

                except Exception as e:
                    self.error(f"<lc>[PiggyPiggy]</lc> Error : {e}")

            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error: {error}")
                await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
