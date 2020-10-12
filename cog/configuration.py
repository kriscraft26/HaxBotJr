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

    def _config_change_cb(self, cb, logMsg):
        def callback(msg):
            cb()
            Logger.bot.info(logMsg)
        return callback

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

            cb = lambda: self._config.update({field: None})
            logMsg = f"Reset {field} from {channel} to None by {ctx.author}"
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

            cb = lambda: self._config.update({field: channel.id})
            prev = self._config[field]
            if prev:
                prev = self.guild.get_channel(prev)
            logMsg = f"Changed {field} from {prev} to {channel} by {ctx.author}"
        
        await ConfirmMessage(
            ctx, text, successText, self._config_change_cb(cb, logMsg)).init()
            
    
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

            cb = lambda: self._config[field].remove(user.id)
            logMsg = f"Removed {user} from {field} by {ctx.author}"
        else:
            if user.id in users:
                text = f"{user} is already part of {type_} users."
                await ctx.send(embed=make_alert(text, color=COLOR_INFO))
                return

            text = f"Are you sure to add {user} to {type_} users?"
            successText = f"Successfully added {user} to {type_} users."

            cb = lambda: self._config[field].add(user.id)
            logMsg = f"Added {user} to {field} by {ctx.author}"
        
        await ConfirmMessage(
            ctx, text, successText, self._config_change_cb(cb, logMsg)).init()

    @parser("config role", ["type", ("visual", "personal")], "-entry", "-remove", "-add",
        parent=display_config, type="type_", entry="role")
    async def config_roles(self, ctx: commands.Context, type_, role, remove, add):
        field = f"role.{type_}"
        roleMap: dict = self._config[field]

        if not remove and not add:
            text = "" if roleMap else "Empty"
            embed: Embed = make_alert(text, title=field, color=COLOR_INFO)

            getMember = self.guild.get_role if type_ == "visual" else self.guild.get_member
            for roleId, memberIds in roleMap.items():
                role = str(self.guild.get_role(roleId))
                if memberIds:
                    value = ", ".join(map(lambda i: str(getMember(i)), memberIds))
                else:
                    value = "Empty"
                embed.add_field(name=role, value=value, inline=False)
            await ctx.send(embed=embed)
            return

        if role:
            role = self.parse_role(role)
            if not role:
                await ctx.send(embed=make_alert("bad role entry input"))
                return

        item = remove or add
        if role:
            item = self.parse_role(item) if type_ == "visual" else self.parse_user(item)
            if not item:
                await ctx.send(embed=make_alert("bad item input"))
                return
        else:
            item = self.parse_role(item)
            if not item:
                await ctx.send(embed=make_alert("bad role input"))
                return
        
        if remove:
            if role:
                if item.id not in roleMap[role.id]:
                    text = f"{item} is not under {role} entry of {type_} roles"
                    await ctx.send(embed=make_alert(text))
                    return
                
                text = f"Are you sure to remove {item} from {role} entry of {type_} roles?"
                successText = \
                    f"Successfully removed {item} from {role} entry of {type_} roles."

                cb = lambda: self._config[field][role.id].remove(item.id)
                logMsg = f"Removed {item} from {role} entry of {field} by {ctx.author}"
            else:
                if item.id not in roleMap:
                    text = f"{item} is not an entry of {type_} roles"
                    await ctx.send(embed=make_alert(text))
                    return
                
                text = f"Are you sure to remove {item} entry from {type_} roles?"
                successText = f"Successfully removed {item} entry from {type_} roles."

                cb = lambda: self._config[field].pop(item.id)
                logMsg = f"Removed {item} entry from {field} by {ctx.author}"
        else:
            if role:
                if item.id in roleMap[role.id]:
                    text = f"{item} is already under {role} entry of {type_} roles"
                    await ctx.send(embed=make_alert(text))
                    return
                
                text = f"Are you sure to add {item} to {role} entry of {type_} roles?"
                successText = f"Successfully added {item} to {role} entry of {type_} roles."

                cb = lambda: self._config[field][role.id].add(item.id)
                logMsg = f"Added {item} to {role} entry of {field} by {ctx.author}"
            else:
                if item.id in roleMap:
                    text = f"{item} is already an entry of {type_} roles"
                    await ctx.send(embed=make_alert(text))
                    return
                
                text = f"Are you sure to add {item} entry to {type_} roles?"
                successText = f"Successfully added {item} entry to {type_} roles."

                cb = lambda: self._config[field].update({item.id: set()})
                logMsg = f"Added {item} entry to {field} by {ctx.author}"
        
        await ConfirmMessage(
            ctx, text, successText, self._config_change_cb(cb, logMsg)).init()