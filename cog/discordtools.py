from discord import Member, Role
from discord.ext import commands

from msgmaker import make_alert
from reactablemessage import ConfirmMessage
from util.cmdutil import parser
from util.discordutil import Discord


class DiscordTools(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.guildRoles = (
            # ranks
            "Flight Captains", "Rocketeer", "Space Pilot", "Passengers", "Engineer", "Cadet",
            "MoonWalker",
            # visual ranks
            "Top Gunner", "Rocket Fuel Champion",
            # pings
            "WarPing", "Strike Team", "Bomb Notif", "Movie Night", "Claim Alert",
            # perms
            "Expeditioner")
        self.mamagerRoles = (
            "War Leader", "Mission Planner", "Region Manager", "Forum Manager", "Bot Maker",
            "Promotion Manager", "Member Manager", "Application Manager")
        self.recruitRoles = ("WarPing", "Cadet", "Passengers")
        self.recruiterRoles = ("Engineer", "Passengers")
        self.trialCapRoles = ("Space Pilot", "Flight Captains")
        self.captainRoles = ("Rocketeer", "Flight Captains")
    
    def _map_roles(self, roleNames):
        roles = []
        for role in Discord.guild.roles:
            if role.name in roleNames:
                roles.append(role)
        return roles
    
    @parser("kick", "member")
    async def kick_member(self, ctx: commands.Context, member):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return
        
        member: Member = Discord.parse_user(member)
        if not member:
            await ctx.send(embed=make_alert("can't find specified member."))
            return
        rank = Discord.get_rank(member)
        if not rank:
            await ctx.send(embed=make_alert(f"{member.display_name} is not a guild member."))
            return
        if rank[0] == "Cosmonaut":
            await ctx.send(embed=make_alert("can't kick staff member."))
            return
        
        text = f"Are you sure to kick {member.display_name}?"
        successText = f"bye bye {member.display_name}."
        await ConfirmMessage(ctx, text, successText, 
            self._kick_member_cb, member, ctx.author).init()
    
    async def _kick_member_cb(self, member: Member, executor: Member):
        reason = f"kicked by {executor.display_name}"

        removeRoles = []
        for role in member.roles:
            if role.name in self.guildRoles or role.name in self.mamagerRoles:
                removeRoles.append(role)
        await member.remove_roles(*removeRoles, reason=reason)

        await member.edit(reason=reason, nick=None)
    
    @parser("invite", "member", "ign")
    async def invite_member(self, ctx: commands.Context, member, ign):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return

        member: Member = Discord.parse_user(member)
        if not member:
            await ctx.send(embed=make_alert("can't find specified member."))
            return
        if Discord.get_rank(member):
            await ctx.send(embed=make_alert(
                f"{member.display_name} is already a guild member."))
            return
        
        text = f"Are you sure to invite {member.display_name} / {ign}?"
        await ConfirmMessage(ctx, text, None,
            self._invite_member_cb, member, ign, ctx.author).init()
    
    async def _invite_member_cb(self, member: Member, ign, executor: Member):
        reason = f"invited by {executor.display_name}"

        nick = "Cadet " + ign
        await member.edit(reason=reason, nick=nick)
        await member.add_roles(*self._map_roles(self.recruitRoles), reason=reason)

        text = f"<@!{member.id}> welcome to the guild! 🥳"
        await Discord.Channels.guild.send(text)