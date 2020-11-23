from discord.ext import tasks, commands

from logger import Logger
from event import Event
from wynnapi import WynnAPI
from msgmaker import *
from reactablemessage import RMessage
from util.cmdutil import parser
from util.discordutil import Discord
from state.config import Config
from state.guildmember import GuildMember
from state.statistic import Statistic
from cog.datamanager import DataManager
from cog.snapshotmanager import SnapshotManager


XP_UPDATE_INTERVAL = 30
XP_LOG_INTERVAL = 5  # in minutes


class XPTracker(commands.Cog):
    XP_RESET_THRESHOLD = 10000

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self._guildStatsReceiver = WynnAPI.guildStats.create_receiver()
        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._logEntries = {}

        self._update.start()
        self._xp_log.start()
        self._snapshotManager.add("XPTracker", self)

        Event.listen("xpChange", self.on_xp_change)
    
    async def __snap__(self):
        return (
            await self.make_xp_lb_pages(False),
            await self.make_xp_lb_pages(True)
        )

    async def on_xp_change(self, id_, diff):
        if id_ not in self._logEntries:
            self._logEntries[id_] = 0
        self._logEntries[id_] += diff

    @tasks.loop(seconds=XP_UPDATE_INTERVAL)
    async def _update(self):
        guildStats = self._guildStatsReceiver.getData()
        if not guildStats:
            return

        for memberData in guildStats["members"]:
            if GuildMember.is_ign_active(memberData["name"]):
                id_ = GuildMember.ignIdMap[ memberData["name"]]
                await Statistic.stats[id_].update_xp(memberData["contributed"])
    
    @_update.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting xp tracking loop")
    
    @tasks.loop(minutes=XP_LOG_INTERVAL)
    async def _xp_log(self):
        filter_ = lambda m: m.status == GuildMember.ACTIVE

        logs = []
        for id_, diff in self._logEntries.items():
            xpStat = Statistic.stats[id_].xp

            logs.append("  |  ".join([
                f"**{GuildMember.members[id_].ign}** +{diff:,}",
                f"__Total__ -> {xpStat['total']:,}",
                f"__Bi-Week__ -> {xpStat['biweek']:,}"]))
        self._logEntries.clear()
        for log in logs:
            await Discord.send(Config.channel_xpLog, log)
    
    @_xp_log.before_loop
    async def _before_xp_log(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting xp logging loop")
    
    async def make_xp_lb_pages(self, total):
        if total:
            lb = Statistic.xpTotalLb
            field = "total"
            titlePrefix = "Total "
        else:
            lb = Statistic.xpLb
            field = "biweek"
            titlePrefix = "Bi-Weekly "

        valGetter = lambda m: Statistic.stats[m.id].xp[field]
        filter_ = lambda m: m.status != GuildMember.REMOVED
        
        return make_entry_pages(await make_stat_entries(
            valGetter, filter_=filter_, lb=lb),
            title=titlePrefix + "XP Leader Board", endpoint=WynnAPI.guildStats)
    
    @parser("xp", ["total"], "-snap", isGroup=True)
    async def display_xp_lb(self, ctx: commands.Context, total, snap):
        if snap:
            pages = await self._snapshotManager.get_snapshot_cmd(ctx, snap, 
                "XPTracker", total)
            if not pages:
                return
        else:
            pages = await self.make_xp_lb_pages(total)
        
        rMsg = RMessage(await ctx.send(pages[0]))
        await rMsg.add_pages(pages)
    
    @parser("xp fix", parent=display_xp_lb)
    async def fix_xp(self, ctx: commands.Context):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return