import aiohttp
from typing import Union
from datetime import timedelta, datetime
from time import time
import backoff

from util.timeutil import now
from logger import Logger


LEGACY_URL_BASE = "https://api.wynncraft.com/public_api.php"
V2_URL_BASE = "https://api.wynncraft.com/v2/" 


MOJANG_UUID_URL = "https://api.mojang.com/users/profiles/minecraft/%s?at=%s"
MOJANG_IGN_URL = "https://api.mojang.com/user/profiles/%s/names"


class WynnData:

    def __init__(self, **params):
        self._data: dict = None
        self.url = LEGACY_URL_BASE
        self.params = params
    
    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=3)
    async def _update(self, session: aiohttp.ClientSession):
        async with session.get(self.url, params=self.params, raise_for_status=True) as resp:
            if resp.status != 200:
                Logger.bot.warning(f"failed request {self.params} with {resp.status}")
                return
            self._data = await resp.json()
    
    def get_tracker(self):
        return WynnData.Tracker(self)
    
    class Tracker:
        
        def __init__(self, wynnData):
            self.lastTimestamp = -1
            self.lastUpdateTime: datetime = None
            self._wynnDta = wynnData
        
        def getData(self) -> Union[dict, None]:
            if self._wynnDta._data:
                currTs = self._wynnDta._data["request"]["timestamp"]
                if currTs > self.lastTimestamp:
                    self.lastUpdateTime = now()
                    self.lastTimestamp = currTs
                    return self._wynnDta._data
            return None
        
        def getLastUpdateDTime(self) -> timedelta:
            if not self.lastUpdateTime:
                return timedelta(seconds=0)
            return now() - self.lastUpdateTime


class WynnAPI:

    guildStats = WynnData(action="guildStats", command="HackForums")
    serverList = WynnData(action="onlinePlayers")
    terrList = WynnData(action="territoryList")

    _session: aiohttp.ClientSession = None

    @classmethod
    def init(cls, session):
        cls._session = session

    @classmethod
    async def update(cls):
        await cls.guildStats._update(cls._session)
        await cls.serverList._update(cls._session)
        await cls.terrList._update(cls._session)
    
    @classmethod
    async def get_player_stats(cls, mcId):
        mcId = list(mcId)
        for i in [8, 13, 18, 23]:
            mcId.insert(i, "-")
        mcId = "".join(mcId)
        async with cls._session.get(f"{V2_URL_BASE}player/{mcId}/stats") as resp:
            if resp.status != 200:
                Logger.bot.warning(
                    f"failed request player stat of {mcId} with {resp.status}")
                return None
            return await resp.json()
    
    @classmethod
    async def get_player_id(cls, ign):
        timestamp = int(time())
        async with cls._session.get(MOJANG_UUID_URL % (ign, timestamp)) as resp:
            if resp.status != 200:
                Logger.bot.warning(
                    f"failed request player id of {ign} with {resp.status}")
                return None
            return (await resp.json())["id"]
    
    @classmethod
    async def get_player_ign(cls, mcId):
        async with cls._session.get(MOJANG_IGN_URL % mcId) as resp:
            if resp.status != 200:
                Logger.bot.warning(
                    f"failed request player ign of {mcId} with {resp.status}")
                return None
            return (await resp.json())[0]["name"]