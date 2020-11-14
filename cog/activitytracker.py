from datetime import timedelta
from asyncio import sleep
from math import trunc

from discord.ext import commands, tasks

from logger import Logger
from event import Event
from wynnapi import WynnAPI
from msgmaker import make_entry_pages, make_stat_entries, decorate_text
from reactablemessage import PagedMessage
from util.cmdutil import parser
from util.timeutil import now as utcNow
from util.discordutil import Discord
from state.config import Config
from state.guildmember import GuildMember
from cog.datamanager import DataManager
from cog.snapshotmanager import SnapshotManager


ACTIVITY_UPDATE_INTERVAL = 1  # in minutes


@DataManager.register("activities", "lastUpdateTime")
class ActivityTracker(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        self._snapManager: SnapshotManager = bot.get_cog("SnapshotManager")
        self._serverListTracker = WynnAPI.serverList.get_tracker()

        self.activities = {}  # id: [actTotal, actCurr, isOnline, server]
        self.lastUpdateTime = utcNow()
        self.apiTimestamps = {}
        self.lb = []
        self.currLb = []

        self.bot = bot

        self._snapManager.add("ActivityTracker", self)
        
        Event.listen("memberAdd", self.on_member_add)
        Event.listen("memberStatusChange", self.on_member_status_change)
    
    async def __snap__(self):
        return await self._make_activity_pages()
    
    async def __loaded__(self):
        self._activity_update.start()
    
    @tasks.loop(minutes=ACTIVITY_UPDATE_INTERVAL)
    async def _activity_update(self):        
        serverList = self._serverListTracker.getData()
        if not serverList:
            return
        
        filter_ = lambda m: m.status == GuildMember.ACTIVE
        tracked = {m.ign async for m in GuildMember.iterate(filter_)}

        now = utcNow()
        if self.lastUpdateTime:
            interval = now - self.lastUpdateTime
        else:
            interval = timedelta(seconds=0)

        for server, players in serverList.items():
            for ign in players:
                if ign in tracked:

                    data = self.activities[GuildMember.ignIdMap[ign]]

                    if data[2]:
                        if not server.startswith("lobby"):
                            data[0] += interval
                        data[1] += interval
                    
                    data[2] = True
                    data[3] = server

                    tracked.remove(ign)
        
        for ign in tracked:
            data = self.activities[GuildMember.ignIdMap[ign]]
            data[1] = timedelta(seconds=0)
            data[2] = False
            data[3] = None
        
        await self._update_lb()

        # print(utcNow() - now)
        self.lastUpdateTime = now
    
    @_activity_update.before_loop
    async def _before_activity_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting activity update loop")
    
    async def _update_lb(self):
        filter_ = lambda m: m.status != GuildMember.REMOVED
        lb = [m.id async for m in GuildMember.iterate(filter_)]
        self.lb = sorted(lb, key=lambda id_: -1 * self.activities[id_][0])
        self.currLb = sorted(lb, key=lambda id_: -1 * self.activities[id_][1])
    
    async def on_member_add(self, id_):
        self.activities[id_] = [timedelta(seconds=0), timedelta(seconds=0), False, None]
        await self._update_lb()
    
    async def on_member_status_change(self, id_, prevStatus):
        currStatus = GuildMember.members[id_].status
        if currStatus != GuildMember.ACTIVE:
            data = self.activities[id_]
            data[1] = timedelta(seconds=0)
            data[2] = False
            data[3] = None
        if currStatus == GuildMember.REMOVED or prevStatus == GuildMember.REMOVED:
            await self._update_lb()
    
    def biweekly_reset(self):
        Logger.bot.info("Reseting activities")
        for data in self.activities.values():
            data[0] = timedelta(seconds=0)
    
    def _format_dt(self, dt: timedelta):
        days = dt.days
        seconds = trunc(dt.seconds)
        hours = seconds // 3600
        minutes = seconds // 60 % 60
        seconds = seconds % 60

        return f"{days:02} {hours:02}:{minutes:02}:{seconds:02}"
    
    def _get_last_update_dt(self):
        dt = utcNow() - self.lastUpdateTime
        return f"{trunc(dt.seconds)} seconds ago"

    @parser("online")
    async def display_online(self, ctx: commands.Context):
        valGetter = lambda m: \
            self._format_dt(self.activities[m.id][1]) + " " + self.activities[m.id][3]
        filter_ = lambda m: self.activities[m.id][2]
        text = decorate_text("\n".join(await make_stat_entries(
            valGetter, group=False, filter_=filter_, rank=False, lb=self.currLb)),
            title="Online Members", lastUpdate=self._get_last_update_dt())
        await ctx.send(text)
    
    async def _make_activity_pages(self):
        valGetter = lambda m: self._format_dt(self.activities[m.id][0])
        pages = make_entry_pages(await make_stat_entries(
            valGetter, group=False, lb=self.lb), 
            title="Activities", lastUpdate=self._get_last_update_dt())

        return pages
    
    @parser("act", "-snap", isGroup=True)
    async def display_activity(self, ctx: commands.Context, snap):
        if snap:
            pages = await self._snapManager.get_snapshot_cmd(ctx, snap, 
                "ActivityTracker")
            if not pages:
                return
        else:
            pages = await self._make_activity_pages()

        await PagedMessage(pages, ctx.channel).init()
    
    @parser("act reset", parent=display_activity)
    async def reset_activity(self, ctx: commands.Context):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return
        self.biweekly_reset()
        await ctx.message.add_reaction("✅")