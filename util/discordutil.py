from re import match

from discord import TextChannel, Guild, Role, Member
from discord.utils import find
from discord.ext.commands import Bot, Context

from msgmaker import make_alert


class Discord:

    RANKS = ["Cosmonaut", "Strategist", "Pilot", "Rocketeer", "Cadet", "MoonWalker"]

    guild: Guild = None
    
    @classmethod
    def init(cls, bot: Bot):
        cls.guild = bot.guilds[0]
        cls.Channels._init()
        cls.Roles._init()
    
    @classmethod
    def have_role(cls, member: Member, roleId) -> bool:
        return bool(find(lambda r: r.id == roleId, member.roles))
    
    @classmethod
    def have_role_named(cls, member: Member, roleName) -> bool:
        return bool(find(lambda r: r.name == roleName, member.roles))
    
    @classmethod
    def have_min_rank(cls, member: Member, minRank) -> bool:
        ranks = cls.RANKS[:cls.RANKS.index(minRank) + 1]
        return bool(find(lambda r: r.name in ranks, member.roles))
    
    @classmethod
    def get_rank(cls, member: Member):
        nick = member.nick
        if not nick or " " not in nick:
            return None
        
        roleRank = find(lambda r: r.name in cls.RANKS, member.roles)
        if not roleRank:
            return None
        roleRank = roleRank.name

        [*nickRank, _] = nick.split(" ")
        nickRank = " ".join(nickRank)

        if nickRank == roleRank:
            return (roleRank, None)
        return (roleRank, nickRank)
    
    @classmethod
    async def send(cls, channelId, text, **kwargs):
        if not channelId:
            return
        return await cls.guild.get_channel(channelId).send(text, **kwargs)
    
    @classmethod
    def split_text(cls, text, chunkSize=2000):
        segments = []
        copy = text
        while len(copy) > chunkSize:
            seg = copy[:chunkSize]
            if "\n" in seg:
                splitIndex = len(seg) - seg[::-1].index("\n") - 1
            elif " " in seg:
                splitIndex = len(seg) - seg[::-1].index(" ") - 1
            else:
                splitIndex = chunkSize
            segments.append(copy[:splitIndex])
            copy = copy[splitIndex:]
        segments.append(copy)
        return segments
    
    @classmethod
    def parse_channel(cls, target: str) -> TextChannel:
        m = match("<#([0-9]+)>", target)
        if m:
            return cls.guild.get_channel(int(m.groups()[0]))
        else:
            return find(lambda c: c.name == target, cls.guild.channels)
    
    @classmethod
    def parse_role(cls, target: str) -> Role:
        m = match("<@&([0-9]+)>", target)
        if m:
            return cls.guild.get_role(int(m.groups()[0]))
        else:
            return find(lambda r: r.name == target, cls.guild.roles)
    
    @classmethod
    def parse_user(cls, target: str) -> Member:
        m = match("<@!([0-9]+)>", target)
        if m:
            return cls.guild.get_member(int(m.groups()[0]))
        else:
            return cls.guild.get_member_named(target)

    @classmethod
    async def user_check(cls, ctx: Context, *userIds):
        passed = ctx.author.id in userIds
        if not passed:
            text = "You have no permission to use this command!"
            await ctx.send(embed=make_alert(text))
        return passed

    @classmethod
    async def channel_check(cls, ctx: Context, channelId):
        passed = ctx.channel.id == channelId
        if not passed:
            text = "This command can't be used in this channel!"
            await ctx.send(embed=make_alert(text))
        return passed
    
    @classmethod
    async def role_check(cls, ctx: Context, roleId):
        passed = cls.have_role(ctx.author, roleId)
        if not passed:
            text = "You don't have the role needed to use this command!"
            await ctx.send(embed=make_alert(text))
        return passed
    
    @classmethod
    async def rank_check(cls, ctx: Context, minRank):
        passed = cls.have_min_rank(ctx.author, minRank)
        if not passed:
            text = "Your rank have no permission to use this command!"
            await ctx.send(embed=make_alert(text))
        return passed
    
    class Channels:

        guild: TextChannel = "guild-chat"
        expedition: TextChannel = "galactic-expedition"

        @classmethod
        def _init(cls):
            for attr, val in cls.__dict__.items():
                if not attr.startswith("_"):
                    setattr(cls, attr, Discord.parse_channel(val))
    
    class Roles:

        expeditioner: Role = "Expeditioner"

        @classmethod
        def _init(cls):
            for attr, val in cls.__dict__.items():
                if not attr.startswith("_"):
                    setattr(cls, attr, Discord.parse_role(val))