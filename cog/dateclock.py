from datetime import datetime, timedelta
import os

from discord.ext import commands, tasks

from logger import Logger
from msgmaker import decorate_text
from util.cmdutil import parser
import util.timeutil as timeutil
from util.discordutil import Discord
from state.config import Config
from state.statistic import Statistic
from cog.remotedebugger import RemoteDebugger
from cog.snapshotmanager import SnapshotManager
from cog.activitytracker import ActivityTracker


class DateClock(commands.Cog):

    def __init__(self, bot: commands.Bot):
        now = timeutil.now()
        deltaDay = (now - timeutil.BI_WEEK_REF).days
        self.bwIndex = deltaDay % 14 + 1
        Logger.bot.info(f"Started at {now} with bwIndex of {self.bwIndex}")

        self.initRun = True

        self._remoteDebugger: RemoteDebugger = bot.get_cog("RemoteDebugger")
        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._update_loop_interval()
        self._daily_loop.start()
    
    @tasks.loop(seconds=0)
    async def _daily_loop(self):
        if self.initRun:
            self.initRun = False
            return
        Logger.bot.debug(f"start daily loop {timeutil.now()} with bwIndex {self.bwIndex}")
        
        await self._daily_callback()

        self.bwIndex += 1
        if self.bwIndex > 14:
            self.bwIndex = 1
            await self._bw_callback()
        Logger.bot.info(f"bwIndex -> {self.bwIndex}")

        self._update_loop_interval()
    
    async def _daily_callback(self):
        archiveNames = Logger.reset()
        self._remoteDebugger.add_archives(*archiveNames)

    async def _bw_callback(self):
        Logger.bot.debug(f"Bi week transitioned at {timeutil.now()}")
        await self._snapshotManager.save_snapshot()
        Statistic.reset_biweekly()

    def _update_loop_interval(self):
        now = timeutil.now()
        nextDay = timeutil.add_tz_info(
            datetime.combine(now.date() + timedelta(days=1), datetime.min.time()))
        # nextDay = now + timedelta(seconds=30)
        delta = nextDay - now
        Logger.bot.debug(f"next day at {nextDay}, {delta} away from {now}")
        self._daily_loop.change_interval(seconds=delta.total_seconds())
    
    @parser("now")
    async def display_time(self, ctx: commands.Context):
        time = timeutil.now().strftime("%b %d, %H:%M:%S (UTC)")
        text = f"{time}\nday {self.bwIndex} of current bi-week"
        await ctx.send(decorate_text(text))
    
    @parser("trigger", ["cbType", ("daily", "biweekly", "bwReport")])
    async def trigger_callback(self, ctx: commands.Context, cbType):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return
        if cbType == "bwReport":
            return
        func = self._daily_callback if cbType == "daily" else self._bw_callback
        await func()