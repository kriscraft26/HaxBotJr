import aiohttp
from typing import Union
from datetime import timedelta, datetime
from time import time
import backoff

from discord.ext import tasks, commands

import wynnapi
from logger import Logger
from msgmaker import decorate_text
from state.apistamp import APIStamp
from util.timeutil import now
from util.cmdutil import parser


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
    
    @parser("api")
    async def display_api_status(self, ctx: commands.Context):
        text = ""
        curr = now()
        endpoints = ("guildStats", "serverList", "terrList")
        for ep in endpoints:
            params = getattr(wynnapi.WynnAPI, ep).params
            updateTime = APIStamp.stamps[id(params)][1]
            text += "%-13s  %2ds\n" % (params["action"], (curr - updateTime).total_seconds())
        await ctx.send(decorate_text(text, title="API Update Status"))