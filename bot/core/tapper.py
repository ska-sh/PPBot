import asyncio
import random
import string
import time
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
        self.role_type = None
        self.player_id = None

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
            # InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="game")

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
                        self.success(f"7日奖励领取成功，天数： {crt_id} ")
                    else:
                        self.error(f"7日奖励领取失败")
                # else:
                #     self.info(f"7日奖励已领取")
            return True
        except Exception as e:
            self.error(f"登录领取7日奖励错误: {e}")

    #开始工作
    async def set_up_shop(self, http_client: aiohttp.ClientSession):
        try:
            self.info("准备开始工作")
            json_data = {"PlayerID": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/SetUpShop", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get("msg")
            if msg == u'success':
                self.success(f"点击开始工作完成")
            else:
                self.success(f"已经开始工作")

        except Exception as e:
            self.error(f"开始工作错误: {e}")

    async def complete_achievement(self, http_client: aiohttp.ClientSession, task_id: int):
        try:
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetAchievementInfo", ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get("msg")
            if msg == u'success':
                map_info = resp_json.get("data").get("mapInfo")
                if map_info is None:
                    json_data = {"PlayerID": 0, "Type": 2, "Id": task_id}
                    resp = await http_client.post("https://api.prod.piggypiggy.io/game/AddSchedule",
                                                  json=json_data, ssl=False)
                    resp_json = await resp.json()
                    msg = resp_json.get("msg")
                    if msg == u'success':
                        self.success(f"开始做任务: {task_id}")
                        await asyncio.sleep(60)
                else:
                    resp_task = map_info.get(task_id)
                    if resp_task is None:
                        json_data = {"PlayerID": 0, "Type": 2, "Id": int(task_id)}
                        resp = await http_client.post("https://api.prod.piggypiggy.io/game/AddSchedule",
                                                      json=json_data, ssl=False)
                        resp_json = await resp.json()
                        msg = resp_json.get("msg")
                        if msg == u'success':
                            self.success(f"开始做任务: {task_id}")
                            await asyncio.sleep(60)
                await self.do_complete_achievement(http_client=http_client, task_id=task_id)
            return True
        except Exception as e:
            self.error(f"做任务失败: {e}")

    async def do_complete_achievement(self, http_client: aiohttp.ClientSession, task_id: str):
        try:
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetAchievementInfo", ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get("msg")
            if msg == u'success':
                map_info = resp_json.get("data").get("mapInfo")
                task_info = map_info.get(task_id)
                if task_info is None:
                    return False
                przie = task_info.get("przie")
                if przie is None:
                    json_data = {"PlayerID": 0, "AchievementID": int(task_id)}
                    resp = await http_client.post("https://api.prod.piggypiggy.io/game/CompleteAchievement",
                                                  json=json_data, ssl=False)
                    resp_json = await resp.json()
                    msg = resp_json.get("msg")
                    if msg == u'success':
                        self.success(f"领取任务奖励： {task_id}")
                    else:
                        self.error(f"领取奖励失败：{resp_json}")
        except Exception as e:
            self.error(f"do_complete_achievement: {e}")

    async def balance(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetPlayerBase", ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')

            if msg == u'success':
                currency = resp_json.get('data').get('currency')
                # self.success(f"balance: {currency}")
                return currency
            else:
                self.error(f"获取金额错误:{resp_json}")
        except Exception as e:
            self.error(f"Error occurred during balance: {e}")

    async def get_shop_info(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetShopInfo", ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')

            if msg == u'success':
                shop_box = resp_json.get('data').get('shopBox')
                if shop_box is None:
                    json_data = {"RoleType": 0, "PlayerID": 0, "UseStar": 0, "ConfigID": "2001", "Param": "",
                                 "ClientParam": "2001", "Count": 1}
                    resp = await http_client.post("https://api.prod.piggypiggy.io/game/CreateStarPay", json=json_data, ssl=False)
                    resp_json = await resp.json()
                    if resp_json.get('msg') == "success":
                        self.success(f"宝箱使用成功")

            #多休眠5秒
            await asyncio.sleep(5)
        except Exception as e:
            self.error(f"Error occurred during balance: {e}")

    async def do_daily_task_info(self, http_client: aiohttp.ClientSession):
        try:

            task_list = ""

            if self.role_type == 0:
                task_list = settings.TASKLIST_CD
            elif self.role_type == 1:
                task_list = settings.TASKLIST_CD_1

            for daily_task in task_list:
                json_data = {"PlayerID": 0}
                resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetDailyTaskInfo", json=json_data, ssl=False)
                resp_json = await resp.json()
                msg = resp_json.get('msg')
                if msg == u'success':
                    #没有工作时间，点击开始工作按钮
                    set_up_shop_time = resp_json.get('data').get('setUpShopTime')
                    if set_up_shop_time is None:
                        await self.set_up_shop(http_client=http_client)
                        return True

                    #有未收取的工作奖励，点击收取
                    cur_task_id = resp_json.get('data').get('curTaskID')
                    if cur_task_id is not None:
                        await self.complete_task(http_client=http_client, task_id=cur_task_id)
                        return True

                    #卡片任务没有执行过，点击执行
                    map_task = resp_json.get('data').get('mapTask')
                    if map_task is None:
                        await self.take_task(http_client=http_client, daily_task=daily_task)
                        return True
                    else:
                        if map_task.get(str(daily_task.get("task_id"))) is None:
                            #self.success(f"task id: {daily_task.get('task_id')} is None")
                            await self.take_task(http_client=http_client, daily_task=daily_task)
                            return True

                        compelete_count = map_task.get(str(daily_task.get("task_id"))).get("compeleteCount")
                        if compelete_count < daily_task.get("compeleteCount"):
                            last_complete_time = map_task.get(str(daily_task.get("task_id"))).get("lastCompleteTime")
                            cd = time.time() - daily_task.get("cd") * 60
                            if last_complete_time < cd * 1000:
                                await self.take_task(http_client=http_client, daily_task=daily_task)
                                return True
                            else:
                                self.warning(f"工作时间冷却中: {daily_task.get('task_id')}, 冷却时间: {format_duration(last_complete_time/1000 - cd)}")
            return True
        except Exception as e:
            self.error(f"do_daily_task_info: {e}")

    async def take_task(self, http_client: aiohttp.ClientSession, daily_task: dict):
        try:
            json_data = {"PlayerID": 0, "TaskID": int(daily_task.get('task_id')), "Ad": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/TakeTask", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')
            if msg == u'success':
                self.success(f"开始工作：{daily_task.get('task_id')} 工作时间{daily_task.get('working')}秒")
                await asyncio.sleep(daily_task.get('working'))
                #多休眠5秒
                await asyncio.sleep(5)
            else:
                self.error(f"工作失败： {resp_json}, 任务id:{daily_task.get('task_id')}")
            return True
        except Exception as e:
            self.error(f"工作失败错误 : {e}")

    async def complete_task(self, http_client: aiohttp.ClientSession, task_id: int):
        try:
            json_data = {"PlayerID": 0, "TaskID": task_id, "Ad": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/CompleteTask", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')
            if msg == u'success':
                self.success(f"获取工作奖励：{task_id}")
                # 工作奖励领取完成，休息5秒
                await asyncio.sleep(5)
        except Exception as e:
            self.error(f"获取工作奖励错误 : {e}")

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Proxy: {proxy} | Error: {error}")

    async def create_star_pay(self, http_client: aiohttp.ClientSession):
        try:
            # self.info(f"开始升级角色")
            json_data = {"RoleType": 1, "PlayerID": 0, "UseStar": 0, "ConfigID": "", "Param": "", "ClientParam": "0-1", "Count": 1}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/CreateStarPay", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')
            if msg == u'success':
                self.success(f"角色升级成功")
                self.role_type = 1
            else:
                self.success(f"角色升级失败")
            return True
        except Exception as e:
            self.error(f"角色升级失败 : {e}")

    async def plunder_detail(self, http_client: aiohttp.ClientSession):
        try:
            # self.info(f"开始抢钱操作")
            json_data = {"PlayerID": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/PlunderDetail", json=json_data, ssl=False)
            resp_json = await resp.json()
            msg = resp_json.get('msg')
            if msg == u'success':
                card_cnts = resp_json.get('data').get('detail').get('cardCnt')
                if card_cnts.get('101') == 1:
                    try:
                        json_data = {"PlayerID": int(self.player_id)}
                        resp = await http_client.post("https://api.prod.piggypiggy.io/game/StartAPlunder", json=json_data, ssl=False)
                        resp_json = await resp.json()
                        msg = resp_json.get('msg')
                        if msg == u'success':
                            self.success(f"开始抢钱，默认抢劫第一用户")
                            json_data = {"PlayerID": 0, "Pos": 0}
                            resp = await http_client.post("https://api.prod.piggypiggy.io/game/TakeAPlunder", json=json_data, ssl=False)
                            resp_json = await resp.json()
                            msg = resp_json.get('msg')
                            if msg == u'success':
                                self.success(f"抢劫成功：{resp_json.get('data').get('value')}，用户原有资金：{resp_json.get('data').get('totalWinValue')}")
                    except Exception as e:
                        self.error(f"抢钱失败 : {e}")
                elif card_cnts.get('103') >= 1:
                    try:
                        # 不是翻倍状态，使用翻倍卡片
                        if resp_json.get('data').get('detail').get('fanbei') is None:
                            json_data = {"PlayerID": 0}
                            resp = await http_client.post("https://api.prod.piggypiggy.io/game/StartFanbei", json=json_data, ssl=False)
                            resp_json = await resp.json()
                            msg = resp_json.get('msg')
                            if msg == u'success':
                                self.success(f"工资翻倍成功")
                    except Exception as e:
                        self.error(f"工资翻倍错误：{e}")
                elif card_cnts.get('102') >= 1:
                    # 不是摸鱼状态，使用摸鱼卡片
                    if resp_json.get('data').get('detail').get('moyu') is None:
                        # 开始带薪休假
                        json_data = {"PlayerID": 0}
                        resp = await http_client.post("https://api.prod.piggypiggy.io/game/StartMoyu", json=json_data, ssl=False)
                        resp_json = await resp.json()
                        msg = resp_json.get('msg')
                        if msg == u'success':
                            self.success(f"带薪休假中")
                elif card_cnts.get('104') == 1:
                    self.error(f"sharingan，接口未编写")
                elif card_cnts.get('105') == 1:
                    self.error(f"无冷却时间，接口未编写")
                elif card_cnts.get('106') == 1:
                    self.error(f"刷新工作，接口未编写")
            return True
        except Exception as e:
            self.error(f"抢钱操作失败 : {e}")

    async def role_type_base(self, http_client: aiohttp.ClientSession):
        try:
            if self.role_type is None:
                resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetPlayerBase", ssl=False)
                resp_json = await resp.json()
                msg = resp_json.get('msg')

                if msg == u'success':
                    self.warning(f"账号基础信息：{resp_json}")
                    self.player_id = resp_json.get('data').get('playerID')
                    if resp_json.get('data').get('roleType') is None:
                        self.role_type = 0
                        # self.success(f"获取角色类型：0")
                    elif resp_json.get('data').get('roleType') is not None:
                        self.role_type = resp_json.get('data').get('roleType')
                        # self.success(f"获取角色类型：{self.role_type}")
            return True
        except Exception as e:
            self.error(f"获取角色类型错误: {e}")

    async def get_invite_data(self, http_client: aiohttp.ClientSession):
        try:
            json_data = {"Page": 1, "PageSize": 10, "PlayerID": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetInviteData", json=json_data, ssl=False)
            resp_json = await resp.json()
            total_count = resp_json.get('data').get('totalCount')
            if total_count is None:
                return False

            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetAchievementInfo", ssl=False)
            resp_json = await resp.json()
            map_info = resp_json.get('data').get('mapInfo')
            if map_info is None:
                return False

            if total_count >= 1 and map_info.get('2001').get('przie') is None:
                await self.do_complete_achievement(http_client=http_client, task_id='2001')
                self.success(f"获取邀请奖励成功：2001")

            if total_count >= 5 and map_info.get('2002').get('przie') is None:
                await self.do_complete_achievement(http_client=http_client, task_id='2002')
                self.success(f"获取邀请奖励成功：2002")

            if total_count >= 12 and map_info.get('2003').get('przie') is None:
                await self.do_complete_achievement(http_client=http_client, task_id='2003')
                self.success(f"获取邀请奖励成功：2003")

        except Exception as e:
            self.error(f"获取邀请奖励失败: {e}")

    async def angel_box_info(self, http_client: aiohttp.ClientSession):
        try:
            json_data = {"PlayerID": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/angel_box_info", json=json_data, ssl=False)
            resp_json = await resp.json()
            if resp.status == 200 and len(resp_json['data']) > 0:
                tasks = resp_json['data']['box']['tasks']
                if resp_json['data']['box'].get('claimState') is not None:
                    json_data = {"PlayerID": 0}
                    resp = await http_client.post("https://api.prod.piggypiggy.io/game/angel_box_claim", json=json_data, ssl=False)
                    resp_json = await resp.json()
                    if resp_json['msg'] == u'success':
                        self.success(f"angel_box_claim {resp_json['data']['awardValue']} success")
                else:
                    for task in tasks:
                        if task.get('finish') is None:
                            json_data = {"Id": int(task['taskID']), "PlayerID": 0}
                            resp = await http_client.post("https://api.prod.piggypiggy.io/game/angel_task_finish", json=json_data, ssl=False)
                            resp_json = await resp.json()
                            if resp_json.get('msg') == u'success':
                                self.success(f"{task['taskID']} finish")
                                await asyncio.sleep(60)
                            else:
                                self.error(f"{resp_json}")
                    json_data = {"PlayerID": 0}
                    resp = await http_client.post("https://api.prod.piggypiggy.io/game/angel_box_claim", json=json_data, ssl=False)
                    resp_json = await resp.json()
                    if resp_json.get('msg') == u'success':
                        self.success(f"angel_box_claim {resp_json['data']['awardValue']} success")

            json_data = {"PlayerID": 0}
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/angel_box_flush", json=json_data, ssl=False)
            resp_json = await resp.json()
            if resp_json['data'].get('retCode') == -2:
                return False
            else:
                await self.angel_box_info(http_client=http_client)
        except Exception as e:
            self.error(f"angel_box_info: {e}")

    async def get_achievement_config(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetAchievementConfig", data='null', ssl=False)
            resp_json = await resp.json()
            if resp_json['msg'] == u'success':
                str_config = json.loads(resp_json['data']['strConfig'])
                for task in str_config:
                    # self.info(f"{task}")
                    if task not in settings.NOT_DO_TASKLIST:
                        await self.complete_achievement(http_client=http_client, task_id=task)
        except Exception as e:
            self.error(f"get_achievement_config: {e}")

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

                msg = await self.role_type_base(http_client=http_client)

                msg = await self.get_7day_info(http_client=http_client)

                msg = await self.plunder_detail(http_client=http_client)

                msg = await self.get_shop_info(http_client=http_client)

                # msg = await self.do_daily_task_info(http_client=http_client)

                # msg = await self.angel_box_info(http_client=http_client)
                #
                # msg = await self.get_achievement_config(http_client=http_client)

                if settings.USE_INVITE:
                    await self.get_invite_data(http_client=http_client)

                try:
                    # json_data = {"PlayerID": 0}
                    # resp = await http_client.post("https://api.prod.piggypiggy.io/game/GetDailyTaskInfo", json=json_data, ssl=False)
                    # resp_json = await resp.json()
                    # msg = resp_json.get('msg')
                    # if msg == u'success':
                    #     map_task = resp_json.get('data').get('mapTask')
                    #     if map_task is not None:
                    #         task_list_1 = ""
                    #         if self.role_type == 0:
                    #             task_list_1 = settings.TASKLIST_CD
                    #         elif self.role_type == 1:
                    #             task_list_1 = settings.TASKLIST_CD_1
                    #         if len(map_task) >= len(task_list_1):
                    #             len_task = len(task_list_1)
                    #             for daily_task in task_list_1:
                    #                 compelete_count = daily_task.get('compeleteCount')
                    #                 map_compelete_count = map_task.get(str(daily_task.get("task_id"))).get('compeleteCount')
                    #                 if map_compelete_count == compelete_count:
                    #                     len_task = len_task - 1
                    #                 if len_task <= 0:
                                        # self.info(f"<lc>[PiggyPiggy]</lc> 工作全部完成开始做任务")
                                        # await self.angel_box_info(http_client=http_client)
                                        #


                                        # currency = await self.balance(http_client=http_client)
                                        # if settings.AUTO_UPGRADE and float(currency) > 2499 \
                                        #         and int(self.role_type) == 0:
                                        #     # self.info(f"开始抢升级角色")
                                        #     await self.create_star_pay(http_client=http_client)
                                        # self.info(f"<lc>[PiggyPiggy]</lc> 工作全部完成，休眠24小时, balance: {currency}，角色: {self.role_type}")
                                        # await asyncio.sleep(3600 * 24)
                    await self.get_achievement_config(http_client=http_client)
                    currency = await self.balance(http_client=http_client)
                    self.info(f"<lc>[PiggyPiggy]</lc> 休眠{settings.SLEEP_BETWEEN_WOEKING}秒, balance: {currency}，角色: {self.role_type}")
                    await asyncio.sleep(settings.SLEEP_BETWEEN_WOEKING)
                    login_need = False

                except Exception as e:
                    self.error(f"<lc>[PiggyPiggy]</lc> Error : {e}")

            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error: {error}")
                await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        # 在创建Tapper实例之前添加随机休眠
        if settings.SLEEP_BETWEEN_START:
            sleep_time = random.randint(settings.SLEEP_BETWEEN_START[0], settings.SLEEP_BETWEEN_START[1])
            logger.info(f"{tg_client.name} | Sleep for {sleep_time} seconds before starting session...")
            await asyncio.sleep(sleep_time)

        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
