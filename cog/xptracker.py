from discord.ext import tasks, commands

from logger import Logger
from msgmaker import *
from leaderboard import LeaderBoard
from reactablemessage import PagedMessage
from util.cmdutil import parser
from cog.wynnapi import WynnAPI
from cog.membermanager import MemberManager
from cog.configuration import Configuration
from cog.datamanager import DataManager


XP_UPDATE_INTERVAL = 6


@DataManager.register("_prevTXp")
class XPTracker(commands.Cog):
    XP_RESET_THRESHOLD = 10000

    def __init__(self, bot: commands.Bot):
        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._guildStatsTracker = wynnAPI.guildStats.get_tracker()
        self._memberManager: MemberManager = bot.get_cog("MemberManager")
        self._config: Configuration = bot.get_cog("Configuration")

        self._lb: LeaderBoard = LeaderBoard.get_lb("xp")

        self._update.start()

    @tasks.loop(seconds=XP_UPDATE_INTERVAL)
    async def _update(self):
        guildStats = self._guildStatsTracker.getData()
        if not guildStats:
            return

        trackedIgns = self._memberManager.get_tracked_igns()

        for memberData in guildStats["members"]:
            if memberData["name"] in trackedIgns:
                id_ = self._memberManager.ignIdMap[ memberData["name"]]
                newTXp = memberData["contributed"]
                self._lb.set_stat(id_, newTXp)
    
    @_update.before_loop
    async def _before_update(self):
        Logger.bot.debug("Starting xp tracking loop")
    
    @parser("xp", ["acc"], ["bw"], isGroup=True)
    async def display_xp_lb(self, ctx: commands.Context, acc, bw):
        pages = self._lb.create_pages(acc, bw,
            title="XP Leader Board", api=self._guildStatsTracker)
        
        await PagedMessage(pages, ctx.channel).init()