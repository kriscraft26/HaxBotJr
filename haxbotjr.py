from aiohttp import ClientSession
from asyncio import run
from traceback import print_tb
from colorama import Back, Fore, Style

from discord import Activity, ActivityType
from discord.utils import find
from discord.ext import commands

from logger import Logger
from leaderboard import LeaderBoard
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
from cog.snapshotmanager import SnapshotManager

class HaxBotJr(commands.Bot):

    session = ClientSession()

    async def on_ready(self):
        await self.change_presence(activity=Activity(type=ActivityType.watching, name="you"))

        Logger.init()
        Logger.bot.debug("logged in as %s" % self.user)

        DataManager.load(LeaderBoard("xp", Logger.xp))
        DataManager.load(LeaderBoard("emerald", Logger.em))
        DataManager.load(LeaderBoard("warCount", Logger.war))

        self.add_cog(DataManager.load(Configuration(self)))
        self.add_cog(WynnAPI(HaxBotJr.session))
        self.add_cog(SnapshotManager(self))
        self.add_cog(DataManager.load(MemberManager(self)))
        self.add_cog(DataManager.load(XPTracker(self)))
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

    async def on_command_error(self, ctx: commands.Context, e: Exception):
        eStr = str(e)
        if eStr.startswith("The check functions"):
            return
        if eStr.startswith("Command") and eStr.endswith("is not found"):
            await ctx.send(embed=make_alert(eStr))
            return
        await ctx.send(embed=make_alert("oh oopsie owo", 
            subtext="Pwease contact Pucaet abouwt thiws uwu"))
        print(Fore.RED + Style.BRIGHT)
        await super().on_command_error(ctx, e)
    
    async def on_reaction_add(self, reaction, user):
        await ReactableMessage.update(reaction, user)