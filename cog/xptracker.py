from discord.ext import tasks, commands

from logger import Logger
from msgmaker import *
from leaderboard import LeaderBoard
from reactablemessage import PagedMessage, ConfirmMessage
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

        self._prevTXp = {}

        self._update.start()

    @tasks.loop(seconds=XP_UPDATE_INTERVAL)
    async def _update(self):
        guildStats = self._guildStatsTracker.getData()
        if not guildStats:
            return

        trackedIgns = self._memberManager.get_tracked_igns()
        xpTotalLb: LeaderBoard = LeaderBoard.get_lb("xpTotal")

        for memberData in guildStats["members"]:
            if memberData["name"] in trackedIgns:
                id_ = self._memberManager.ignIdMap[ memberData["name"]]
                newTXp = memberData["contributed"]

                prevTXp = self._prevTXp.get(id_, -1)
                if prevTXp == newTXp:
                    continue

                self._prevTXp[id_] = xpTotalLb.get_stat(id_)
                LeaderBoard.accumulate(id_, "xp", newTXp)
    
    @_update.before_loop
    async def _before_update(self):
        Logger.bot.debug("Starting xp tracking loop")
        
    def reset_xp(self):
        Logger.bot.info("resetting all accumulated xp.")
        LeaderBoard.get_lb("xpAcc").reset_stats()
    
    @parser("xp", ["total"], isGroup=True)
    async def display_xp_lb(self, ctx: commands.Context, total):
        lbName = "xpTotal" if total else "xpAcc"
        title = ("Total" if total else "Accumulated") + " XP Leader Board"
        pages = LeaderBoard.get_lb(lbName).create_pages(
            title=title, api=self._guildStatsTracker)
        
        await PagedMessage(pages, ctx.channel).init()
    
    @parser("xp reset", parent=display_xp_lb)
    async def reset_xp_cmd(self, ctx: commands.Context):
        if not await self._config.perm_check(ctx, "group.staff"):
            return

        text = "Are you sure to reset all members' accumulated xp?"
        successText = "Successfully reset all members' accumulated xp."

        await ConfirmMessage(ctx, text, successText, lambda msg: self.reset_xp()).init()