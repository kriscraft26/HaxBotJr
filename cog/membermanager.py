from typing import Dict, List, Callable, Set

from discord import Member, Embed, User
from discord.ext import tasks, commands

from logger import Logger
from msgmaker import *
from pagedmessage import PagedMessage
from leaderboard import LeaderBoard
from util.cmdutil import parser
from cog.wynnapi import WynnAPI
from cog.configuration import Configuration
from cog.datamanager import DataManager


class GuildMember:

    def __init__(self, dMember: Member, rank: str, vRank: str):
        Logger.bot.info(f"Added {dMember}({dMember.nick}) as guild member")
        self.id: int = dMember.id
        self.discord = str(dMember)

        seg = dMember.nick.split(" ")
        self.rank = rank
        self.vRank = None
        self.ign: str = seg[-1]

    def __repr__(self):
        s = "<GuildMember"
        properties = ["ign", "discord", "rank", "vRank"]
        for p in properties:
            if hasattr(self, p):
                s += f" {p}={getattr(self, p)}"
        return s + ">"


IG_MEMBERS_UPDATE_INTERVAL = 3

@DataManager.register("members", "ignIdMap", "idleMembers", 
                      mapper={"removedMembers": "idleMembers"})
class MemberManager(commands.Cog):

    def __init__(self, bot: commands.Bot):
        LeaderBoard.set_member_manager(self)

        self.members: Dict[int, GuildMember] = {}
        self.ignIdMap: Dict[str, int] = {}

        self.idleMembers: Set[int] = set()

        self.hasInitMembersUpdate = False

        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._guildStatsTracker = wynnAPI.guildStats.get_tracker()
        self._igMembers: Set[str] = set()

        self._config: Configuration = bot.get_cog("Configuration")

    def __loaded__(self):
        self._ig_members_update.start()

        allMembers = list(self.members.values())
        if allMembers:
            sampleMember = allMembers[0]
            if hasattr(sampleMember, "xp"):
                Logger.bot.debug("detected outdated GuildMember objects, updating...")
                for member in allMembers:
                    del member.xp
                    del member.emerald
                    del member.warCount
                    Logger.bot.debug(f"-> {member}")
        
        if type(self.idleMembers) == dict:
            Logger.bot.debug("detected outdated idleMembers, updating...")
            updated = set()
            for id_, member in self.idleMembers.items():
                dMember = self._config.guild.get_member(id_)
                if dMember and self._config.is_of_group("guild", dMember):
                    updated.add(id_)
                    self.members[id_] = member
                    self.ignIdMap[member.ign] = id_
                    LeaderBoard.get_lb("xpTotal").set_stat(id_, member.xp.total.val)
                    LeaderBoard.get_lb("xpAcc").set_stat(id_, member.xp.acc.val)
                    LeaderBoard.get_lb("warCount").set_stat(id_, member.warCount.val)
                    LeaderBoard.get_lb("emeraldTotal").set_stat(id_, member.emerald.total.val)
                    LeaderBoard.get_lb("emeraldAcc").set_stat(id_, member.emerald.acc.val)
                    del member.xp
                    del member.emerald
                    del member.warCount
                    Logger.bot.debug(f"-> {member}")
            self.idleMembers = updated
            Logger.bot.debug(f"-> {self.idleMembers}")
    
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
            trackedIgns = self.get_igns_set()

            joined = self._igMembers.difference(prevIgMembers).intersection(trackedIgns)
            joinedIds = {self.ignIdMap[ign] for ign in joined}
            self.idleMembers = self.idleMembers.difference(joinedIds)
            if joined:
                Logger.bot.info(f"{joined} status set to active")
            
            removed = prevIgMembers.difference(self._igMembers).intersection(trackedIgns)
            removedIds = {self.ignIdMap[ign] for ign in removed}
            self.idleMembers = self.idleMembers.union(removedIds)
            if removed:
                Logger.bot.info(f"{removed} status set to idle")
    
    @_ig_members_update.before_loop
    async def _before_ig_members_update(self):
        Logger.bot.debug("Starting in-game members update loop")
    
    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        isGMemberBefore = before.id in self.members
        isGMemberAfter = self._config.is_of_group("guild", after)

        if isGMemberBefore and not isGMemberAfter:
            self._remove_member(self.members[after.id])
        elif not isGMemberBefore and isGMemberAfter:
            self._update_guild_info(self._add_member(after), after)
        elif isGMemberBefore and isGMemberAfter:
            self._update_guild_info(self.members[before.id], after)
    
    @commands.Cog.listener()
    async def on_member_remove(self, dMember: Member):
        if dMember.id in self.members:
            self._remove_member(self.members[dMember.id])

    @commands.Cog.listener()
    async def on_user_update(self, before: User, after: User):
        if before.id in self.members:
            member = self.members[before.id]
            Logger.bot.info(f"{member.ign} discord change {member.discord} -> {after}")
            member.discord = str(after)
    
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
        currGuildDMembers = self._config.get_all_guild_members()
        currGuildDMembers = {m.id: m for m in currGuildDMembers}

        currGuildMemberIds = set(currGuildDMembers.keys())
        prevGuildMemberIds = set(self.members.keys())

        joined = currGuildMemberIds.difference(prevGuildMemberIds)
        for id_ in joined:
            dMember = currGuildDMembers[id_]
            self._add_member(dMember)

            ign = dMember.nick.split(" ")[-1]
            if ign not in self._igMembers:
                self.idleMembers.add(id_)
                Logger.bot.info(f"{ign} status set to idle")
        
        removed = prevGuildMemberIds.difference(currGuildMemberIds)
        for id_ in removed:
            self._remove_member(self.members[id_])
        
        changed = prevGuildMemberIds.intersection(currGuildMemberIds)
        for id_ in changed:
            gMember = self.members[id_]
            dMember = currGuildDMembers[id_]
            self._update_guild_info(gMember, dMember)

            ign = dMember.nick.split(" ")[-1]
            if ign in self._igMembers and id_ in self.idleMembers:
                self.idleMembers.remove(id_)
                Logger.bot.info(f"{ign} status set to active")
            elif ign not in self._igMembers and id_ not in self.idleMembers:
                self.idleMembers.add(id_)
                Logger.bot.info(f"{ign} status set to idle")
    
    def _add_member(self, dMember: Member):
        gMember = GuildMember(dMember, *(self._config.get_rank(dMember)))
        
        id_ = dMember.id
        self.ignIdMap[gMember.ign] = id_
        self.members[id_] = gMember
        
        return gMember
    
    def _remove_member(self, gMember: GuildMember):
        Logger.bot.info(f"removed guild member {gMember}")
        id_ = gMember.id

        del self.members[id_]
        del self.ignIdMap[gMember.ign]
        id_ in self.idleMembers and self.idleMembers.remove(id_)

        LeaderBoard.remove_stats(id_)
    
    def get_igns_set(self) -> Set[str]:
        return set(self.ignIdMap.keys())
    
    def get_tracked_igns(self) -> Set[str]:
        idle_igns = {self.members[id_].ign for id_ in self.idleMembers}
        return self.get_igns_set().difference(idle_igns)
    
    def get_member_by_ign(self, ign: str) -> GuildMember:
        return self.members[self.ignIdMap[ign]]

    @parser("stats", "ign")
    async def display_stats(self, ctx: commands.Context, ign: str):
        if ign not in self.ignIdMap:
            await ctx.send(embed=make_alert(f"{ign} is not in the guild."))
            return
        
        m = self.get_member_by_ign(ign)

        stats = LeaderBoard.get_stats(m.id)
        ranks = LeaderBoard.get_ranks(m.id)
        statInfo = {name: (stat, ranks[name]) for name, stat in stats.items()}

        maxStatLen = max(map(lambda n: len(str(n)), stats.values()))
        maxRankLen = max(map(lambda n: len(str(n)), ranks.values()))

        separator = "-" * (21 + maxStatLen + maxRankLen) + "\n"
        statDisplay = f"%{maxStatLen}d (#%d)\n"
        idleStatus = "-- NOT IN GUILD" if m.id in self.idleMembers else ""

        text = ""
        text += f"Total XP:        {statDisplay}" % statInfo["xpTotal"]
        text += f"Accumulated XP:  {statDisplay}" % statInfo["xpAcc"]
        text += separator
        text += f"Total Em:        {statDisplay}" % statInfo["emeraldTotal"]
        text += f"Accumulated Em   {statDisplay}" % statInfo["emeraldAcc"]
        text += separator
        text += f"War Count:       {statDisplay}" % statInfo["warCount"]
        text += "\n"
        text += f"discord {m.discord} {idleStatus}"

        vRank = f"<{m.vRank}> " if m.vRank else ""
        title = f"[{m.rank}] {vRank}{m.ign}"

        text = decorate_text(text, title=title)
        await ctx.send(text)
    
    @parser("members", ["idle"], isGroup=True)
    async def display_members(self, ctx: commands.Context, idle):
        lb = self.idleMembers if idle else self.members.keys()
        igns = self.ignIdMap.keys()
        members = self.members
        title = ("Idle " if idle else "") + "Guild Members"
        statSelector = lambda m: m.discord
        
        pages = make_entry_pages(make_stat_entries(lb, igns, members, statSelector),
            title=title)
        await PagedMessage(pages, ctx.channel).init()
    
    @parser("members missing", parent=display_members)
    async def display_missing_members(self, ctx: commands.Context):
        trackedIgns = self.get_igns_set()
        missingIgns = self._igMembers.difference(trackedIgns)
        await ctx.send(", ".join(missingIgns))

    @parser("members fix", parent=display_members)
    async def fix_members(self, ctx):
        if not await self._config.perm_check(ctx, "user.dev"):
            return
        for member in self.members.values():
            if member.rank == "Commander":
                member.rank = "Cosmonaut"