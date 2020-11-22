from typing import Set

from discord import Member, Message, Embed
from discord.ext import commands
from discord.utils import find

from vote import *
from msgmaker import make_alert
from reactablemessage import RMessage
from util.cmdutil import parser
from util.discordutil import Discord
from cog.datamanager import DataManager


@DataManager.register("votes")
class Votation(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.expeditioners: Set[int] = set()
        self.votes = {}

        self.bot = bot

    async def __loaded__(self):
        isExpeditioner = lambda m: Discord.have_role(m, Discord.Roles.expeditioner.id)
        self.expeditioners = set(map(lambda m: m.id, 
            filter(isExpeditioner, Discord.Channels.expedition.members)))
    
    async def _start_vote(self, ctx: commands.Context, voteCls, title, target, **kwargs):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return
        if not await Discord.role_check(ctx, Discord.Roles.expeditioner.id):
            return
        if not await Discord.channel_check(ctx, Discord.Channels.expedition.id):
            return
        if not self.expeditioners:
            await ctx.send(embed=make_alert("No expeditioners in this channel."))
            return
        if title in self.votes:
            await ctx.send(embed=make_alert(f"The title {title} is already used."))
            return
        if target and not target.isnumeric():
            await ctx.send(embed=make_alert(f"The target has to be an integer."))
            return
        target = None if target is None else int(target)
        await ctx.message.delete()

        vote = voteCls(**kwargs, title=title, target=target)
        if not await vote.check(ctx):
            return

        self.votes[title] = vote
        await vote.start(self.expeditioners)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if not self.votes:
            return

        if payload.channel_id != Discord.Channels.expedition.id or \
           payload.member.id not in self.expeditioners:
            return
        
        message: Message = await Discord.Channels.expedition.fetch_message(payload.message_id)
        emoji = payload.emoji.name

        for vote in self.votes.values():
            if vote.voteMsg == payload.message_id and emoji in vote.options:
                await message.remove_reaction(emoji, payload.member)
                await vote.set_vote(payload.member.id, emoji)

                if vote.should_auto_end():
                    await self._end_vote_cb(vote, True)

                return
    
    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        if not self.votes:
            return
        
        id_ = after.id
        isBefore = Discord.have_role(before, Discord.Roles.expeditioner.id)
        isAfter = Discord.have_role(after, Discord.Roles.expeditioner.id)

        if isBefore and not isAfter:
            self.expeditioners.remove(id_)
            for vote in self.votes.values():
                await vote.remove_expeditioner(id_)
        elif not isBefore and isAfter:
            self.expeditioners.add(id_)
            for vote in self.votes.values():
                await vote.add_expeditioner(id_)
    
    @parser("vote", isGroup=True)
    async def _vote_root(self, ctx):
        pass

    @parser("vote binary", "title", [["default"], ("yes", "no")], "-target",
        parent=_vote_root)
    async def start_binary_vote(self, ctx: commands.Context, title, target, **kwargs):
        await self._start_vote(ctx, BinaryVote, title, target, **kwargs)

    @parser("vote options", "title", "options...", "-default", "-target", 
        parent=_vote_root, isGroup=True)
    async def start_options_vote(self, ctx: commands.Context, title, target, **kwargs):
        await self._start_vote(ctx, OptionVote, title, target, **kwargs)
    
    @parser("vote consensus", "title", parent=_vote_root)
    async def start_consensus_vote(self, ctx: commands.Context, title):
        await self._start_vote(ctx, ConsensusVote, title, None)
    
    @parser("vote end", "title", ["anonymous"], parent=_vote_root)
    async def end_vote(self, ctx: commands.Context, title, anonymous):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return

        if not self.votes:
            await ctx.send(embed=make_alert("No active vote."))
            return
        if not await Discord.role_check(ctx, Discord.Roles.expeditioner.id):
            return
        if title not in self.votes:
            await ctx.send(embed=make_alert(f"No vote titled `{title}`."))
            return
        await ctx.message.delete()

        text = f"Are you sure to end the vote `{title}`?"
        rMsg = RMessage(await ctx.send(embed=Embed(title=text)))
        await rMsg.add_reaction("❌", rMsg.delete)
        await rMsg.add_reaction("✅", self._end_vote_cb, 
            self.votes[title], anonymous, rMsg)

    async def _end_vote_cb(self, vote, anonymous, rMsg):
        await vote.end(anonymous)
        del self.votes[vote.title]

        await rMsg.delete()
    
    async def _get_option_vote(self, ctx: commands.Context, title):
        if title not in self.votes:
            await ctx.send(embed=make_alert(f"No active vote with title `{title}`"))
            return

        vote = self.votes[title]
        if not isinstance(vote, OptionVote):
            await ctx.send(embed=make_alert(f"`{title}` is not an options vote."))
            return
        
        return vote
    
    @parser("vote options add", "title", "option", parent=start_options_vote)
    async def add_option(self, ctx: commands.Context, title, option):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return

        vote = await self._get_option_vote(ctx, title)
        if not vote:
            return
        
        if await vote.add_option(option):
            await ctx.message.delete()

    @parser("vote options remove", "title", "option", parent=start_options_vote)
    async def remove_option(self, ctx: commands.Context, title, option):
        if not await Discord.rank_check(ctx, "Cosmonaut"):
            return
        
        vote = await self._get_option_vote(ctx, title)
        if not vote:
            return
        
        if await vote.remove_option(option):
            await ctx.message.delete()
    
    @parser("vote refresh", parent=_vote_root)
    async def refresh_votes(self, ctx: commands.Context):
        if not Discord.role_check(ctx, Discord.Roles.expeditioner.id):
            return
        await ctx.message.delete()

        for vote in self.votes.values():
            await vote.refresh(self.expeditioners)