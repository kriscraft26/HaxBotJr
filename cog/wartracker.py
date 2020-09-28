from typing import Set, Dict, List

from discord.ext import commands, tasks

from logger import Logger
from msgmaker import *
from pagedmessage import PagedMessage
from util.cmdutil import parser
from cog.datacog import DataCog
from cog.wynnapi import WynnAPI
from cog.membermanager import MemberManager


WAR_SERVERS_UPDATE_INTERVAL = 3

@DataCog.register("currentWar")
class WarTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.prevInitdWars = []
        self.currentWar = None
        self.hasInitUpdated = False

        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._serverListTracker = wynnAPI.serverList.get_tracker()

        self._memberManager: MemberManager = bot.get_cog("MemberManager")

        self._update.start()
    
    @tasks.loop(seconds=WAR_SERVERS_UPDATE_INTERVAL)
    async def _update(self):
        serverList = self._serverListTracker.getData()
        if not serverList:
            return
        
        if not self.hasInitUpdated and not self.currentWar:
            self._init_update(serverList)
            self.hasInitUpdated = True
        
        if self.currentWar:
            if self.currentWar not in serverList:
                Logger.war.info(f"War at {self.currentWar} ended")
                self.currentWar = None
                self.prevInitdWars = []
        else:
            for war in self.prevInitdWars:
                if war not in serverList:
                    continue
                players = serverList[war]
                if not players:
                    continue
                targetPlayers = set(players).intersection(self._memberManager.get_igns_set())
                if targetPlayers:
                    Logger.war.info(f"{war} started with {targetPlayers}")
                    for ign in targetPlayers:
                        self._incrememt_war_count(ign)
                    self.currentWar = war
                    break
        
            initWarCheck = lambda w: w.startswith("WAR") and not serverList[w]
            self.prevInitdWars = filter(initWarCheck, serverList.keys())

    def _init_update(self, serverList: dict):
        for war, players in serverList.items():
            if war.startswith("WAR") and players:
                targetPlayers = set(players).intersection(self._memberManager.get_igns_set())
                if targetPlayers:
                    Logger.war.info(f"{war} is currently on going with {targetPlayers}")
                    for ign in targetPlayers:
                        self._incrememt_war_count(ign)
                    self.currentWar = war
                    return
    
    def _incrememt_war_count(self, ign: str):
        member = self._memberManager.get_member_by_ign(ign)
        Logger.war.info(f"{ign} warCount +1 from {member.warCount}")
        member.warCount += 1
        self._memberManager.rank_war_count(member.id)
    
    @_update.before_loop
    async def _before_update(self):
        Logger.bot.debug("Starting war tracking loop")
    
    def reset_war_count(self):
        Logger.bot.info("resetting all accumulated war counts")
        for member in self._memberManager.members.values():
            member.warCount = 0

    @parser("wc")
    async def display_war_count_lb(self, ctx: commands.Context):
        lb = self._memberManager.warCountLb
        igns = self._memberManager.ignIdMap.keys()
        members = self._memberManager.members
        statSelector = lambda m: m.warCount
        title = "War Count Leader Board"

        pages = make_entry_pages(make_stat_entries(lb, igns, members, statSelector), 
            title="War Count Leader Board", api=self._serverListTracker)
        await PagedMessage(pages, ctx.channel).init()


    # code for update loop that tracks all wars

    # @tasks.loop(seconds=WarTracker.WAR_SERVERS_UPDATE_INTERVAL)
    # def update(self):
    #     serverList = self._serverListTracker.getData()
    #     if not serverList:
    #         return

    #     warServers = dict(filter(lambda w: w[0].startswith("WAR"), serverList.items()))
    #     recWars = set(self.wars.keys())
    #     currWars = set(warServers.keys())


    #     initialized = currWars.difference(self.prevWars)
    #     for war in initialized:
    #         if not serverList[war]:
    #             self.wars[war] = None
        
    #     inbat = recWars.intersection(currWars)
    #     for war in inbat:
    #         prevPlayers = self.wars[war]
    #         currPlayers = warServers[war]
    #         # if the war stated
    #         if not prevPlayers and currPlayers:
    #             # if the war is started by our guild
    #             if set(currPlayers).intersection(set(self._memberManager.ignIdMap.keys())):
    #                 WarTracker.wars[war] = (currPlayers, [])
    #         # if player exited from war
    #         if prevPlayers and currPlayers and prevPlayers[0] != currPlayers:
    #             exitedPlayers = set(prevPlayers[0]).difference(set(currPlayers))
    #             WarTracker.wars[war] = (currPlayers, list(exitedPlayers))

    #     ended = recWars.difference(currWars)
    #     for war in ended:
    #         data = WarTracker.wars[war]
    #         del WarTracker.wars[war]
    #         data and WarTracker.endCallback and WarTracker.endCallback(war, *data)
        
    #     WarTracker.prevWars = currWars