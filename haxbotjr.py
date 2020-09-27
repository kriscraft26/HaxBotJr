from aiohttp import ClientSession
from asyncio import run

from discord.ext import commands

from logger import Logger
from msgmaker import make_alert, COLOR_ERROR
from pagedmessage import PagedMessage
from cog.datacog import DataCog
from cog.configuration import Configuration
from cog.wynnapi import WynnAPI
from cog.membermanager import MemberManager
from cog.xptracker import XPTracker
from cog.wartracker import WarTracker
from cog.dateclock import DateClock

class HaxBotJr(commands.Bot):

    session = ClientSession()

    async def on_ready(self):
        Logger.init()
        Logger.bot.debug("logged in as %s" % self.user)

        DataCog.init(self)

        self.add_cog(DataCog.load(Configuration, self))
        self.add_cog(WynnAPI(HaxBotJr.session))
        self.add_cog(DataCog.load(MemberManager, self))
        self.add_cog(XPTracker(self))
        self.add_cog(DataCog.load(WarTracker, self))
        self.add_cog(DateClock(self))

        DataCog().start_saving_loop()

    @classmethod
    def exit(cls):
        Logger.bot.debug("exiting...")
        DataCog.save()
        Logger.archive_logs()
        run(cls.session.close())

    async def on_command_error(self, ctx: commands.Context, e: Exception):
        alert = make_alert("Command Error", str(e), None, color=COLOR_ERROR)
        await ctx.send(embed=alert)
    
    async def on_reaction_add(self, reaction, user):
        await PagedMessage.update(reaction, user)