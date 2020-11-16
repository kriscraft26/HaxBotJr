from typing import Dict, List, Callable, Set
from asyncio import sleep

from discord import Member, Embed, User
from discord.ext import tasks, commands

from logger import Logger
from event import Event
from wynnapi import WynnAPI
from msgmaker import *
from reactablemessage import RMessage
from leaderboard import LeaderBoard
from util.cmdutil import parser
from util.discordutil import Discord
from state.config import Config
from state.guildmember import GuildMember
from cog.snapshotmanager import SnapshotManager


IG_MEMBERS_UPDATE_INTERVAL = 3

IG_RANKS = ["Recruit", "Recruiter", "Captain", "Chief", "Owner"]


class MemberManager(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.hasInitMembersUpdate = False

        self._guildStatsTracker = WynnAPI.guildStats.get_tracker()
        self._igMembers: Set[str] = set()
        self._snapshotManager: SnapshotManager = bot.get_cog("SnapshotManager")

        self._snapshotManager.add("MemberManager", self)

        self.bot = bot
        self._ig_members_update.start()

    async def __snap__(self):
        return {
            "stats": {m.ign: self.make_stats_msg(m) async for m in GuildMember.iterate()},
            "members": await self.make_members_pages(False),
            "members.idle": await self.make_members_pages(True),
            "members.missing": await self.make_members_missing_msg()
        }
    
    @tasks.loop(seconds=IG_MEMBERS_UPDATE_INTERVAL)
    async def _ig_members_update(self):
        guildStats = self._guildStatsTracker.getData()
        if not guildStats:
            return
        
        if not self.hasInitMembersUpdate:
            self._igMembers = {m["name"] for m in guildStats["members"]}
            await self._bulk_update_members()
            self.hasInitMembersUpdate = True

        else:
            prevIgMembers = self._igMembers
            currIgMembers = set()

            for memberData in guildStats["members"]:
                ign = memberData["name"]
                currIgMembers.add(ign)

                if ign not in prevIgMembers:
                    text = ign + " has joined the guild"
                    await Discord.send(Config.channel_memberLog, text)

                member: GuildMember = GuildMember.get_member_named(ign)
                if member and member.status == GuildMember.IDLE:
                    await GuildMember.set_status(member.id, GuildMember.ACTIVE)
                
            missingIgns = prevIgMembers.difference(currIgMembers)
            self._igMembers = currIgMembers
            
            for ign in missingIgns:

                text = ign + " has left the guild"
                await Discord.send(Config.channel_memberLog, text)

                if GuildMember.is_ign_active(ign):
                    member = GuildMember.get_member_named(ign)
                    await GuildMember.set_status(member.id, GuildMember.IDLE)
    
    @_ig_members_update.before_loop
    async def _before_ig_members_update(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting in-game members update loop")

    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        isGMemberBefore = before.id in GuildMember.discordIdMap
        isGMemberAfter = Discord.get_rank(after)

        if isGMemberBefore and not isGMemberAfter:
            await GuildMember.remove(GuildMember.discordIdMap[before.id])
        elif not isGMemberBefore and isGMemberAfter:
            await GuildMember.add(after, isGMemberAfter)
        elif isGMemberBefore and isGMemberAfter:
            ignBefore = before.nick.split(" ")[-1]
            ignAfter = after.nick.split(" ")[-1]
            id_ = GuildMember.ignIdMap[ignBefore]
            if ignBefore != ignAfter:
                if not await GuildMember.ign_check(id_):
                    await GuildMember.remove(id_)
                    await GuildMember.add(after, isGMemberAfter)
            else:
                await GuildMember.update(id_, after)
    
    @commands.Cog.listener()
    async def on_member_remove(self, dMember: Member):
        if dMember.id in GuildMember.discordIdMap:
            await GuildMember.remove(GuildMember.discordIdMap[dMember.id])

    async def _bulk_update_members(self):
        currDiscordIds = set(map(lambda m: m.id, 
            filter(Discord.get_rank, Discord.guild.members)))
        prevDiscordIds = set(GuildMember.discordIdMap.keys())

        joined = currDiscordIds.difference(prevDiscordIds)
        for id_ in joined:
            dMember = Discord.guild.get_member(id_)
            memberId = await GuildMember.add(dMember, Discord.get_rank(dMember))
            if not memberId:
                continue

            if GuildMember.members[memberId].ign not in self._igMembers:
                await GuildMember.set_status(memberId, GuildMember.IDLE)
        
        removed = prevDiscordIds.difference(currDiscordIds)
        for id_ in removed:
            await GuildMember.remove(GuildMember.discordIdMap[id_])
        
        changed = prevDiscordIds.intersection(currDiscordIds)
        for id_ in changed:
            gMember = GuildMember.members[GuildMember.discordIdMap[id_]]
            dMember = Discord.guild.get_member(id_)
            ign = dMember.nick.split(" ")[-1]

            if gMember.ign != ign:
                if not await GuildMember.ign_check(gMember.id):
                    await GuildMember.remove(gMember.id)
                    await GuildMember.add(dMember, Discord.get_rank(dMember))
            else:
                await GuildMember.update(gMember.id, dMember)

            if ign in self._igMembers:
                await GuildMember.set_status(gMember.id, GuildMember.ACTIVE)
            else:
                await GuildMember.set_status(gMember.id, GuildMember.IDLE)
    
    def make_stats_msg(self, member: GuildMember):
        statInfo = LeaderBoard.get_entry(member.id)
        xp = statInfo["xpBw"]
        em = statInfo["emeraldBw"]
        wc = statInfo["warCountBw"]
        statTemplate = f"%-{len(str(max(xp[0], em[0], wc[0])))}d #%d"
        
        if member.ownerId:
            title = GuildMember.members[member.ownerId].ign + " " + member.ign
            text = ""
        elif member.discordId:
            title = str(Discord.guild.get_member(member.discordId)) + " " + member.ign
            text = f"rank     {member.rank}\n"
            if member.vRank:
                text += f"title    {member.vRank}\n"
            text += "-------\n"
        else:
            title = member.ign
            text = ""

        text += f"xp       {statTemplate % xp}\n"
        text += f"emerald  {statTemplate % em}\n"
        text += f"war      {statTemplate % wc}\n-------\n"
        text += f"status   {member.status}"

        return decorate_text(text, title=title)

    @parser("stats", "ign", "-snap")
    async def display_stats(self, ctx: commands.Context, ign, snap):
        if snap:
            statsSnap = await self._snapshotManager.get_snapshot_cmd(ctx, snap,
                "MemberManager", "stats")
            if not statsSnap:
                return
            if ign not in statsSnap:
                await ctx.send(embed=make_alert(f"{ign} is/was not in the guild."))
                return
            text = statsSnap[ign]
        else:
            if ign not in GuildMember.ignIdMap:
                await ctx.send(embed=make_alert(f"{ign} is/was not in the guild."))
                return
            text = self.make_stats_msg(GuildMember.get_member_named(ign))
        
        await ctx.send(text)
    
    async def make_members_pages(self, idle):
        title = ("Idle " if idle else "") + "Guild Members"
        valGetter = lambda m: Discord.guild.get_member(
            GuildMember.members[m.ownerId].discordId if m.ownerId else m.discordId)
        filter_ = lambda m: m.status == (GuildMember.IDLE if idle else GuildMember.ACTIVE)
        
        return make_entry_pages(await make_stat_entries(
            valGetter, group=False, filter_=filter_), title=title)

    @parser("members", ["idle"], "-snap", isGroup=True)
    async def display_members(self, ctx: commands.Context, idle, snap):
        if snap:
            pages = await self._snapshotManager.get_snapshot_cmd(ctx, snap,
                "MemberManager", "members" + (".idle" if idle else ""))
            if not pages:
                return
        else:
            pages = await self.make_members_pages(idle)
        
        rMsg = RMessage(await ctx.send(pages[0]))
        await rMsg.add_pages(pages)
    
    async def make_members_missing_msg(self):
        igns = self._igMembers.copy()
        filter_ = lambda m: m.status == GuildMember.ACTIVE
        mapper = lambda m: igns.remove(m.ign)
        async for _ in GuildMember.iterate(filter_, mapper):
            pass
        return ", ".join(igns)

    @parser("members missing", "-snap", parent=display_members)
    async def display_missing_members(self, ctx: commands.Context, snap):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return
        if snap:
            text = await self._snapshotManager.get_snapshot_cmd(ctx, snap,
                "MemberManager", "members.missing")
            if not text:
                return
        else:
            text = await self.make_members_missing_msg()
        await ctx.send(text)

    @parser("members fix", parent=display_members)
    async def fix_members(self, ctx):
        if not await Discord.user_check(ctx, *Config.user_dev):
            return
        for member in self.members.values():
            member.mcId = await WynnAPI.get_player_id(member.ign)
            await sleep(0.2)
    
    @parser("alt", isGroup=True)
    async def display_alt(self, ctx):
        if not GuildMember.altMap:
            await ctx.send("`No alts are registered.`")
            return
        
        embed = Embed()
        getName = lambda id_: GuildMember.members[id_].ign
        for ownerId, altIds in GuildMember.altMap.items():
            altNames = ", ".join(map(getName, altIds))
            embed.add_field(name=getName(ownerId), value=altNames, inline=False)
        await ctx.send(embed=embed)
    
    @parser("alt add", "main", "alt", parent=display_alt)
    async def add_alt(self, ctx, main, alt):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return
        owner = GuildMember.get_member_named(main)
        if not owner:
            await ctx.send(f"`{main} is not a guild member.`")
            return
        if not await GuildMember.add_alt(owner.id, alt):
            if alt in GuildMember.ignIdMap:
                await ctx.send(f"`{alt} is already an alt.`")
            else:
                await ctx.send(f"`the player {alt} doesn't exist.`")
            return
        await ctx.message.add_reaction("✅")
    
    @parser("alt remove", "alt", parent=display_alt)
    async def remove_alt(self, ctx, alt):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return
        member = GuildMember.get_member_named(alt)
        if not member:
            await ctx.send(f"`{alt} is not a guild member.`")
            return
        if not member.ownerId:
            await ctx.send(f"`{alt} is not an alt.`")
            return
        await GuildMember.remove_alt(member.id)
        await ctx.message.add_reaction("✅")

        isNonMember = lambda m: \
            m.id not in GuildMember.discordIdMap and m.nick and m.nick.endswith(" " + alt)
        for dMember in filter(isNonMember, Discord.guild.members):
            ranks = Discord.get_rank(dMember)
            if ranks:
                await GuildMember.update(member.id, dMember)
                return
        await GuildMember.remove(member.id)