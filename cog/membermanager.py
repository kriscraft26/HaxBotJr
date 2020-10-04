from typing import Dict, List, Callable, Set

from discord import Member, Embed
from discord.ext import tasks, commands

from logger import Logger
from msgmaker import *
from pagedmessage import PagedMessage
from statistic import Statistic, AccumulatedStatistic, LeaderBoard
from util.cmdutil import parser
from cog.wynnapi import WynnAPI
from cog.configuration import Configuration
from cog.datamanager import DataManager


class GuildMember:

    def __init__(self, dMember: Member, rank: str, vRank: str):
        Logger.bot.info(f"Added {dMember}({dMember.nick}) as guild member")
        self.id: int = dMember.id
        self.discord = f"{dMember.name}#{dMember.discriminator}"

        seg = dMember.nick.split(" ")
        self.rank = rank
        self.vRank = None
        self.ign: str = seg[-1]

        self.xp = AccumulatedStatistic("xp", self.id)
        self.warCount = Statistic("warCount", self.id, initVal=0)
        self.emerald = AccumulatedStatistic("emerald", self.id)
    
    def __repr__(self):
        s = "<GuildMember"
        properties = ["ign", "discord", "rank", "vRank", "xp", "warCount", "emerald"]
        for p in properties:
            if hasattr(self, p):
                s += f" {p}={getattr(self, p)}"
        return s + ">"


IG_MEMBERS_UPDATE_INTERVAL = 3

@DataManager.register("members", "ignIdMap", "removedMembers")
class MemberManager(commands.Cog):

    def __init__(self, bot: commands.Bot):
        LeaderBoard.set_member_manager(self)

        self.members: Dict[int, GuildMember] = {}
        self.ignIdMap: Dict[str, int] = {}

        self.removedMembers: Dict[int, GuildMember] = {}

        self.hasInitMembersUpdate = False

        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._guildStatsTracker = wynnAPI.guildStats.get_tracker()
        self._igMembers: Set[str] = set()

        self._config: Configuration = bot.get_cog("Configuration")

    def __loaded__(self):
        self._ig_members_update.start()

        allMembers = list(self.members.values()) + list(self.removedMembers.values())
        if allMembers:
            sampleMember = allMembers[0]
            if not hasattr(sampleMember, "vRank"):
                Logger.bot.debug("detected outdated GuildMember objects, updating...")
                for member in allMembers:
                    dMember = self._config.guild.get_member(member.id)
                    if dMember:
                        rank = self._config.get_rank(dMember)
                        if rank:
                            vRank = rank[1]
                            member.vRank = vRank
                            if vRank:
                                Logger.bot.debug(f"-> {member}")
    
    @tasks.loop(seconds=IG_MEMBERS_UPDATE_INTERVAL)
    async def _ig_members_update(self):
        guildStats = self._guildStatsTracker.getData()
        if not guildStats:
            return
        
        prevIgMembers = self._igMembers
        self._igMembers = {m["name"] for m in guildStats["members"]}

        if not self.hasInitMembersUpdate:
            self._bulk_update_members()
            self.hasInitMembersUpdate = True
        else:

            joined = self._igMembers.difference(prevIgMembers)
            if joined:
                guildDMembers = self._config.get_all_guild_members(self._igMembers)
                guildDMembers = {m.nick.split(" ")[-1]: m for m in guildDMembers}

                validIgns = joined.intersection(set(guildDMembers.keys()))
                for ign in validIgns:
                    self._add_member(guildDMembers[ign])
                
            removed = prevIgMembers.difference(self._igMembers)
            for ign in removed:
                if ign in self.ignIdMap:
                    self._remove_member(self.get_member_by_ign(ign))
    
    @_ig_members_update.before_loop
    async def _before_ig_members_update(self):
        Logger.bot.debug("Starting in-game members update loop")
    
    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        isGMemberBefore = self._config.is_guild_member(before, self._igMembers)
        isGMemberAfter = self._config.is_guild_member(after, self._igMembers)

        if isGMemberBefore and not isGMemberAfter:
            self._remove_member(self.members[after.id])
        elif not isGMemberBefore and isGMemberAfter:
            self._update_guild_info(self._add_member(after), after)
        elif isGMemberBefore and isGMemberAfter:
            self._update_guild_info(self.members[before.id], after)
    
    def _update_guild_info(self, gMember: GuildMember, dMember: Member):
        currRank, vRank = self._config.get_rank(dMember)
        if gMember.rank != currRank:
            Logger.guild.info(f"{gMember.ign} rank change {gMember.rank} -> {currRank}")
            gMember.rank = currRank
            Logger.war.info(f"{gMember.ign} war count reset from {gMember.warCount}")
            gMember.warCount.val = 0
        if gMember.vRank != vRank:
            Logger.guild.info(f"{gMember.ign} vRank change {gMember.vRank} -> {vRank}")
            gMember.vRank = vRank
        
        currIgn = dMember.nick.split(" ")[-1]
        if gMember.ign != currIgn:
            Logger.guild.info(f"{gMember.ign} changed ign to {currIgn}")
            del self.ignIdMap[gMember.ign]
            self.ignIdMap[currIgn] = gMember.id
            gMember.ign = currIgn
        
        gMember.discord = f"{dMember.name}#{dMember.discriminator}"

    def _bulk_update_members(self):
        currGuildDMembers = self._config.get_all_guild_members(self._igMembers)
        currGuildDMembers = {m.id: m for m in currGuildDMembers}

        currGuildMemberIds = set(currGuildDMembers.keys())
        prevGuildMemberIds = set(self.members.keys())

        joined = currGuildMemberIds.difference(prevGuildMemberIds)
        for joinedMemberId in joined:
            self._add_member(currGuildDMembers[joinedMemberId])
        
        removed = prevGuildMemberIds.difference(currGuildMemberIds)
        for removedMemberId in removed:
            self._remove_member(self.members[removedMemberId])
        
        changed = prevGuildMemberIds.intersection(currGuildMemberIds)
        for changedMemberId in changed:
            gMember = self.members[changedMemberId]
            dMember = currGuildDMembers[changedMemberId]
            self._update_guild_info(gMember, dMember)
    
    def _add_member(self, dMember: Member):
        id_ = dMember.id
        if id_ in self.removedMembers:
            gMember = self.removedMembers[id_]
            Logger.bot.info(f"Undo removal of guild member {gMember}")
            del self.removedMembers[id_]

            LeaderBoard.get_lb("xpAcc").add_stat(gMember.xp.acc)
            LeaderBoard.get_lb("xpTotal").add_stat(gMember.xp.total)
            LeaderBoard.get_lb("warCount").add_stat(gMember.warCount)
            LeaderBoard.get_lb("emeraldAcc").add_stat(gMember.emerald.acc)
            LeaderBoard.get_lb("emeraldTotal").add_stat(gMember.emerald.total)
        else:
            gMember = GuildMember(dMember, *(self._config.get_rank(dMember)))
        
        self.ignIdMap[gMember.ign] = id_
        self.members[id_] = gMember
        
        return gMember
    
    def _remove_member(self, gMember: GuildMember):
        Logger.bot.info(f"removed guild member {gMember}")
        id_ = gMember.id

        del self.members[id_]
        del self.ignIdMap[gMember.ign]

        LeaderBoard.get_lb("xpAcc").remove_stat(gMember.xp.acc)
        LeaderBoard.get_lb("xpTotal").remove_stat(gMember.xp.total)
        LeaderBoard.get_lb("warCount").remove_stat(gMember.warCount)
        LeaderBoard.get_lb("emeraldAcc").remove_stat(gMember.emerald.acc)
        LeaderBoard.get_lb("emeraldTotal").remove_stat(gMember.emerald.total)

        self.removedMembers[id_] = gMember
    
    def clear_removed_members(self):
        Logger.bot.info(f"clearing removed members: {self.removedMembers}")
        self.removedMembers.clear()
    
    def get_igns_set(self) -> Set[str]:
        return set(self.ignIdMap.keys())
    
    def get_member_by_ign(self, ign: str) -> GuildMember:
        return self.members[self.ignIdMap[ign]]

    @parser("stats", "ign")
    async def display_stats(self, ctx: commands.Context, ign: str):
        if ign not in self.ignIdMap:
            await ctx.send(embed=make_alert(f"{ign} is not in the guild."))
            return
        
        m = self.get_member_by_ign(ign)

        maxStatLen = len(str(max([m.xp.acc.val, m.xp.total.val, m.warCount.val, 
                                  m.emerald.total.val, m.emerald.acc.val])))

        accXpRank = LeaderBoard.get_lb("xpAcc").get_rank(m.id) + 1
        totalXpRank = LeaderBoard.get_lb("xpTotal").get_rank(m.id) + 1
        warCountRank = LeaderBoard.get_lb("warCount").get_rank(m.id) + 1
        accEmRank = LeaderBoard.get_lb("emeraldAcc").get_rank(m.id) + 1
        totalEmRank = LeaderBoard.get_lb("emeraldTotal").get_rank(m.id) + 1

        maxRankLen = len(str(max([accXpRank, totalXpRank, warCountRank, 
                                  accEmRank, totalEmRank])))

        separator = "-" * (21 + maxStatLen + maxRankLen) + "\n"

        text = ""
        text += f"Total XP:        %{maxStatLen}d (#{totalXpRank})\n" % m.xp.total.val
        text += f"Accumulated XP:  %{maxStatLen}d (#{accXpRank})\n" % m.xp.acc.val
        text += separator
        text += f"Total Em:        %{maxStatLen}d (#{totalEmRank})\n" % m.emerald.total.val
        text += f"Accumulated Em   %{maxStatLen}d (#{accEmRank})\n" % m.emerald.acc.val
        text += separator
        text += f"War Count:       %{maxStatLen}d (#{warCountRank})\n" % m.warCount.val
        text += separator
        text += f"discord {m.discord}"

        vRank = f"[{m.vRank}] " if m.vRank else ""
        title = f"[{m.rank}] {vRank}{m.ign}"

        text = decorate_text(text, title=title)
        await ctx.send(text)
    
    @parser("members", ["removed"], isGroup=True)
    async def display_members(self, ctx: commands.Context, removed):
        if removed:
            lb = self.removedMembers.keys()
            igns = list(map(lambda m: m.ign, self.removedMembers.values()))
            members = self.removedMembers
        else:
            lb = self.members.keys()
            igns = self.ignIdMap.keys()
            members = self.members
        title = ("Removed " if removed else "") + "Guild Members"
        statSelector = lambda m: m.discord
        
        pages = make_entry_pages(make_stat_entries(lb, igns, members, statSelector),
            title=title)
        await PagedMessage(pages, ctx.channel).init()
    
    @parser("members missing", parent=display_members)
    async def display_missing_members(self, ctx: commands.Context):
        trackedIgns = set(self.ignIdMap.keys())
        missingIgns = self._igMembers.difference(trackedIgns)
        await ctx.send(", ".join(missingIgns))

    @parser("members fix", parent=display_members)
    async def fix_members(self, ctx):
        if not await self._config.perm_check(ctx, "user.dev"):
            return
        for member in self.members.values():
            if member.rank == "Commander":
                member.rank = "Cosmonaut"