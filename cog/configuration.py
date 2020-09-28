from typing import Set, Dict, Union, Tuple, List, Any
from os import getenv

from discord import Member, Guild, TextChannel
from discord.utils import find
from discord.ext import commands

from logger import Logger
from msgmaker import decorate_text
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
            "channel.log": None
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