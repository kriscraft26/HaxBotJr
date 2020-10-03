from aiohttp import ClientSession
from asyncio import run

from discord import Activity, ActivityType
from discord.utils import find
from discord.ext import commands

from logger import Logger
from statistic import LeaderBoard
from msgmaker import make_alert, COLOR_ERROR
from reactablemessage import ReactableMessage
from cog.datamanager import DataManager
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
        await self.change_presence(activity=Activity(type=ActivityType.watching, name="you"))

        Logger.init()
        Logger.bot.debug("logged in as %s" % self.user)

        DataManager.load(LeaderBoard("xpTotal", Logger.xp))
        DataManager.load(LeaderBoard("xpAcc", Logger.xp))
        DataManager.load(LeaderBoard("emeraldTotal", Logger.em))
        DataManager.load(LeaderBoard("emeraldAcc", Logger.em))
        DataManager.load(LeaderBoard("warCount", Logger.war))

        self.add_cog(DataManager.load(Configuration(self)))
        self.add_cog(WynnAPI(HaxBotJr.session))
        self.add_cog(DataManager.load(MemberManager(self)))
        self.add_cog(XPTracker(self))
        self.add_cog(DataManager.load(WarTracker(self)))
        self.add_cog(DataManager.load(EmeraldTracker(self)))
        self.add_cog(DateClock(self))
        self.add_cog(RemoteDebugger(self))
        self.add_cog(DataManager())

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