from typing import Set, Union, Tuple
from os import getenv
from re import match

from discord import Member, Guild, TextChannel, Message, Embed
from discord.utils import find
from discord.ext import commands

from logger import Logger
from msgmaker import *
from reactablemessage import PagedMessage, ConfirmMessage
from util.cmdutil import parser
from cog.datamanager import DataManager


@DataManager.register("_config")
class Configuration(commands.Cog):

    DEFAULT_CONFIG = {
        "user.dev": {},
        "user.ignore": {},
        "role.visual": {},
        "role.personal": {},
        "channel.xpLog": None,
        "channel.bwReport": None
    }

    def __init__(self, bot: commands.Bot):
        self._config = Configuration.DEFAULT_CONFIG
        self._channels = {
            "xpLog": None,
            "bwReport": None,
        }
        self._groups = {
            "guild": ["MoonWalker", "Cosmonaut", "Rocketeer", "Space Pilot", 
                      "Engineer", "Cadet"],
            "staff": ["Cosmonaut"],
            "trusted": ["Cosmonaut", "Rocketeer"]
        }
        
        self.guild: Guild = bot.guilds[0]
        self.bot = bot
    
    def __loaded__(self):
        for key, val in Configuration.DEFAULT_CONFIG.items():
            self._config.setdefault(key, val)
        removedKeys = set(self._config.keys()).difference(
            set(Configuration.DEFAULT_CONFIG.keys()))
        for key in removedKeys:
            del self._config[key]
        
        for key in self._channels:
            channelId = self._config["channel." + key]
            if channelId:
                self._channels[key] = self.guild.get_channel(channelId)

    def __call__(self, configName: str):
        if configName.startswith("channel."):
            return self._channels[configName.split(".")[1]]
        return self._config[configName]
    
    def _set(self, name: str, val):
        Logger.bot.info(f"Config {name}: {self._config[name]} -> {val}")
        self._config[name] = val

        configSub = name.split(".")[1]
        if configSub in self._channels:
            self._channels[configSub] = self.guild.get_channel(val) if val else None
    
    async def send(self, channelName, text, **kwargs):
        channel = self._channels.get(channelName, None)
        if not channel:
            return
        await channel.send(text, **kwargs)

    def is_of_group(self, groupName: str, member: Member) -> bool:
        rank = self.get_rank(member)
        if not rank:
            return False
        roleRank = rank[0]
        return roleRank in self._groups[groupName]
    
    def is_of_user(self, userName: str, member: Member) -> bool:
        return str(member) in self._config[f"user.{userName}"]

    def get_rank(self, member: Member) -> Union[None, Tuple[str, str]]:
        if self.is_of_user("ignore", member):
            return None

        nick = member.nick
        if not nick or " " not in nick:
            return None

        memberRoles = list(map(lambda r: r.name, member.roles))
        roleRank = find(lambda r: r in memberRoles, self._groups["guild"])
        if not roleRank:
            return None

        [*nameRank, _] = nick.split(" ")
        nameRank = " ".join(nameRank).strip()

        if roleRank == nameRank:
            return (roleRank, None)
        
        if nameRank in self._config["role.visual"]:
            if roleRank in self._config["role.visual"][nameRank]:
                return (roleRank, nameRank)
            Logger.bot.warning(f"{nick}: visual role mismatch")
            return None
        
        if nameRank in self._config["role.personal"]:
            if str(member) in self._config["role.personal"][nameRank]:
                return (roleRank, nameRank)
            Logger.bot.warning(f"{nick}: personal role mismatch")
            return None
        
        Logger.bot.warning(f"{nick}: rank role mismatch")
        return None
    
    def get_all_guild_members(self) -> Set[Member]:
        predicate = lambda m: not self.is_of_user("ignore", m) and\
                              self.is_of_group("guild", m)
        return set(filter(predicate, self.guild.members))

    async def perm_check(self, ctx: commands.Context, fieldName):
        type_, name = fieldName.split(".")
        checker = self.is_of_group if type_ == "group" else self.is_of_user
        passed = checker(name, ctx.author)
        if not passed:
            names = ", ".join(
                self._config[fieldName] if type_ == "user" else self._groups[name])
            alert = make_alert("You have no permission to use this command",
                subtext=f"only {names} can use it")
            await ctx.send(embed=alert)
        return passed

    async def cog_check(self, ctx: commands.Context):
        return await self.perm_check(ctx, "group.staff")

    @parser("config", isGroup=True)
    async def display_config(self, ctx: commands.Context):
        entries = self._config.keys()
        fmt = lambda k: f"{k}\n{self(k)}\n"
        entries = list(map(fmt, entries))
        entries[-1] = entries[-1].strip()

        pages = make_entry_pages(entries, maxEntries=5, title="Configuration")
        await PagedMessage(pages, ctx.channel).init()
    
    async def _set_channel(self, ctx: commands.Context, channel, channelType):
        channel: TextChannel = self.parse_channel(channel)
        if not channel:
            await ctx.send(embed=make_alert("bad channel input"))
            return
        channelName = f"#{channel.name}"

        if self._config[f"channel.{channelType}"] == channel.id:
            text = f"{channelName} is already set as {channelType} channel."
            await ctx.send(embed=make_alert(text, color=COLOR_INFO))
            return

        text = f"Are you sure to set {channelName} as {channelType} channel?"
        successText = f"Successfully set {channelName} as {channelType} channel."

        cb = lambda m: self._set(f"channel.{channelType}", channel.id)
        await ConfirmMessage(ctx, text, successText, cb).init()
    
    async def _reset_channel(self, ctx: commands.Context, channelType):
        channel = self._channels[channelType]
        if not channel:
            text = f"There are no channel set as {channelType} channel"
            await ctx.send(embed=make_alert(text, color=COLOR_INFO))
            return
        text = f"Are you sure to reset {channelType} channel? (currently #{channel.name})"
        successText = f"Successfully reset {channelType} channel."

        cb = lambda m: self._set(f"channel.{channelType}", None)
        await ConfirmMessage(ctx, text, successText, cb).init()
    
    def parse_channel(self, target: str):
        m = match("<#([0-9]+)>", target)
        if m:
            return self.guild.get_channel(int(m.groups()[0]))
        else:
            return find(lambda c: c.name == target, self.guild.channels)
    
    def parse_role(self, target: str):
        m = match("<@&([0-9]+)>", target)
        if m:
            return self.guild.get_role(int(m.groups()[0]))
        else:
            return find(lambda r: r.name == target, self.guild.roles)
    
    def parse_user(self, target: str):
        m = match("<@!([0-9]+)>", target)
        if m:
            return self.guild.get_member(int(m.groups()[0]))
        else:
            return self.guild.get_member_named(target)

    @parser("config channel", ["type", ("xpLog", "bwReport")], ["reset"], "-set",
        parent=display_config, type="type_", set="set_")
    async def config_channel(self, ctx: commands.Context, type_, reset, set_):
        if reset:
            await self._reset_channel(ctx, type_)
        elif set_:
            await self._set_channel(ctx, set_, type_)
        else:
            title = "channel." + type_
            channel = self._channels[type_]
            text = "#" + channel.name if channel else "Not set"
            await ctx.send(embed=make_alert(text, title=title, color=COLOR_INFO))
    
    @parser("config user", ["type", ("dev", "ignore")], "-remove", "-add",
        parent=display_config, type="type_")
    async def config_user(self, ctx: commands.Context, type_, remove, add):
        field = f"user.{type_}"
        users = self._config[field]

        if not remove and not add:
            text = ", ".join(users) if users else "Empty"
            await ctx.send(embed=make_alert(text, title=field, color=COLOR_INFO))
            return
        
        try:
            user = remove or add
            gMember = self.bot.get_cog("MemberManager").members[int(user[3:-1])]
        except:
            await ctx.send(embed=make_alert("bad user input"))
            return
        user = gMember.discord

        if remove:
            if user not in users:
                text = f"{user} is not part of {type_} users."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return
            
            text = f"Are you sure to remove {user} from {type_} users?"
            successText = f"Successfully removed {user} from {type_} users."
            cb = lambda m: self._set(field, users.difference({user}))
        else:
            if user in users:
                text = f"{user} is already part of {type_} users."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return

            text = f"Are you sure to add {user} to {type_} users?"
            successText = f"Successfully added {user} to {type_} users."

            cb = lambda m: self._set(field, users.union({user}))
        
        await ConfirmMessage(ctx, text, successText, cb).init()