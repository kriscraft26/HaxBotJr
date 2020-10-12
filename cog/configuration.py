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
        "user.dev": set(),
        "user.ignore": set(),
        "role.visual": {},
        "role.personal": {},
        "channel.xpLog": None,
        "channel.bwReport": None
    }

    def __init__(self, bot: commands.Bot):
        self._config = Configuration.DEFAULT_CONFIG
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
        
        sample = self._config["user.dev"].pop()
        self._config["user.dev"].add(sample)
        if type(sample) == str:
            Logger.bot.debug("outed config data detected, updating...")

            getMId = lambda s: self.parse_user(s).id
            getRId = lambda r: self.parse_role(r).id

            self._config["user.dev"] = set(map(getMId, self._config["user.dev"]))
            self._config["user.ignore"] = set(map(getMId, self._config["user.ignore"]))

            self._config["role.visual"] = {getRId(r): set(map(getRId, rs)) 
                for r, rs in self._config["role.visual"].items()}
            self._config["role.personal"] = {getRId(r): set(map(getMId, ms)) 
                for r, ms in self._config["role.personal"].items()}
            
            Logger.bot.debug(f"-> {self._config}")

    def __call__(self, configName: str):
        return self._config[configName]
    
    def _set(self, name: str, val):
        Logger.bot.info(f"Config {name}: {self._config[name]} -> {val}")
        self._config[name] = val
    
    async def send(self, channelName, text, **kwargs):
        channel = self.bot.get_channel(self._config["channel." + channelName])
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
        return member.id in self._config[f"user.{userName}"]

    def get_rank(self, member: Member) -> Union[None, Tuple[str, str]]:
        if self.is_of_user("ignore", member):
            return None

        nick = member.nick
        if not nick or " " not in nick:
            return None

        roleRank = find(lambda r: r.name in self._groups["guild"], member.roles)
        if not roleRank:
            return None

        [*nameRank, _] = nick.split(" ")
        nameRank = " ".join(nameRank).strip()
        nameRank = find(lambda r: r.name == nameRank, member.roles)
        if not nameRank:
            Logger.bot.warning(f"{nick}: missing nick rank")

        if roleRank.id == nameRank.id:
            return (roleRank.name, None)
        
        if nameRank.id in self._config["role.visual"]:
            if roleRank.id in self._config["role.visual"][nameRank.id]:
                return (roleRank.name, nameRank.name)
            Logger.bot.warning(f"{nick}: visual role mismatch")
            return None
        
        if nameRank.id in self._config["role.personal"]:
            if member.id in self._config["role.personal"][nameRank.id]:
                return (roleRank.name, nameRank.name)
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
            if type_ == "user":
                names = map(lambda i: str(self.guild.get_member(i)), self._config[fieldName])
            else:
                names = self._groups[name]
            names = ", ".join(names)
            alert = make_alert("You have no permission to use this command",
                subtext=f"only {names} can use it")
            await ctx.send(embed=alert)
        return passed

    async def cog_check(self, ctx: commands.Context):
        return await self.perm_check(ctx, "group.staff")

    @parser("config", isGroup=True)
    async def display_config(self, ctx: commands.Context):
        text = "\n".join(self._config.keys())
        await ctx.send(embed=make_alert(text, title="Configuration", color=COLOR_INFO))
    
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
        field = "channel." + type_

        if not reset and not set_:
            title = "channel." + type_
            channel = self.guild.get_channel(self._config[field])
            text = "#" + channel.name if channel else "Not set"
            await ctx.send(embed=make_alert(text, title=title, color=COLOR_INFO))
            return

        if reset:
            channel = self.guild.get_channel(self._config[field])
            if not channel:
                text = f"There are no channel set as {type_} channel"
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return
            text = f"Are you sure to reset {type_} channel? (currently #{channel.name})"
            successText = f"Successfully reset {type_} channel."

            cb = lambda m: self._set(f"channel.{type_}", None)
        else:
            channel: TextChannel = self.parse_channel(set_)
            if not channel:
                await ctx.send(embed=make_alert("bad channel input"))
                return
            channelName = f"#{channel.name}"

            if self._config[field] == channel.id:
                text = f"{channelName} is already set as {type_} channel."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return

            text = f"Are you sure to set {channelName} as {type_} channel?"
            successText = f"Successfully set {channelName} as {type_} channel."

            cb = lambda m: self._set(field, channel.id)
        
        await ConfirmMessage(ctx, text, successText, cb).init()
            
    
    @parser("config user", ["type", ("dev", "ignore")], "-remove", "-add",
        parent=display_config, type="type_")
    async def config_user(self, ctx: commands.Context, type_, remove, add):
        field = f"user.{type_}"
        users = self._config[field]

        if not remove and not add:
            if users:
                text = ", ".join(map(lambda i: str(self.guild.get_member(i)), users))
            else:
                text = "Empty"
            await ctx.send(embed=make_alert(text, title=field, color=COLOR_INFO))
            return
        
        user = self.parse_user(remove or add)
        if not user:
            await ctx.send(embed=make_alert("bad user input"))
            return

        if remove:
            if user.id not in users:
                text = f"{user} is not part of {type_} users."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return
            
            text = f"Are you sure to remove {user} from {type_} users?"
            successText = f"Successfully removed {user} from {type_} users."
            cb = lambda m: self._set(field, users.difference({user.id}))
        else:
            if user.id in users:
                text = f"{user} is already part of {type_} users."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return

            text = f"Are you sure to add {user} to {type_} users?"
            successText = f"Successfully added {user} to {type_} users."

            cb = lambda m: self._set(field, users.union({user.id}))
        
        await ConfirmMessage(ctx, text, successText, cb).init()

    @parser("config role", ["type", ("visual", "personal")], "-remove", "-add",
        parent=display_config, type="type_")
    async def config_roles(self, ctx: commands.Context, type_, remove, add):
        field = f"role.{type_}"
        roleMap: dict = self._config[field]

        if not remove and not add:
            embed: Embed = make_alert("", title=field, color=COLOR_INFO)
            for key, val in roleMap.items():
                embed.add_field(name=key, value=", ".join(val), inline=False)
            await ctx.send(embed=embed)
            return
        
        try:
            role = self.guild.get_role(int((remove or add)[3:-1])).name
        except:
            await ctx.send(embed=make_alert("bad role input"))
            return
        
        if remove:
            if role not in roleMap:
                pass