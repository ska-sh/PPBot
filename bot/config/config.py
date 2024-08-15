from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    PLAY_GAMES: bool = True

    AUTO_UPGRADE: bool = False

    POINTS: list[int] = [190, 230]
    BLACKLIST_TASK: list[str] = ['1101', '1201', '1401', '1625', '1629', '1632', '1633', '1634', '1639', '1641', '1642',
                                 '1643']
    TASKLIST_CD: list[object] = [{"task_id": 1001, "compeleteCount": 2, "cd": 180, "working": 30},
                                 {"task_id": 1002, "compeleteCount": 5, "cd": 5, "working": 20},
                                 {"task_id": 1003, "compeleteCount": 8, "cd": 5, "working": 10},
                                 {"task_id": 1004, "compeleteCount": 8, "cd": 6, "working": 20},
                                 {"task_id": 1005, "compeleteCount": 5, "cd": 10, "working": 10},
                                 {"task_id": 1006, "compeleteCount": 5, "cd": 15, "working": 30}]

    TASKLIST_CD_1: list[object] = [{"task_id": 2001, "compeleteCount": 2, "cd": 120, "working": 20},
                                   {"task_id": 2002, "compeleteCount": 8, "cd": 2, "working": 10},
                                   {"task_id": 2003, "compeleteCount": 6, "cd": 2, "working": 10},
                                   {"task_id": 2004, "compeleteCount": 5, "cd": 5, "working": 20},
                                   {"task_id": 2005, "compeleteCount": 3, "cd": 10, "working": 20}]
    USE_REF: bool = False
    REF_ID: str = ''

    USE_PROXY_FROM_FILE: bool = False


settings = Settings()


