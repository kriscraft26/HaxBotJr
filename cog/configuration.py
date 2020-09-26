from typing import TypeVar, Generic, Set, Dict, Union, Tuple, List
from os import getenv

from discord import Member, Guild
from discord.utils import find
from discord.ext import commands

from cog.datacog import DataCog


T = TypeVar("T")


class Field(Generic[T]):

    def __init__(self, name: str, initValue: T):
        self.name = name
        self.val: T = initValue


@DataCog.register("guildGroup", "staffGroup", "visualRole")
class Configuration(commands.Cog):

    DATA_FILE = "./data/CONFIGURATION-DATA"

    def __init__(self, bot: commands.Bot):
        self.guildGroup: Field[Set[str]] = Field(
            "group.guild", 
            {"Cadet", "Engineer", "Space Pilot", "Rocketeer", "Cosmonaut", "Commander"})
        self.staffGroup: Field[Set[str]] = Field(
            "group.staff", 
            {"Cosmonaut", "Commander"})
        self.visualRole: Field[Dict[str, Set[str]]] = Field(
            "visualRole", 
            {"Top Gunner": {"Space Pilot", "Rocketeer"}})
        
        targetGuildCheck = lambda g: g.name == getenv("GUILD")
        self.guild: Guild = find(targetGuildCheck, bot.guilds)

    def is_guild_member(self, member: Member, igns: Set[str]) -> bool:
        return self.is_of_group(self.guildGroup, member) and \
            member.nick.split(" ")[-1] in igns
    
    def is_of_group(self, group: Field[Set[str]], member: Member) -> bool:
        rank = self.get_rank(member)
        if not rank:
            return False
        roleRank = rank[0]
        return roleRank in group.val

    def get_rank(self, member: Member) -> Union[None, Tuple[str, str]]:
        nick = member.nick.strip()
        if not nick or " " not in nick:
            return None

        roleRank = find(lambda r: r.name in self.guildGroup.val, member.roles)
        if not roleRank:
            return None
        roleRank = roleRank.name
        
        [*nameRank, _] = nick.split(" ")
        nameRank = " ".join(nameRank).strip()

        if nameRank in self.visualRole.val and roleRank not in self.visualRole.val[nameRank]:
            return None
        elif roleRank != nameRank:
            return None
        
        return (roleRank, nameRank)
    
    def get_all_guild_members(self, igns: Set[str]) -> Set[Member]:
        return set(filter(lambda m: self.is_guild_member(m, igns), self.guild.members))