import aiohttp
from typing import Union
from datetime import timedelta, datetime
from time import time
import backoff

from discord.ext import tasks, commands

import wynnapi
from logger import Logger
from util.timeutil import now


UPDATE_INTERVAL = 10  # Number of seconds between each update() call.


class WynnAPI(commands.Cog):

    def __init__(self, bot, session: aiohttp.ClientSession):
        wynnapi.WynnAPI.init(session)
        self.bot = bot
        self._update.start()

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def _update(self):
        await wynnapi.WynnAPI.update()
    
    @_update.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting Wynncraft API update loop")