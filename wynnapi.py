import aiohttp
from typing import Union
from datetime import timedelta, datetime
from time import time
import backoff

from util.timeutil import now
from logger import Logger
from state.apistamp import APIStamp


LEGACY_URL_BASE = "https://api.wynncraft.com/public_api.php"
V2_URL_BASE = "https://api.wynncraft.com/v2/" 


MOJANG_UUID_URL = "https://api.mojang.com/users/profiles/minecraft/%s?at=%s"
MOJANG_IGN_URL = "https://api.mojang.com/user/profiles/%s/names"


class APIEndpoint:

    def __init__(self, **params):
        self._data: dict = None
        self._receivers = set()
        self.url = LEGACY_URL_BASE
        self.params = params
    
    @backoff.on_exception(backoff.expo, aiohttp.ClientError, max_tries=3)
    async def _update(self, session: aiohttp.ClientSession):
        async with session.get(self.url, params=self.params, raise_for_status=True) as resp:
            if resp.status != 200:
                Logger.bot.warning(f"failed request {self.params} with {resp.status}")
                return
            resp = await resp.json()
            if APIStamp.set_stamp(self.params, resp["request"]["timestamp"]):
                self._data = resp
                for receiver in self._receivers:
                    receiver._isUpdated = True
    
    def create_receiver(self):
        receiver = APIEndpoint.Receiver(self)
        self._receivers.add(receiver)
        return receiver
    
    class Receiver:
        
        def __init__(self, endpoint):
            self._isUpdated = False
            self._endpoint = endpoint 
        
        def getData(self) -> Union[dict, None]:
            if self._isUpdated:
                self._isUpdated = False
                return self._endpoint._data
            return None


class WynnAPI:

    guildStats = APIEndpoint(action="guildStats", command="HackForums")
    serverList = APIEndpoint(action="onlinePlayers")
    terrList = APIEndpoint(action="territoryList")

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
            return (await resp.json())[-1]["name"]