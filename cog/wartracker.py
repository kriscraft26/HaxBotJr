from typing import Set, Dict, List

from discord.ext import commands, tasks

from logger import Logger
from msgmaker import *
from leaderboard import LeaderBoard
from reactablemessage import PagedMessage
from util.cmdutil import parser
from cog.datamanager import DataManager
from cog.wynnapi import WynnAPI
from cog.membermanager import MemberManager


WAR_SERVERS_UPDATE_INTERVAL = 3

@DataManager.register("currentWar")
class WarTracker(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.prevInitdWars = []
        self.currentWar = None
        self.hasInitUpdated = False

        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._serverListTracker = wynnAPI.serverList.get_tracker()
        self._memberManager: MemberManager = bot.get_cog("MemberManager")

        self._lb: LeaderBoard = LeaderBoard.get_lb("warCount")

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
            trackedIgns = self._memberManager.get_tracked_igns()
            for war in self.prevInitdWars:
                if war not in serverList:
                    continue
                players = serverList[war]
                if not players:
                    continue
                targetPlayers = set(players).intersection(trackedIgns)
                if targetPlayers:
                    Logger.war.info(f"{war} started with {targetPlayers}")
                    for ign in targetPlayers:
                        self._incrememt_war_count(ign)
                    self.currentWar = war
                    break
        
            initWarCheck = lambda w: w.startswith("WAR") and not serverList[w]
            self.prevInitdWars = filter(initWarCheck, serverList.keys())

    def _init_update(self, serverList: dict):
        trackedIgns = self._memberManager.get_tracked_igns()
        for war, players in serverList.items():
            if war.startswith("WAR") and players:
                targetPlayers = set(players).intersection(trackedIgns)
                if targetPlayers:
                    Logger.war.info(f"{war} is currently on going with {targetPlayers}")
                    for ign in targetPlayers:
                        self._incrememt_war_count(ign)
                    self.currentWar = war
                    return
    
    def _incrememt_war_count(self, ign: str):
        id_ = self._memberManager.ignIdMap[ign]
        prevWc = self._lb.get_stat(id_)
        self._lb.set_stat(id_, prevWc + 1)
    
    @_update.before_loop
    async def _before_update(self):
        Logger.bot.debug("Starting war tracking loop")

    @parser("wc", ["acc"], ["bw"])
    async def display_war_count_lb(self, ctx: commands.Context, acc, bw):
        pages = self._lb.create_pages(acc, bw,
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