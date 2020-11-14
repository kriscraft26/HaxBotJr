from aiohttp import ClientSession
from asyncio import run
from colorama import Back, Fore, Style

from discord import Activity, ActivityType
from discord.utils import find
from discord.ext import commands

from logger import Logger
from leaderboard import LeaderBoard
from msgmaker import make_alert, COLOR_ERROR
from reactablemessage import ReactableMessage
from util.discordutil import Discord
from state.state import State
from state.config import Config
from state.guildmember import GuildMember
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
from cog.claimtracker import ClaimTracker
from cog.help import Help
from cog.misc import Misc
from cog.votation import Votation
from cog.activitytracker import ActivityTracker
from cog.discordtools import DiscordTools

class HaxBotJr(commands.Bot):

    session = None

    async def on_ready(self):
        await self.change_presence(activity=Activity(type=ActivityType.watching, name="you"))

        Logger.init()
        Logger.bot.debug("logged in as %s" % self.user)

        Discord.init(self)

        HaxBotJr.session = ClientSession()

        await State.load(Config)
        await State.load(GuildMember)
    
        await DataManager.load(LeaderBoard("xp", Logger.xp))
        await DataManager.load(LeaderBoard("emerald", Logger.em))
        await DataManager.load(LeaderBoard("warCount", Logger.war))

        self.add_cog(Configuration(self))
        self.add_cog(WynnAPI(self, HaxBotJr.session))
        self.add_cog(SnapshotManager(self))
        self.add_cog(MemberManager(self))
        self.add_cog(XPTracker(self))
        self.add_cog(await DataManager.load(WarTracker(self)))
        self.add_cog(await DataManager.load(EmeraldTracker(self)))
        self.add_cog(await DataManager.load(ClaimTracker(self)))
        self.add_cog(await DataManager.load(ActivityTracker(self)))
        self.add_cog(RemoteDebugger(self))
        self.add_cog(DateClock(self))
        self.add_cog(DataManager(self))
        self.add_cog(Help(self))
        self.add_cog(Misc(self))
        self.add_cog(await DataManager.load(Votation(self)))
        self.add_cog(DiscordTools(self))

        print("ready")

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
        await super().on_command_error(ctx, e)
    
    async def on_reaction_add(self, reaction, user):
        await ReactableMessage.update(reaction, user)