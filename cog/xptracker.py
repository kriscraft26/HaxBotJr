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
from cog.snapshotmanager import SnapshotManager


XP_UPDATE_INTERVAL = 6
XP_LOG_INTERVAL = 5  # in minutes


@DataManager.register("_prevTXp")
class XPTracker(commands.Cog):
    XP_RESET_THRESHOLD = 10000

    def __init__(self, bot: commands.Bot):
        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._guildStatsTracker = wynnAPI.guildStats.get_tracker()
        self._memberManager: MemberManager = bot.get_cog("MemberManager")
        self._config: Configuration = bot.get_cog("Configuration")
        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._lb: LeaderBoard = LeaderBoard.get_lb("xp")
        self._lastLoggedVal = {}
        self._prevXp = {}

        self._update.start()
        self._xp_log.start()
        self._snapshotManager.add("XPTracker", self)
    
    def __snap__(self):
        return self._snapshotManager.make_lb_snapshot(self._lb, 
            title="XP Leader Board", api=self._guildStatsTracker)

    @tasks.loop(seconds=XP_UPDATE_INTERVAL)
    async def _update(self):
        guildStats = self._guildStatsTracker.getData()
        if not guildStats:
            return

        trackedIgns = self._memberManager.get_tracked_igns()

        for memberData in guildStats["members"]:
            if memberData["name"] in trackedIgns:
                id_ = self._memberManager.ignIdMap[ memberData["name"]]
                prevXp = self._prevXp.get(id_, -1)
                currXp = self._lb.get_stat(id_)
                newXp = memberData["contributed"]
                if prevXp != newXp:
                    self._lb.set_stat(id_, newXp)
                self._prevXp[id_] = currXp
    
    @_update.before_loop
    async def _before_update(self):
        Logger.bot.debug("Starting xp tracking loop")
    
    @tasks.loop(minutes=XP_LOG_INTERVAL)
    async def _xp_log(self):
        for id_ in self._memberManager.members:
            stat = self._lb.get_stat(id_)
            prev = self._lastLoggedVal.get(id_, -1)
            if prev == -1:
                self._lastLoggedVal[id_] = stat
                continue

            dxp = stat - prev
            if not dxp:
                continue
            text = "  |  ".join([
                f"**{self._memberManager.members[id_].ign}** (+{dxp:,})",
                f"__Total__ -> {self._lb.get_total(id_):,}",
                f"__Acc__ -> {self._lb.get_acc(id_):,}",
                f"__BW__ -> {self._lb.get_bw(id_):,}"])
            await self._config.send("xpLog", text)
            self._lastLoggedVal[id_] = stat
    
    @_xp_log.before_loop
    async def _before_xp_log(self):
        Logger.bot.debug("Starting xp logging loop")
    
    @parser("xp", ["acc"], ["total"], "-snap", isGroup=True)
    async def display_xp_lb(self, ctx: commands.Context, acc, total, snap):
        if snap:
            snapshot = await self._snapshotManager.get_snapshot_cmd(ctx, snap, 
                "XPTracker")
            if not snapshot:
                return
            pages = snapshot[acc][total]
        else:
            pages = self._lb.create_pages(acc, total,
                title="XP Leader Board", api=self._guildStatsTracker)
        
        await PagedMessage(pages, ctx.channel).init()
    
    @parser("xp fix", parent=display_xp_lb)
    async def fix_xp(self, ctx: commands.Context):
        if not await self._config.perm_check(ctx, "user.dev"):
            return
        id_ = self._memberManager.ignIdMap["chriscold10"]
        self._lb._total[id_] = self._lb.get_total(id_) + 23346331
        self._lb._rank(id_, self._lb._totalLb, self._lb.get_total)

        self._lb._acc[id_] = self._lb.get_acc(id_) + 23346331
        self._lb._rank(id_, self._lb._accLb, self._lb.get_acc)

        self._lb._bw[id_] = self._lb.get_bw(id_) + 23151947
        self._lb._rank(id_, self._lb._bwLb, self._lb.get_bw)