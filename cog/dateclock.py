from datetime import datetime, timedelta
import os

from discord.ext import commands, tasks

from logger import Logger
from msgmaker import decorate_text
from leaderboard import LeaderBoard
from util.cmdutil import parser
import util.timeutil as timeutil
from cog.remotedebugger import RemoteDebugger


class DateClock(commands.Cog):

    def __init__(self, bot: commands.Bot):
        now = timeutil.now()
        deltaDay = (now - timeutil.BI_WEEK_REF).days
        self.bwIndex = deltaDay % 14 + 1
        Logger.bot.info(f"Started at {now} with bwIndex of {self.bwIndex}")

        self.initRun = True

        self._remoteDebugger: RemoteDebugger = bot.get_cog("RemoteDebugger")

        self._update_loop_interval()
        self._daily_loop.start()
    
    @tasks.loop(seconds=0)
    async def _daily_loop(self):
        if self.initRun:
            self.initRun = False
            return
        Logger.bot.debug(f"start daily loop {timeutil.now()} with bwIndex {self.bwIndex}")
        
        archiveNames = Logger.reset()
        self._remoteDebugger.add_archives(*archiveNames)

        self.bwIndex += 1
        if self.bwIndex > 14:
            self.bwIndex = 1
            self._on_bi_week_transition()
        Logger.bot.info(f"bwIndex -> {self.bwIndex}")

        self._update_loop_interval()
    
    def _on_bi_week_transition(self):
        Logger.bot.debug(f"Bi week transitioned at {timeutil.now()}")
        LeaderBoard.update_all_bw_base()

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