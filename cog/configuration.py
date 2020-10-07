from typing import Set, Union, Tuple
from os import getenv

from discord import Member, Guild, TextChannel, Message
from discord.utils import find
from discord.ext import commands

from logger import Logger
from msgmaker import make_entry_pages, make_alert
from reactablemessage import PagedMessage, ConfirmMessage
from util.cmdutil import parser
from cog.datamanager import DataManager


@DataManager.register("_config")
class Configuration(commands.Cog):

    DEFAULT_CONFIG = {
        "group.guild": ["MoonWalker", "Cosmonaut", "Rocketeer", "Space Pilot", 
                        "Engineer", "Cadet"],
        "group.staff": ["Cosmonaut"],
        "group.trusted": ["Cosmonaut", "Rocketeer"],
        "user.dev": {"Pucaet#9528"},
        "user.ignore": {"Kyoto#1414"},
        "role.visual": {
            "Top Gunner": {"Space Pilot", "Rocketeer"},
            "Commander": {"Cosmonaut"},
            "Commandress": {"Cosmonaut"}
        },
        "role.personal": {
            "Princess": {"pontosaurus#6727"}
        },
        "channel.xpLog": None
    }

    def __init__(self, bot: commands.Bot):
        self._config = Configuration.DEFAULT_CONFIG
        self._channels = {
            "channel.xpLog": None
        }
        
        self.guild: Guild = bot.guilds[0]
    
    def __loaded__(self):
        for key, val in Configuration.DEFAULT_CONFIG.items():
            self._config.setdefault(key, val)
        removedKeys = set(self._config.keys()).difference(
            set(Configuration.DEFAULT_CONFIG.keys()))
        for key in removedKeys:
            del self._config[key]
        
        for key in self._channels:
            if self._config[key]:
                self._channels[key] = self.guild.get_channel(self._config[key])

    def __call__(self, configName):
        if configName in self._channels:
            return self._channels[configName]
        return self._config[configName]
    
    def _set(self, name, val):
        Logger.bot.info(f"Config {name}: {self._config[name]} -> {val}")
        self._config[name] = val
        if name in self._channels:
            self._channels[name] = self.guild.get_channel(val) if val else None
    
    async def send(self, channelName, text, **kwargs):
        channel = self._channels.get(f"channel.{channelName}", None)
        if not channel:
            return
        await channel.send(text, **kwargs)

    def is_of_group(self, groupName: str, member: Member) -> bool:
        rank = self.get_rank(member)
        if not rank:
            return False
        roleRank = rank[0]
        return roleRank in self._config[f"group.{groupName}"]
    
    def is_of_user(self, userName: str, member: Member) -> bool:
        return str(member) in self._config[f"user.{userName}"]

    def get_rank(self, member: Member) -> Union[None, Tuple[str, str]]:
        if self.is_of_user("ignore", member):
            return None

        nick = member.nick
        if not nick or " " not in nick:
            return None

        memberRoles = list(map(lambda r: r.name, member.roles))
        roleRank = find(lambda r: r in memberRoles, self._config["group.guild"])
        if not roleRank:
            return None

        [*nameRank, _] = nick.split(" ")
        nameRank = " ".join(nameRank).strip()

        if roleRank == nameRank:
            return (roleRank, None)
        
        if nameRank in self._config["role.visual"]:
            if roleRank in self._config["role.visual"][nameRank]:
                return (roleRank, nameRank)
            print(f"{nick}: visual role mismatch")
            return None
        
        if nameRank in self._config["role.personal"]:
            if str(member) in self._config["role.personal"][nameRank]:
                return (roleRank, nameRank)
            print(f"{nick}: personal role mismatch")
            return None
        
        print(f"{nick}: rank role mismatch")
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
            staffGroup = ", ".join(self._config[fieldName])
            alert = make_alert("You have no permission to use this command",
                subtext=f"only {staffGroup} can use it")
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
    
    @parser("config trackXP", parent=display_config)
    async def set_xp_channel(self, ctx: commands.Context):
        channel: TextChannel = ctx.channel
        if self._config["channel.xpLog"]:
            text = f"Are you sure to disbale xp tracking in #{channel.name}?"
            successText = f"Successfully disabled xp tracking in #{channel.name}."
        else:
            text = f"Are you sure to track xp in #{channel.name}?"
            successText = f"Successfully set #{channel.name} as xp tracking channel."

        await ConfirmMessage(ctx, text, successText, self.set_xp_channel_cb).init()
    
    async def set_xp_channel_cb(self, msg: ConfirmMessage):
        channel: TextChannel = msg.channel
        if self._config["channel.xpLog"]:
            self._set("channel.xpLog", None)
        else:
            self._set("channel.xpLog", channel.id)