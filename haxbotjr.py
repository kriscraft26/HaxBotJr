from aiohttp import ClientSession
from asyncio import run

from discord.utils import find
from discord.ext import commands

from logger import Logger
from msgmaker import make_alert, COLOR_ERROR
from reactablemessage import ReactableMessage
from cog.datacog import DataCog
from cog.configuration import Configuration
from cog.wynnapi import WynnAPI
from cog.membermanager import MemberManager
from cog.xptracker import XPTracker
from cog.wartracker import WarTracker
from cog.dateclock import DateClock
from cog.remotedebugger import RemoteDebugger
from cog.emeraldtracker import EmeraldTracker

class HaxBotJr(commands.Bot):

    session = ClientSession()

    async def on_ready(self):
        Logger.init()
        Logger.bot.debug("logged in as %s" % self.user)

        self.add_cog(DataCog.load(Configuration, self))
        self.add_cog(WynnAPI(HaxBotJr.session))
        self.add_cog(DataCog.load(MemberManager, self))
        self.add_cog(XPTracker(self))
        self.add_cog(DataCog.load(WarTracker, self))
        self.add_cog(DataCog.load(EmeraldTracker, self))
        self.add_cog(DateClock(self))
        self.add_cog(RemoteDebugger(self))

        DataCog().start_saving_loop()

    @classmethod
    def exit(cls):
        Logger.bot.debug("exiting...")
        Logger.archive_logs()
        run(cls.session.close())

    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        cmd = str(ctx.command)
        if self.should_suppress_error(e):
            msg = ctx.message
            print(f"suppressed error: {e} from '{msg.content}' in #{msg.channel}")
            return
        alert = make_alert(str(e), title="Command Error")
        await ctx.send(embed=alert)
    
    def should_suppress_error(self, e: commands.CommandError):
        return str(e).startswith("The check functions")
    
    async def on_reaction_add(self, reaction, user):
        await ReactableMessage.update(reaction, user)