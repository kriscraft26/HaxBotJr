from typing import Dict, List, Callable, Set

from discord import Member, Embed
from discord.ext import tasks, commands

from logger import Logger
from msgmaker import *
from pagedmessage import PagedMessage
from util.cmdutil import parser
from cog.wynnapi import WynnAPI
from cog.configuration import Configuration
from cog.datacog import DataCog


# TODO: add dMember field
class GuildMember:

    def __init__(self, dMember: Member):
        Logger.bot.info(f"Added {dMember}({dMember.nick}) as guild member")
        self.id: int = dMember.id

        seg = dMember.nick.split(" ")
        self.rank = " ".join(seg[:-1])
        self.ign: str = seg[-1]

        self.totalXp = -1
        self.accXp = 0

        self.warCount = 0
    
    def __repr__(self):
        s = "<GuildMember"
        properties = ["ign", "rank", "totalXp", "accXp", "warCount"]
        for p in properties:
            s += f" {p}={getattr(self, p)}"
        return s + ">"


IG_MEMBERS_UPDATE_INTERVAL = 3

@DataCog.register("members", "ignIdMap", "removedMembers", "accXpLb", 
                  "totalXpLb", "warCountLb")
class MemberManager(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.members: Dict[int, GuildMember] = {}
        self.ignIdMap: Dict[str, int] = {}

        self.removedMembers: Dict[int, GuildMember] = {}

        self.accXpLb: List[int] = []
        self.totalXpLb: List[int] = []
        self.warCountLb: List[int] = []

        self.hasInitMembersUpdate = False

        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._guildStatsTracker = wynnAPI.guildStats.get_tracker()
        self._igMembers: Set[str] = set()

        self._config: Configuration = bot.get_cog("Configuration")

    def __loaded__(self):
        self._ig_members_update.start()
    
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
            gMember = self._add_member(after)
            self._update_guild_info(gMember, after)
        elif isGMemberBefore and isGMemberAfter:
            self._update_guild_info(self.members[before.id], after)
    
    def _update_guild_info(self, gMember: GuildMember, dMember: Member):
        currRank = self._config.get_rank(dMember)[0]
        if gMember.rank != currRank:
            Logger.guild.info(f"{gMember.ign} rank change {gMember.rank} -> {currRank}")
            gMember.rank = currRank
            Logger.war.info(f"{gMember.ign} war count reset from {gMember.warCount}")
            gMember.warCount = 0
            self.rank_war_count(gMember.id)
        
        currIgn = dMember.nick.replace(currRank, "").strip()
        if gMember.ign != currIgn:
            Logger.guild.info(f"{gMember.ign} changed ign to {currIgn}")
            del self.ignIdMap[gMember.ign]
            self.ignIdMap[currIgn] = gMember.id
            gMember.ign = currIgn

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
        else:
            gMember = GuildMember(dMember)
        
        self.ignIdMap[gMember.ign] = id_
        self.members[id_] = gMember
        
        self.rank_acc_xp(id_)
        self.rank_total_xp(id_)
        self.rank_war_count(id_)

        return gMember
    
    def _remove_member(self, gMember: GuildMember):
        Logger.bot.info(f"removed guild member {gMember}")
        id_ = gMember.id

        del self.members[id_]
        del self.ignIdMap[gMember.ign]

        self.accXpLb.remove(id_)
        self.totalXpLb.remove(id_)
        self.warCountLb.remove(id_)

        self.removedMembers[id_] = gMember
    
    def clear_removed_members(self):
        Logger.bot.info(f"clearing removed members: {self.removedMembers}")
        self.removedMembers.clear()
    
    def _rank_member(self, id_: int, key: Callable[[GuildMember], bool],
                     lb: List[GuildMember]):
        gMember = self.members[id_]
        val = key(gMember)
        i = 0
        if id_ in lb:
            i = lb.index(id_)
            lb.remove(id_)

        while 0 <= i and i <= len(lb):
            leftDiff = 0 if i == 0 else key(self.members[lb[i - 1]]) - val
            rightDiff = 0 if i == len(lb) else val - key(self.members[lb[i]])
            if leftDiff < 0:
                i -= 1
                continue
            if rightDiff < 0:
                i += 1
                continue
            break
        
        lb.insert(i, id_)
    
    def rank_total_xp(self, id_: int):
        self._rank_member(id_, lambda m: m.totalXp, self.totalXpLb)
    
    def rank_acc_xp(self, id_: int):
        self._rank_member(id_, lambda m: m.accXp, self.accXpLb)
    
    def rank_war_count(self, id_: int):
        self._rank_member(id_, lambda m: m.warCount, self.warCountLb)
    
    def get_igns_set(self) -> Set[str]:
        return set(self.ignIdMap.keys())
    
    def get_member_by_ign(self, ign: str) -> GuildMember:
        return self.members[self.ignIdMap[ign]]

    @parser("stats", "ign")
    async def display_stats(self, ctx: commands.Context, ign: str):
        if ign not in self.ignIdMap:
            await ctx.send(embed=make_alert(f"{ign} is not in the guild."))
            return
        
        gMember = self.get_member_by_ign(ign)
        dMember: Member = self._config.guild.get_member(gMember.id)

        maxStatLen = len(str(max([gMember.accXp, gMember.totalXp, gMember.warCount])))

        accXpRank = self.accXpLb.index(gMember.id) + 1
        totalXpRank = self.totalXpLb.index(gMember.id) + 1
        warCountRank = self.warCountLb.index(gMember.id) + 1

        maxRankLen = len(str(max([accXpRank, totalXpRank, warCountRank])))

        separator = "-" * (20 + maxStatLen + maxRankLen) + "\n"

        text = ""
        text += f"Total XP:        %{maxStatLen}d (#{totalXpRank})\n" % gMember.totalXp
        text += f"Accumulated XP:  %{maxStatLen}d (#{accXpRank})\n" % gMember.accXp
        text += separator
        text += f"War Count:       %{maxStatLen}d (#{warCountRank})\n" % gMember.warCount
        text += separator
        text += f"discord {dMember.name}#{dMember.discriminator}"

        title = f"[{gMember.rank}] {gMember.ign}"

        text = decorate_text(text, title=title)
        await ctx.send(text)
    
    @parser("members", ["removed"])
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
        def statSelector(m):
            dMember = self._config.guild.get_member(m.id)
            return f"{dMember.name}#{dMember.discriminator}"
        
        pages = make_entry_pages(make_stat_entries(lb, igns, members, statSelector),
            title=title)
        await PagedMessage(pages, ctx.channel).init()