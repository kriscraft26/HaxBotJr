from typing import Dict, List, Callable, Set

from discord import Member, Embed, User
from discord.ext import tasks, commands

from logger import Logger
from msgmaker import *
from reactablemessage import PagedMessage
from leaderboard import LeaderBoard
from util.cmdutil import parser
from cog.wynnapi import WynnAPI
from cog.configuration import Configuration
from cog.datamanager import DataManager
from cog.snapshotmanager import SnapshotManager


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
MEMBER_DELETION_INTERVAL = 10  # in minutes


@DataManager.register("members", "ignIdMap", "idleMembers", 
                      "_deletionQueue", "_removedMembers")
class MemberManager(commands.Cog):

    def __init__(self, bot: commands.Bot):
        LeaderBoard.set_member_manager(self)

        self.members: Dict[int, GuildMember] = {}
        self.ignIdMap: Dict[str, int] = {}

        self.idleMembers: Set[int] = set()

        self._deletionQueue: List[int] = []
        self._removedMembers = {}

        self.hasInitMembersUpdate = False

        wynnAPI: WynnAPI = bot.get_cog("WynnAPI")
        self._guildStatsTracker = wynnAPI.guildStats.get_tracker()
        self._igMembers: Set[str] = set()
        self._config: Configuration = bot.get_cog("Configuration")
        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._snapshotManager.add("MemberManager", self)

    def __loaded__(self):
        self._ig_members_update.start()
        self._member_deletion.start()
    
    def __snap__(self):
        return {
            "stats": {m.ign: self.make_stats_msg(m) for m in self.members.values()},
            "members": self.make_members_pages(False),
            "members.idle": self.make_members_pages(True),
            "members.missing": self.make_members_missing_msg()
        }
    
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
    
    @tasks.loop(minutes=MEMBER_DELETION_INTERVAL)
    async def _member_deletion(self):
        for id_ in self._deletionQueue:
            Logger.bot.info(f"deleting {self._removedMembers[id_][0]}")
            del self._removedMembers[id_]
        self._deletionQueue = list(self._removedMembers.keys())
        
    @_member_deletion.before_loop
    async def _before_member_deletion(self):
        Logger.bot.debug("Starting member deletion loop")

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
            LeaderBoard.update_all_rank_base(gMember.id)
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
        id_ = dMember.id
        if id_ in self._removedMembers:
            gMember, statsInfo = self._removedMembers[id_]
            Logger.bot.info(f"undo removal of {gMember}")

            del self._removedMembers[id_]
            if id_ in self._deletionQueue:
                self._deletionQueue.remove(id_)

            LeaderBoard.force_add_entry(id_, statsInfo)

        gMember = GuildMember(dMember, *(self._config.get_rank(dMember)))
        
        self.ignIdMap[gMember.ign] = id_
        self.members[id_] = gMember

        if gMember.ign not in self._igMembers:
            self.idleMembers.add(id_)
            Logger.bot.info(f"{gMember.ign} status set to idle")
        
        return gMember
    
    def _remove_member(self, gMember: GuildMember):
        Logger.bot.info(f"removed guild member {gMember}")
        id_ = gMember.id

        del self.members[id_]
        del self.ignIdMap[gMember.ign]
        id_ in self.idleMembers and self.idleMembers.remove(id_)

        self._removedMembers[id_] = (gMember, LeaderBoard.get_entry(id_))
        LeaderBoard.remove_entry(id_)

    def get_igns_set(self) -> Set[str]:
        return set(self.ignIdMap.keys())
    
    def get_tracked_igns(self) -> Set[str]:
        idle_igns = {self.members[id_].ign for id_ in self.idleMembers}
        return self.get_igns_set().difference(idle_igns)
    
    def get_member_by_ign(self, ign: str) -> GuildMember:
        return self.members[self.ignIdMap[ign]]
    
    def make_stats_msg(self, member: GuildMember):
        statInfo = LeaderBoard.get_entry(member.id)

        maxStatLen = max(map(lambda e: len(str(e[0])), statInfo.values()))
        maxRankLen = max(map(lambda e: len(str(e[1])), statInfo.values()))

        separator = "-" * (21 + maxStatLen + maxRankLen) + "\n"
        statDisplay = f"%{maxStatLen}d (#%d)\n"
        idleStatus = "-- NOT IN GUILD" if member.id in self.idleMembers else ""

        text = ""
        text += f"Total XP:          {statDisplay}" % statInfo["xp"]
        text += f"Accumulated XP:    {statDisplay}" % statInfo["xpAcc"]
        text += f"Bi-Weekly XP:      {statDisplay}" % statInfo["xpBw"]
        text += separator
        text += f"Total Em:          {statDisplay}" % statInfo["emerald"]
        text += f"Accumulated Em     {statDisplay}" % statInfo["emeraldAcc"]
        text += f"Bi-Weekly Em       {statDisplay}" % statInfo["emeraldBw"]
        text += separator
        text += f"Total Wars:        {statDisplay}" % statInfo["warCount"]
        text += f"Accumulated Wars:  {statDisplay}" % statInfo["warCountAcc"]
        text += f"Bi-Weekly Wars:    {statDisplay}" % statInfo["warCountBw"]
        text += "\n"
        text += f"discord {member.discord} {idleStatus}"

        vRank = f"<{member.vRank}> " if member.vRank else ""
        title = f"[{member.rank}] {vRank}{member.ign}"

        return decorate_text(text, title=title)

    @parser("stats", "ign", "-snap")
    async def display_stats(self, ctx: commands.Context, ign, snap):
        if snap:
            statsSnap = await self._snapshotManager.get_snapshot_cmd(ctx, snap,
                "MemberManager", "stats")
            if ign not in statsSnap:
                await ctx.send(embed=make_alert(f"{ign} is not in the guild."))
                return
            text = statsSnap[ign]
        else:
            if ign not in self.ignIdMap:
                await ctx.send(embed=make_alert(f"{ign} is not in the guild."))
                return
            text = self.make_stats_msg(self.get_member_by_ign(ign))
        
        await ctx.send(text)
    
    def make_members_pages(self, idle):
        lb = self.idleMembers if idle else self.members.keys()
        igns = self.ignIdMap.keys()
        members = self.members
        title = ("Idle " if idle else "") + "Guild Members"
        statSelector = lambda m: m.discord
        
        return make_entry_pages(make_stat_entries(lb, igns, members, statSelector),
            title=title)

    @parser("members", ["idle"], "-snap", isGroup=True)
    async def display_members(self, ctx: commands.Context, idle, snap):
        if snap:
            pages = await self._snapshotManager.get_snapshot_cmd(ctx, snap,
                "MemberManager", "members" + (".idle" if idle else ""))
        else:
            pages = self.make_members_pages(idle)
        await PagedMessage(pages, ctx.channel).init()
    
    def make_members_missing_msg(self):
        trackedIgns = self.get_igns_set()
        missingIgns = self._igMembers.difference(trackedIgns)
        return ", ".join(missingIgns)

    @parser("members missing", "-snap", parent=display_members)
    async def display_missing_members(self, ctx: commands.Context, snap):
        if snap:
            text = await self._snapshotManager.get_snapshot_cmd(ctx, snap,
                "MemberManager", "members.missing")
        else:
            text = self.make_members_missing_msg()
        await ctx.send(text)

    @parser("members fix", parent=display_members)
    async def fix_members(self, ctx):
        if not await self._config.perm_check(ctx, "user.dev"):
            return
        for member in self.members.values():
            if member.rank == "Commander":
                member.rank = "Cosmonaut"