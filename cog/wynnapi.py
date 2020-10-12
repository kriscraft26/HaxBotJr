import requests
import aiohttp
from typing import Union
from datetime import timedelta, datetime

from discord.ext import tasks, commands

from util.timeutil import now
from logger import Logger


LEGACY_URL_HEADER = "https://api.wynncraft.com/public_api.php"
UPDATE_INTERVAL = 3  # Number of seconds between each update() call.


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

    def __init__(self, session: aiohttp.ClientSession):
        self.guildStats = WynnData(action="guildStats", command="HackForums")
        self.serverList = WynnData(action="onlinePlayers")
        self.terrList = WynnData(action="territoryList")

        self._session = session

        self._update.start()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def _update(self):
        await self.guildStats._update(self._session)
        await self.serverList._update(self._session)
        await self.terrList._update(self._session)
    
    @_update.before_loop
    async def _before_update(self):
        Logger.bot.debug("Starting Wynncraft API update loop")


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
        self.url = LEGACY_URL_HEADER
        self.params = params
    
    async def _update(self, session: aiohttp.ClientSession):
        async with session.get(self.url, params=self.params) as resp:
            if resp.status != 200:
                Logger.bot.warning(f"failed GET {self.url}, status code: {resp.status}")
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
