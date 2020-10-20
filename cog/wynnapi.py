import aiohttp
from typing import Union
from datetime import timedelta, datetime
from time import time
import backoff

from discord.ext import tasks, commands

from util.timeutil import now
from logger import Logger


LEGACY_URL_BASE = "https://api.wynncraft.com/public_api.php"
V2_URL_BASE = "https://api.wynncraft.com/v2/" 
UPDATE_INTERVAL = 3  # Number of seconds between each update() call.


MOJANG_UUID_URL = "https://api.mojang.com/users/profiles/minecraft/%s?at=%s"
MOJANG_IGN_URL = "https://api.mojang.com/user/profiles/%s/names"


class WynnAPI(commands.Cog):
    """Cog that manages Wynncraft API requests.

    This Cog class manages Wynncraft API requests for guild statistics and
    server list.

    Attributes
    ----------
    guildStats: WynnData
        API request manager for guild statistics.
    serverList: WynnData
        API request manager for server list.
    """

    def __init__(self, bot, session: aiohttp.ClientSession):
        self.guildStats = WynnData(action="guildStats", command="HackForums")
        self.serverList = WynnData(action="onlinePlayers")
        self.terrList = WynnData(action="territoryList")

        self._session = session
        self.bot = bot

        self._update.start()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def _update(self):
        await self.guildStats._update(self._session)
        await self.serverList._update(self._session)
        await self.terrList._update(self._session)
    
    @_update.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting Wynncraft API update loop")
    
    async def get_player_stats(self, mcId):
        mcId = list(mcId)
        for i in [8, 13, 18, 23]:
            mcId.insert(i, "-")
        mcId = "".join(mcId)
        async with self._session.get(f"{V2_URL_BASE}player/{mcId}/stats") as resp:
            if resp.status != 200:
                Logger.bot.warning(
                    f"failed request player stat of {mcId} with {resp.status}")
                return None
            return await resp.json()
    
    async def get_player_id(self, ign):
        timestamp = int(time())
        async with self._session.get(MOJANG_UUID_URL % (ign, timestamp)) as resp:
            if resp.status != 200:
                Logger.bot.warning(
                    f"failed request player id of {ign} with {resp.status}")
                return None
            return (await resp.json())["id"]
    
    async def get_player_ign(self, mcId):
        async with self._session.get(MOJANG_IGN_URL % mcId) as resp:
            if resp.status != 200:
                Logger.bot.warning(
                    f"failed request player ign of {mcId} with {resp.status}")
                return None
            return await resp.json()


class WynnData:
    """Manages a Wynncraft API request.

    To receive non-duplicated API response, use WynnData.Tracker, which
    provides latest unique API response once until new response is 
    recrived.

    Methods
    -------
    get_tracker()
        Get an instance of this WynnData object's Tracker object.
    """

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
        """Get an instance of this WynnData object's Tracker object.

        Returns
        -------
        WynnData.Tracker
            Provide latest unique API response and other info.
        """
        return WynnData.Tracker(self)
    
    class Tracker:
        """Provide latest unique API response and other info.

        A new instance of this class should only be created through
        WynnData.get_tracker().

        Attributes
        ----------
        lastTimestamp: int
            The timestamp of latest API response.
        lastUpdateTime: datetime.datetime
            The time when latest unique API response is received in UTC
            timezone.
        
        Methods
        -------
        getData()
            Get the lastest unique API response once.
        getLastUpdateDTime()
            Get the amount of time passed since last unique API response.
        """

        def __init__(self, wynnData):
            self.lastTimestamp = -1
            self.lastUpdateTime: datetime = None
            self._wynnDta = wynnData
        
        def getData(self) -> Union[dict, None]:
            """Get the lastest unique API response once.

            The response will only returned once, after that None will be
            returned until a new unique API response is received.

            Returns
            -------
            response: dict or None
                The latest unique API response, None if it is already
                returned and no new unique API response has received.
            """
            if self._wynnDta._data:
                currTs = self._wynnDta._data["request"]["timestamp"]
                if currTs > self.lastTimestamp:
                    self.lastUpdateTime = now()
                    self.lastTimestamp = currTs
                    return self._wynnDta._data
            return None
        
        def getLastUpdateDTime(self) -> timedelta:
            """Get the amount of time passed since last unique API response.

            Returns
            -------
            datetime.timedelta
                The amount of time passed since last unique API response.
            """
            if not self.lastUpdateTime:
                return timedelta(seconds=0)
            return now() - self.lastUpdateTime
