from typing import Set, Dict, List

from discord.ext import commands, tasks

from logger import Logger
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


WAR_SERVERS_UPDATE_INTERVAL = 3

@DataManager.register("currentWar")
class WarTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.prevInitdWars = []
        self.currentWar = None
        self.hasInitUpdated = False

        self._serverListReceiver = WynnAPI.serverList.create_receiver()
        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._update.start()
        self._snapshotManager.add("WarTracker", self)
    
    async def __snap__(self):
        return (
            await self.make_war_lb_pages(False),
            await self.make_war_lb_pages(True)
        )
    
    @tasks.loop(seconds=WAR_SERVERS_UPDATE_INTERVAL)
    async def _update(self):
        serverList = self._serverListReceiver.getData()
        if not serverList:
            return
        
        if not self.hasInitUpdated and not self.currentWar:
            await self._init_update(serverList)
            self.hasInitUpdated = True
        
        if self.currentWar:
            if self.currentWar not in serverList:
                Logger.war.info(f"War at {self.currentWar} ended")
                self.currentWar = None
                self.prevInitdWars = []
            else:
                await self.bot.get_cog("ClaimTracker").dismiss_alert()
        else:
            for war in self.prevInitdWars:
                if war not in serverList:
                    continue
                players = serverList[war]
                if not players:
                    continue
                targetPlayers = set(filter(GuildMember.is_ign_active, players))
                if targetPlayers:
                    Logger.war.info(f"{war} started with {targetPlayers}")
                    for ign in targetPlayers:
                        await Statistic.stats[GuildMember.ignIdMap[ign]].increment_war()
                    self.currentWar = war
                    break
        
            initWarCheck = lambda w: w.startswith("WAR") and not serverList[w]
            self.prevInitdWars = filter(initWarCheck, serverList.keys())

    async def _init_update(self, serverList: dict):
        for war, players in serverList.items():
            if war.startswith("WAR") and players:
                targetPlayers = set(filter(GuildMember.is_ign_active, players))
                if targetPlayers:
                    Logger.war.info(f"{war} is currently on going with {targetPlayers}")
                    for ign in targetPlayers:
                        await Statistic.stats[GuildMember.ignIdMap[ign]].increment_war()
                    self.currentWar = war
                    return
    
    @_update.before_loop
    async def _before_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting war tracking loop")
    
    async def make_war_lb_pages(self, total):
        if total:
            lb = Statistic.warTotalLb
            field = "total"
            titlePrefix = "Total "
        else:
            lb = Statistic.warLb
            field = "biweek"
            titlePrefix = "Bi-Weekly "

        valGetter = lambda m: Statistic.stats[m.id].war[field]
        filter_ = lambda m: m.status != GuildMember.REMOVED
        
        return make_entry_pages(await make_stat_entries(
            valGetter, filter_=filter_, lb=lb),
            title=titlePrefix + "War Leader Board", endpoint=WynnAPI.serverList)

    @parser("wc", ["total"], "-snap", isGroup=True)
    async def display_war_count_lb(self, ctx: commands.Context, total, snap):
        if snap:
            pages = await self._snapshotManager.get_snapshot_cmd(ctx, snap, 
                "WarTracker", total)
            if not pages:
                return
        else:
            pages = await self.make_war_lb_pages(total)

        rMsg = RMessage(await ctx.send(pages[0]))
        await rMsg.add_pages(pages)
    
    @parser("wc fix", parent=display_war_count_lb)
    async def fix_wc(self, ctx: commands.Context):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return