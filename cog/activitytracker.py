from datetime import timedelta
from asyncio import sleep
from math import trunc

from discord.ext import commands, tasks

from logger import Logger
from event import Event
from wynnapi import WynnAPI
from msgmaker import *
from reactablemessage import RMessage
from util.cmdutil import parser
from util.timeutil import now as utcNow
from util.discordutil import Discord
from state.config import Config
from state.guildmember import GuildMember
from cog.datamanager import DataManager
from cog.snapshotmanager import SnapshotManager


ACTIVITY_UPDATE_INTERVAL = 1  # in minutes


@DataManager.register("lastUpdateTime")
class ActivityTracker(commands.Cog):
    
    def __init__(self, bot: commands.Bot):
        self._snapManager: SnapshotManager = bot.get_cog("SnapshotManager")
        self._serverListTracker = WynnAPI.serverList.get_tracker()

        self.lastUpdateTime = utcNow()
        self.bot = bot

        self._snapManager.add("ActivityTracker", self)
        
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
        with GuildMember.members:
            tracked = {m.ign async for m in GuildMember.members.avalues(filter_)}

        now = utcNow()
        if self.lastUpdateTime:
            interval = now - self.lastUpdateTime
        else:
            interval = timedelta(seconds=0)

        for server, players in serverList.items():
            for ign in players:
                if ign in tracked:

                    stat: Statistic = Statistic.stats[GuildMember.ignIdMap[ign]]

                    if stat.world and not server.startswith("lobby"):
                            await stat.accumulate_online_time(interval)
                    
                    await stat.update_world(server)
                    tracked.remove(ign)
        
        for ign in tracked:
            await Statistic.stats[GuildMember.ignIdMap[ign]].update_world(None)
        
        self.lastUpdateTime = now
    
    @_activity_update.before_loop
    async def _before_activity_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting activity update loop")
    
    def _get_last_update_dt(self):
        dt = utcNow() - self.lastUpdateTime
        return f"{trunc(dt.seconds)} seconds ago"

    @parser("online")
    async def display_online(self, ctx: commands.Context):
        valGetter = lambda m: format_act_dt((s := Statistic.stats[m.id]).onlineTime["curr"]) \
            + " " + s.world
        filter_ = lambda m: Statistic.stats[m.id].world
        text = decorate_text("\n".join(await make_stat_entries(
            valGetter, group=False, filter_=filter_, rank=False, lb=Statistic.onlineTimeLb)),
            title="Online Members", lastUpdate=self._get_last_update_dt())
        await ctx.send(text)
    
    async def _make_activity_pages(self):
        valGetter = lambda m: format_act_dt(Statistic.stats[m.id].onlineTime["biweek"])
        pages = make_entry_pages(await make_stat_entries(
            valGetter, group=False, lb=Statistic.onlineTimeBwLb), 
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

        rMsg = RMessage(await ctx.send(pages[0]))
        await rMsg.add_pages(pages)
    
    @parser("act reset", parent=display_activity)
    async def reset_activity(self, ctx: commands.Context):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return
        self.biweekly_reset()
        await ctx.message.add_reaction("✅")