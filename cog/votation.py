from typing import Dict, Set
from asyncio import sleep
import operator

from discord import TextChannel, Member, Message, Reaction, Emoji, Embed
from discord.ext import commands, tasks
from discord.utils import find

from logger import Logger
from msgmaker import make_alert, COLOR_INFO, decorate_text
from reactablemessage import ConfirmMessage
from util.cmdutil import parser
from cog.configuration import Configuration
from cog.datamanager import DataManager


NUMBER_EMOJIS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
REFRESH_INTERVAL = 3  # in hours


@DataManager.register("votes")
class Votation(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.expeditioners: Set[int] = set()
        self.votes = {}

        self._config: Configuration = bot.get_cog("Configuration")

        self.bot = bot

    async def __loaded__(self):
        channel = self._config.guild.get_channel(self._config("channel.expedition"))
        isExpeditioner = lambda m: self._config.has_role("expedition", m)
        self.expeditioners = set(map(lambda m: m.id, 
            filter(isExpeditioner, channel.members)))

        self._refresh_loop.start()
    
    @tasks.loop(hours=REFRESH_INTERVAL)
    async def _refresh_loop(self):
        for vote in self.votes.values():
            await vote.refresh(self._config, self.expeditioners)
    
    @_refresh_loop.before_loop
    async def _before_refresh_loop(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting vote refresh loop")

    def _find_expeditioners(self, channel: TextChannel) -> Set[int]:
        return set(map(lambda m: m.id, filter(self._is_expeditioner, channel.members)))
    
    def _is_expeditioner(self, member: Member) -> bool:
        return bool(find(lambda r: r.name == "Expeditioner", member.roles))
    
    def _is_expedition_channel(self, channel: TextChannel) -> bool:
        return channel.name == "galactic-expedition"
    
    async def _start_vote(self, ctx: commands.Context, voteCls, title, target, **kwargs):
        if not await self._config.perm_check(ctx, "group.staff"):
            return
        if not self._is_expeditioner(ctx.author):
            await ctx.send(embed=make_alert("Only an expeditioner can start a vote."))
            return
        if not self._is_expedition_channel(ctx.channel):
            await ctx.send(embed=make_alert("Can only start vote in expedition channel."))
            return
        self.expeditioners = self._find_expeditioners(ctx.channel)
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
        await vote.start(ctx.channel, self.expeditioners, self._config)
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, member: Member):
        if not self.votes:
            return

        if member.id not in self.expeditioners:
            return
        
        message: Message = reaction.message
        emoji = reaction.emoji

        for vote in self.votes.values():
            if vote.voteMsg == message.id and emoji in vote.options:
                await message.remove_reaction(emoji, member)
                await vote.set_vote(member.id, emoji, self._config)

                if vote.should_auto_end():
                    channel = self._config("channel.expedition")
                    channel = self._config.guild.get_channel(channel)
                    await self._end_vote_cb(channel, vote, True)

                return
    
    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        if not self.votes:
            return
        
        id_ = after.id
        isBefore = self._is_expeditioner(before)
        isAfter = self._is_expeditioner(after)

        if isBefore and not isAfter:
            self.expeditioners.remove(id_)
            for vote in self.votes.values():
                await vote.remove_expeditioner(id_, self._config)
        elif not isBefore and isAfter:
            self.expeditioners.add(id_)
            for vote in self.votes.values():
                await vote.add_expeditioner(id_, self._config)
    
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
        if not await self._config.perm_check(ctx, "group.staff"):
            return

        if not self.votes:
            await ctx.send(embed=make_alert("No active vote."))
            return
        if not self._is_expeditioner(ctx.author):
            await ctx.send(embed=make_alert("Only an expeditioner can end the vote."))
            return
        if title not in self.votes:
            await ctx.send(embed=make_alert(f"No vote titled `{title}`."))
            return
        await ctx.message.delete()

        text = f"Are you sure to end the vote `{title}`?"
        vote = self.votes[title]
        await ConfirmMessage(
            ctx, text, None, self._end_vote_cb, ctx.channel, vote, anonymous).init()

    async def _end_vote_cb(self, channel, vote, anonymous):
        await vote.end(channel, anonymous, self._config)
        del self.votes[vote.title]
    
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
        if not await self._config.perm_check(ctx, "group.staff"):
            return

        vote = await self._get_option_vote(ctx, title)
        if not vote:
            return
        
        if await vote.add_option(ctx.channel, option):
            await ctx.message.delete()

    @parser("vote options remove", "title", "option", parent=start_options_vote)
    async def remove_option(self, ctx: commands.Context, title, option):
        if not await self._config.perm_check(ctx, "group.staff"):
            return
        
        vote = await self._get_option_vote(ctx, title)
        if not vote:
            return
        
        if await vote.remove_option(ctx.channel, option, self._config):
            await ctx.message.delete()

class Vote:

    def __init__(self, title, options, default, target):
        self.title = title
        self.options: Dict[str, str] = options
        self.default: str = default
        self.vote = {}
    
        self.voteMsg: int = None
        self.memberMsg: int = None

        self.target = target
    
    def __repr__(self):
        s = "<Vote"
        for name, val in self.__dict__.items():
            s += f" {name}={val}"
        return s + ">"

    def make_vote_embed(self) -> Embed:
        title = "" if self.target is None else f"target: {self.target}%"
        text = "\n".join([f"{emoji} {s}" for emoji, s in self.options.items()])
        subtext = "default vote: " + self.options[self.default] if self.default else None
        return make_alert(text, subtext=subtext, title=title, color=COLOR_INFO)

    def make_member_embed(self, expeditioners, config: Configuration) -> Embed:
        names = set()

        votedCount = 0
        for id_ in expeditioners:
            name = config.guild.get_member(id_).display_name.split(" ")[-1]
            if self.vote[id_]:
                name = f"~~{name}~~"
                votedCount += 1
            names.add(name)
        
        memberNum = len(expeditioners)
        percent = int(votedCount / len(expeditioners) * 100)
        progress = "{0:⬜<10}".format("🟩" * (percent//10))
        progress += f"  {percent}%\n\n"
        
        embed = make_alert(progress, title=self.title, color=COLOR_INFO)
        embed.add_field(name="Expeditioners:", value=", ".join(names))
        return embed
    
    async def add_expeditioner(self, id_, config):
        self.vote[id_] = None
        await self.update_member_msg(config)
    
    async def remove_expeditioner(self, id_, config):
        del self.vote[id_]
        await self.update_member_msg(config)

    async def update_member_msg(self, config: Configuration):
        embed = self.make_member_embed(list(self.vote.keys()), config)
        channel: TextChannel = config.guild.get_channel(config("channel.expedition"))
        msg = await channel.fetch_message(self.memberMsg)
        await msg.edit(embed=embed)
    
    async def refresh(self, config: Configuration, expeditioners):
        channel: TextChannel = config.guild.get_channel(config("channel.expedition"))

        msg = await channel.fetch_message(self.memberMsg)
        await msg.delete()
        msg = await channel.fetch_message(self.voteMsg)
        await msg.delete()
        
        await self._send_messages(channel, expeditioners, config)
    
    async def _send_messages(self, channel, expeditioners, config):
        msg = await channel.send(embed=self.make_member_embed(expeditioners, config))
        self.memberMsg = msg.id
        msg = await channel.send(embed=self.make_vote_embed())
        self.voteMsg = msg.id

        for emoji in self.options:
            await msg.add_reaction(emoji)
            await sleep(0.25)
        
        await msg.pin(reason="Vote message.")

    async def start(self, channel: TextChannel, expeditioners, config):
        self.vote = {id_: None for id_ in expeditioners}
        await self._send_messages(channel, expeditioners, config)
    
    def should_auto_end(self):
        if not self.target:
            return False
        for emoji in self.options:
            count = len(list(filter(lambda v: v == emoji, self.vote.values())))
            totalPercent = int(count / len(self.vote) * 100)
            if totalPercent >= self.target:
                return True
        return False
    
    async def end(self, channel: TextChannel, anonymous, config: Configuration):
        maxDescLen = max(max(map(len, self.options.values())), 6) + 2

        entries = [f"# {self.title} #"]
        if self.default:
            votedNum = len(self.vote)
            entries.append(f"[%-{maxDescLen - 1}s  [Count]  [Vote%%]" % "Option]")
            template = f"%-{maxDescLen}s   %-2d        %3d%%"
        else:
            votedNum = len(list(filter(bool, self.vote.values())))
            entries.append(
                f"[%-{maxDescLen - 1}s  [Count]  [Vote%%]  [Global%%]" % "Option]")
            template = f"%-{maxDescLen}s   %-2d        %3d%%       %3d%%"

        for emoji, desc in self.options.items():
            desc = f"<{desc}>"
            count = len(list(filter(lambda v: v == emoji, self.vote.values())))
            if emoji == self.default:
                count += len(list(filter(operator.not_, self.vote.values())))

            votePercent = int(count / votedNum * 100) if votedNum else 0
            if self.default:
                entries.append(template % (desc, count, votePercent))
            else:
                totalPercent = int(count / len(self.vote) * 100)
                entries.append(template % (desc, count, votePercent, totalPercent))
        
        await channel.send(decorate_text("\n".join(entries), sh="apache"))

        if not anonymous:
            nameMap = {emoji: set()  for emoji in self.options}
            for id_, emoji in self.vote.items():
                if emoji:
                    name = config.guild.get_member(id_).display_name.split(" ")[-1]
                    nameMap[emoji].add(name)
            
            embed = Embed()
            for emoji, names in nameMap.items():
                names = ", ".join(names) if names else "No one"
                embed.add_field(name=self.options[emoji], value=names)
            
            await channel.send(embed=embed)
        
        message = await channel.fetch_message(self.voteMsg)
        await message.unpin(reason="Vote ended")
    
    async def check(self, ctx):
        if self.default and self.default not in self.options:
            await ctx.send(embed=make_alert("Default isn't part of options."))
            return
        return True

    async def set_vote(self, id_, emoji, config):
        self.vote[id_] = emoji
        await self.update_member_msg(config)


class BinaryVote(Vote):

    def __init__(self, title, default, target):
        options = {"✅": "yes", "❌": "no"}
        if default:
            defaultChoice = "✅" if default == "yes" else "❌"
        else:
            defaultChoice = None
        super().__init__(title, options, defaultChoice, target)
    
    def make_vote_embed(self):
        title = "" if self.target is None else f"target: {self.target}%"
        subtext = "default vote: " + self.options[self.default] if self.default else None
        return make_alert("Vote here", subtext=subtext, title=title, color=COLOR_INFO)
    
    async def check(self, ctx):
        return True


class OptionVote(Vote):

    async def check(self, ctx):
        if len(self.options) > 10:
            await ctx.send(embed=make_alert("Max amount of options are 10."))
            return
        if not await super().check(ctx):
            return
        return True
    
    async def start(self, channel, expeditioners, config):
        self.default = \
            NUMBER_EMOJIS[self.options.index(self.default)] if self.default else None
        self.options = {NUMBER_EMOJIS[i]: s for i, s in enumerate(self.options)}
        await super().start(channel, expeditioners, config)
    
    async def add_option(self, channel: TextChannel, option):
        if len(self.options) == 10:
            await channel.send(embed=make_alert("Can't add more option."))
            return
        
        emoji = NUMBER_EMOJIS[len(self.options)]
        self.options[emoji] = option
        
        msg: Message = await channel.fetch_message(self.voteMsg)
        await msg.add_reaction(emoji)
        await msg.edit(embed=self.make_vote_embed())
        
        return True
    
    async def remove_option(self, channel: TextChannel, option, config):
        if option not in self.options.values():
            await channel.send("There are no such option.")
            return
        
        hasRemoved = False
        newOptions = {}

        for emoji, desc in self.options.items():
            if hasRemoved:
                newEmoji = NUMBER_EMOJIS[NUMBER_EMOJIS.index(emoji) - 1]
                newOptions[newEmoji] = desc

                for id_, vote in self.vote.items():
                    if vote == emoji:
                        self.vote[id_] = newEmoji
            else:
                if desc == option:
                    hasRemoved = True
                    for id_, vote in self.vote.items():
                        if vote == emoji:
                            self.vote[id_] = None
                else:
                    newOptions[emoji] = desc
        self.options = newOptions

        msg: Message = await channel.fetch_message(self.voteMsg)
        await msg.remove_reaction(emoji, msg.author)
        await msg.edit(embed=self.make_vote_embed())

        await self.update_member_msg(config)

        return True


class ConsensusVote(Vote):

    def __init__(self, title, target):
        options = {"✅": "Assent", "👌": "Reserve", "👎": "Dissent", 
                   "❌": "Object", "😶": "Stand Aside"}
        super().__init__(title, options, "✅", 100)
    
    def make_vote_embed(self):
        embed = super().make_vote_embed()
        embed.set_footer(text="")
        return embed
    
    async def check(self, ctx):
        return True