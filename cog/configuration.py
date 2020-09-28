from typing import Set, Union, Tuple
from os import getenv

from discord import Member, Guild, TextChannel
from discord.utils import find
from discord.ext import commands

from logger import Logger
from msgmaker import make_entry_pages, make_alert
from pagedmessage import PagedMessage
from util.cmdutil import parser
from cog.datacog import DataCog


@DataCog.register("_config")
class Configuration(commands.Cog):

    DATA_FILE = "./data/CONFIGURATION-DATA"

    def __init__(self, bot: commands.Bot):
        self._config = {
            "group.guild": {"Cadet", "Engineer", "Space Pilot", "Rocketeer", 
                            "Cosmonaut", "Commander"},
            "group.staff": {"Cosmonaut", "Commander"},
            "visualRole": {
                "Top Gunner": {"Space Pilot", "Rocketeer"}
            },
            "channel.xpLog": None
        }
        
        targetGuildCheck = lambda g: g.name == getenv("GUILD")
        self.guild: Guild = find(targetGuildCheck, bot.guilds)
    
    def __call__(self, configName):
        return self._config[configName]
    
    def _set(self, name, val):
        Logger.bot.info(f"Config {name}: {self._config[name]} -> {val}")
        self._config[name] = val

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
    
    async def cog_check(self, ctx: commands.Context):
        isStaff = self.is_of_group("staff", ctx.author)
        if not isStaff:
            staffGroup = ", ".join(self._config["group.staff"])
            alert = make_alert("You have no permission to use this command",
                subtext=f"only {staffGroup} can use it")
            await ctx.send(embed=alert)
        return isStaff

    @parser("config", isGroup=True)
    async def display_config(self, ctx: commands.Context):
        entries = self._config.keys()
        fmt = lambda k: f"{k}\n{self._config[k]}\n"
        entries = list(map(fmt, entries))
        entries[-1] = entries[-1].strip()

        pages = make_entry_pages(entries, maxEntries=5, title="Configuration")
        await PagedMessage(pages, ctx.channel).init()