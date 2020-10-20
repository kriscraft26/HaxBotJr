from datetime import timedelta
from asyncio import sleep
from math import trunc

from discord.ext import commands, tasks

from logger import Logger
from msgmaker import make_entry_pages, make_stat_entries, decorate_text
from reactablemessage import PagedMessage
from util.cmdutil import parser
from util.timeutil import now as utcNow
from cog.membermanager import MemberManager
from cog.datamanager import DataManager
from cog.wynnapi import WynnAPI
from cog.snapshotmanager import SnapshotManager
from cog.configuration import Configuration


ACTIVITY_UPDATE_INTERVAL = 1  # in minutes


@DataManager.register("activities", "removedDataCache", "lastUpdateTime")
class ActivityTracker(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        self._config: Configuration = bot.get_cog("Configuration")
        self._snapManager: SnapshotManager = bot.get_cog("SnapshotManager")
        self._memeberManager: MemberManager = bot.get_cog("MemberManager")
        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._serverListTracker = wynnAPI.serverList.get_tracker()

        self.activities = {}  # id: [actTotal, actCurr, isOnline, server]
        self.lastUpdateTime = None
        self.apiTimestamps = {}
        self.removedDataCache = {}
        self.lb = []
        self.currLb = []

        self.bot = bot

        self._snapManager.add("ActivityTracker", self)
        self._memeberManager.add_member_track_cb(self.on_member_track)
        self._memeberManager.add_member_un_track_cb(self.on_member_un_track)
    
    def __snap__(self):
        return self._make_activity_pages()
    
    def __loaded__(self):
        tracked = self._memeberManager.get_tracked_igns()
        trackedId = set(map(lambda ign: self._memeberManager.ignIdMap[ign], tracked))
        missingId = trackedId.difference(set(self.activities.keys()))
        for id_ in missingId:
            self.on_member_track(id_)

        self._activity_update.start()
    
    @tasks.loop(minutes=ACTIVITY_UPDATE_INTERVAL)
    async def _activity_update(self):        
        serverList = self._serverListTracker.getData()
        if not serverList:
            return
        
        tracked = self._memeberManager.get_tracked_igns()

        now = utcNow()
        if self.lastUpdateTime:
            interval = now - self.lastUpdateTime
        else:
            interval = timedelta(seconds=0)

        for server, players in serverList.items():
            for ign in players:
                if ign in tracked:

                    data = self.activities[self._memeberManager.ignIdMap[ign]]

                    if data[2]:
                        if not server.startswith("lobby"):
                            data[0] += interval
                        data[1] += interval
                    
                    data[2] = True
                    data[3] = server

                    tracked.remove(ign)
        
        for ign in tracked:
            data = self.activities[self._memeberManager.ignIdMap[ign]]
            data[1] = timedelta(seconds=0)
            data[2] = False
            data[3] = None
        
        self._update_lb()

        # print(utcNow() - now)
        self.lastUpdateTime = now
    
    @_activity_update.before_loop
    async def _before_activity_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting activity update loop")
    
    def _update_lb(self):
        sortKey = lambda id_: -1 * self.activities[id_][0]
        self.lb = sorted(list(self.activities.keys()), key=sortKey)
        sortKey = lambda id_: -1 * self.activities[id_][1]
        self.currLb = sorted(list(self.activities.keys()), key=sortKey)
    
    def on_member_track(self, id_):
        if id_ in self.removedDataCache:
            data = self.removedDataCache.pop(id_)
        else:
            data = [timedelta(seconds=0), timedelta(seconds=0), False, None]
        self.activities[id_] = data
        self._update_lb()
    
    def on_member_un_track(self, id_):
        self.removedDataCache[id_] = self.activities.pop(id_)
        self._update_lb()
    
    def biweekly_reset(self):
        Logger.bot.info("Reseting activities")
        dataList = list(self.activities.values()) + list(self.removedDataCache.values())
        for data in dataList:
            data[0] = timedelta(seconds=0)
    
    def _format_dt(self, dt: timedelta):
        days = dt.days
        seconds = trunc(dt.seconds) - 86400 * days
        hours = seconds // 3600
        minutes = seconds // 60 % 60
        seconds = seconds % 60

        return f"{days:02} {hours:02}:{minutes:02}:{seconds:02}"
    
    def _get_last_update_dt(self):
        dt = utcNow() - self.lastUpdateTime
        seconds = trunc(dt.seconds)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes} minutes {seconds} seconds ago"

    @parser("online")
    async def display_online(self, ctx: commands.Context):
        entries = []

        lb = {}
        maxIgnLen = 0
        maxServerLen = 0
        maxRankLen = 0
        for id_ in self.currLb:
            if self.activities[id_][2]:
                member = self._memeberManager.members[id_]
                [_, dt, _, server] = self.activities[id_]
                
                maxIgnLen = max(maxIgnLen, len(member.ign))
                maxServerLen = max(maxServerLen, len(server))
                maxRankLen = max(maxRankLen, len(member.rank))

                lb[member.ign] = (member.rank, server, self._format_dt(dt))
        if not lb:
            await ctx.send("`No member is online.`")
            return

        template = "{0:<%d} {1:<%d}  |  {2:<%d} {3}" % (maxRankLen, maxIgnLen, maxServerLen)

        for ign, (rank, server, dt) in lb.items():
            entries.append(template.format(rank, ign, server, dt))
        
        dt = self._get_last_update_dt()
        text = decorate_text("\n".join(entries), title="Online Members", lastUpdate=dt)
        await ctx.send(text)
    
    def _make_activity_pages(self):
        dt = self._get_last_update_dt()

        entries = []
        
        igns = map(lambda id_: self._memeberManager.members[id_].ign, self.lb)
        statSelector = lambda m: self._format_dt(self.activities[m.id][0])
        members = self._memeberManager.members

        entries = make_stat_entries(self.lb, igns, members, statSelector, strStat=True)
        pages = make_entry_pages(entries, title="Activities", lastUpdate=dt)

        return pages
    
    @parser("act", "-snap", isGroup=True)
    async def display_activity(self, ctx: commands.Context, snap):
        if snap:
            pages = await self._snapManager.get_snapshot_cmd(ctx, snap, 
                "ActivityTracker")
            if not pages:
                return
        else:
            pages = self._make_activity_pages()

        await PagedMessage(pages, ctx.channel).init()
    
    @parser("act reset", parent=display_activity)
    async def reset_activity(self, ctx: commands.Context):
        if not await self._config.perm_check(ctx, "user.dev"):
            return
        self.biweekly_reset()
        await ctx.message.add_reaction("✅")