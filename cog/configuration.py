from typing import Set, Union, Tuple
from os import getenv

from discord import Member, Guild, TextChannel, Message
from discord.utils import find
from discord.ext import commands

from logger import Logger
from msgmaker import make_entry_pages, make_alert
from pagedmessage import PagedMessage
from confirmmessage import ConfirmMessage
from util.cmdutil import parser
from cog.datacog import DataCog


@DataCog.register("_config")
class Configuration(commands.Cog):

    DEFAULT_CONFIG = {
        "group.guild": {"Cadet", "Engineer", "Space Pilot", "Rocketeer", 
                        "Cosmonaut", "Commander"},
        "group.staff": {"Cosmonaut", "Commander"},
        "visualRole": {
            "Top Gunner": {"Space Pilot", "Rocketeer"}
        },
        "channel.xpLog": None
    }

    def __init__(self, bot: commands.Bot):
        self._config = Configuration.DEFAULT_CONFIG
        self._channels = {
            "channel.xpLog": None
        }
        
        targetGuildCheck = lambda g: g.name == getenv("GUILD")
        self.guild: Guild = find(targetGuildCheck, bot.guilds)
    
    def __loaded__(self):
        for key, val in Configuration.DEFAULT_CONFIG.items():
            self._config.setdefault(key, val)
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

    def is_guild_member(self, member: Member, igns: Set[str]) -> bool:
        return self.is_of_group("guild", member) and \
            member.nick.split(" ")[-1] in igns
    
    def is_of_group(self, groupName: str, member: Member) -> bool:
        rank = self.get_rank(member)
        if not rank:
            return False
        roleRank = rank[0]
        return roleRank in self._config[f"group.{groupName}"]

    def get_rank(self, member: Member) -> Union[None, Tuple[str, str]]:
        nick = member.nick
        if not nick or " " not in nick:
            return None

        roleRank = find(lambda r: r.name in self._config["group.guild"], member.roles)
        if not roleRank:
            return None
        roleRank = roleRank.name
        
        [*nameRank, _] = nick.split(" ")
        nameRank = " ".join(nameRank).strip()

        if nameRank in self._config["visualRole"] and \
           roleRank not in self._config["visualRole"][nameRank]:
            return None
        elif roleRank != nameRank:
            return None
        
        return (roleRank, nameRank)
    
    def get_all_guild_members(self, igns: Set[str]) -> Set[Member]:
        return set(filter(lambda m: self.is_guild_member(m, igns), self.guild.members))
    
    async def staff_check(self, ctx: commands.Context):
        isStaff = self.is_of_group("staff", ctx.author)
        if not isStaff:
            staffGroup = ", ".join(self._config["group.staff"])
            alert = make_alert("You have no permission to use this command",
                subtext=f"only {staffGroup} can use it")
            await ctx.send(embed=alert)
        return isStaff

    async def cog_check(self, ctx: commands.Context):
        return await self.staff_check(ctx) 

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