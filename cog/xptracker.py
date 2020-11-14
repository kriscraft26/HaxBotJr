from discord.ext import tasks, commands

from logger import Logger
from wynnapi import WynnAPI
from msgmaker import *
from leaderboard import LeaderBoard
from reactablemessage import PagedMessage
from util.cmdutil import parser
from util.discordutil import Discord
from state.config import Config
from state.guildmember import GuildMember
from cog.datamanager import DataManager
from cog.snapshotmanager import SnapshotManager


XP_UPDATE_INTERVAL = 30
XP_LOG_INTERVAL = 5  # in minutes


class XPTracker(commands.Cog):
    XP_RESET_THRESHOLD = 10000

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._guildStatsTracker = WynnAPI.guildStats.get_tracker()
        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._lb: LeaderBoard = LeaderBoard.get_lb("xp")
        self._lastLoggedVal = {}

        self._update.start()
        self._xp_log.start()
        self._snapshotManager.add("XPTracker", self)
    
    async def __snap__(self):
        return await self._snapshotManager.make_lb_snapshot(self._lb, 
            title="XP Leader Board", api=self._guildStatsTracker)

    @tasks.loop(seconds=XP_UPDATE_INTERVAL)
    async def _update(self):
        guildStats = self._guildStatsTracker.getData()
        if not guildStats:
            return


        for memberData in guildStats["members"]:
            if GuildMember.is_ign_active(memberData["name"]):
                id_ = GuildMember.ignIdMap[ memberData["name"]]
                self._lb.set_stat(id_,  memberData["contributed"])
    
    @_update.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting xp tracking loop")
    
    @tasks.loop(minutes=XP_LOG_INTERVAL)
    async def _xp_log(self):
        filter_ = lambda m: m.status == GuildMember.ACTIVE
        mapper = lambda m: m.id

        async for id_ in GuildMember.iterate(filter_, mapper):
            stat = self._lb.get_stat(id_)
            prev = self._lastLoggedVal.get(id_, -1)
            if prev == -1:
                self._lastLoggedVal[id_] = stat
                continue

            dxp = stat - prev
            if not dxp:
                continue
            text = "  |  ".join([
                f"**{GuildMember.members[id_].ign}** (+{dxp:,})",
                f"__Total__ -> {self._lb.get_total(id_):,}",
                f"__Acc__ -> {self._lb.get_acc(id_):,}",
                f"__BW__ -> {self._lb.get_bw(id_):,}"])
            await Discord.send(Config.channel_xpLog, text)
            self._lastLoggedVal[id_] = stat
    
    @_xp_log.before_loop
    async def _before_xp_log(self):
        await self.bot.wait_until_ready()
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
            pages = await self._lb.create_pages(acc, total,
                title="XP Leader Board", api=self._guildStatsTracker)
        
        await PagedMessage(pages, ctx.channel).init()
    
    @parser("xp fix", parent=display_xp_lb)
    async def fix_xp(self, ctx: commands.Context):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return