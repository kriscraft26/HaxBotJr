from typing import Dict, Set
from asyncio import sleep
import operator

from discord import TextChannel, Member, Message, Reaction, Emoji, Embed
from discord.ext import commands
from discord.utils import find

from logger import Logger
from msgmaker import make_alert, COLOR_INFO, decorate_text
from reactablemessage import ConfirmMessage
from util.cmdutil import parser
from cog.configuration import Configuration


NUMBER_EMOJIS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


class Votation(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.memberMsg: Message = None
        self.voteMsg: Message = None
        self.expeditioners: Set[int] = set()
        self.options: Dict[str, str] = {}
        self.vote: Dict[int, str] = {}
        self.default: str = None

        self.bot = bot

    def _find_expeditioners(self, channel: TextChannel) -> Set[int]:
        return set(map(lambda m: m.id, filter(self._is_expeditioner, channel.members)))
    
    def _is_expeditioner(self, member: Member) -> bool:
        return bool(find(lambda r: r.name == "Expeditioner", member.roles))
    
    def _is_expedition_channel(self, channel: TextChannel) -> bool:
        return channel.name == "galactic-expedition"
    
    def _make_expeditioner_list(self):
        config: Configuration = self.bot.get_cog("Configuration")
        names = set()

        votedCount = 0
        for id_ in self.expeditioners:
            name = config.guild.get_member(id_).display_name
            if self.vote[id_]:
                name = f"~~{name}~~"
                votedCount += 1
            names.add(name)
        
        memberNum = len(self.expeditioners)
        percent = int(votedCount / len(self.expeditioners) * 100)
        progress = "{0:⬜<10}".format("🟩" * (percent//10))
        progress += f"  {percent}%\n\n"
        
        return progress + ", ".join(names)
    
    async def _start_vote(self, ctx: commands.Context, options: Dict, default: str):
        if not self._is_expeditioner(ctx.author):
            await ctx.send(embed=make_alert("Only an expeditioner can start a vote."))
            return
        if not self._is_expedition_channel(ctx.channel):
            await ctx.send(embed=make_alert("Can only start vote in expedition channel."))
            return
        expeditioners = self._find_expeditioners(ctx.channel)
        if not expeditioners:
            await ctx.send(embed=make_alert("No expeditioners in this channel."))
            return
        if default and default not in options:
            await ctx.send(embed=make_alert("Default isn't part of options."))
            return

        self.options = options
        self.default = default
        self.expeditioners = expeditioners
        self.vote = {id_: None  for id_ in expeditioners}

        alert = make_alert(self._make_expeditioner_list(), color=COLOR_INFO)
        self.memberMsg = await ctx.send(embed=alert)

        await ctx.message.delete()
        return True
    
    async def _add_reactions(self):
        for emoji in self.options:
            await self.voteMsg.add_reaction(emoji)
            await sleep(0.25)
    
    async def _update_member_msg(self):
        alert = make_alert(self._make_expeditioner_list(), color=COLOR_INFO)
        await self.memberMsg.edit(embed=alert)
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, member: Member):
        if not self.voteMsg:
            return

        message: Message = reaction.message
        if message.id != self.voteMsg.id:
            Logger.bot.debug(f"[DEBUG] different message {message.id} != {self.voteMsg.id}")
            return
        if member.id not in self.expeditioners:
            Logger.bot.debug(f"[DEBUG] not expeditioner {member}")
            return
        
        emoji = reaction.emoji
        Logger.bot.debug(f"[DEBUG] add vote {emoji} from {member}, {message.reactions}")
        await message.remove_reaction(emoji, member)
        if emoji in self.options:
            self.vote[member.id] = emoji
            await self._update_member_msg()
    
    @commands.Cog.listener()
    async def on_member_update(self, before: Member, after: Member):
        if not self.voteMsg:
            return
        
        id_ = after.id
        isBefore = self._is_expeditioner(before)
        isAfter = self._is_expeditioner(after)

        if isBefore and not isAfter:
            self.expeditioners.remove(id_)
            del self.vote[id_]
        elif not isBefore and isAfter:
            self.expeditioners.add(id_)
            self.vote[id_] = None

        if isBefore ^ isAfter:
            await self._update_member_msg()
    
    @parser("vote", isGroup=True)
    async def _vote_root(self, ctx):
        pass

    @parser("vote binary", [["default"], ("yes", "no")], parent=_vote_root)
    async def start_binary_vote(self, ctx: commands.Context, default):
        config: Configuration = self.bot.get_cog("Configuration")
        if not await config.perm_check(ctx, "group.staff"):
            return

        options = {"✅": "yes", "❌": "no"}
        if default:
            defaultChoice = "✅" if default == "yes" else "❌"
        else:
            defaultChoice = None
        if not await self._start_vote(ctx, options, defaultChoice):
            return

        subtext = "default vote: " + default if default else None

        alert = make_alert("Vote here", subtext=subtext, color=COLOR_INFO)
        self.voteMsg = await ctx.send(embed=alert)
        await self._add_reactions()

    @parser("vote options", "options...", "-default", parent=_vote_root)
    async def start_options_vote(self, ctx: commands.Context, options, default):
        config: Configuration = self.bot.get_cog("Configuration")
        if not await config.perm_check(ctx, "group.staff"):
            return

        if len(options) > 10:
            await ctx.send(embed=make_alert("Max amount of options are 10."))
            return
        if default and default not in options:
            await ctx.send(embed=make_alert("Invalid default choice"))
            return
        
        defaultChoice = NUMBER_EMOJIS[options.index(default)] if default else None
        options = {NUMBER_EMOJIS[i]: s for i, s in enumerate(options)}
        if not await self._start_vote(ctx, options, defaultChoice):
            return
        
        text = "\n".join([f"{emoji} {s}" for emoji, s in options.items()])
        subtext = "default vote: " + default if default else None
        alert = make_alert(text, subtext=subtext, color=COLOR_INFO)
        self.voteMsg = await ctx.send(embed=alert)
        await self._add_reactions()
    
    @parser("vote consensus", parent=_vote_root)
    async def start_consensus_vote(self, ctx: commands.Context):
        config: Configuration = self.bot.get_cog("Configuration")
        if not await config.perm_check(ctx, "group.staff"):
            return

        options = {"✅": "Assent", "👌": "Reserve", "👎": "Dissent", 
                   "❌": "Object", "😶": "Stand Aside"}
        if not await self._start_vote(ctx, options, "✅"):
            return
        
        text = "\n".join([f"{emoji} {s}" for emoji, s in options.items()])
        self.voteMsg = await ctx.send(embed= make_alert(text, color=COLOR_INFO))
        await self._add_reactions()
    
    @parser("vote end", ["anonymous"], parent=_vote_root)
    async def end_vote(self, ctx: commands.Context, anonymous):
        config: Configuration = self.bot.get_cog("Configuration")
        if not await config.perm_check(ctx, "group.staff"):
            return

        if not self.voteMsg:
            await ctx.send(embed=make_alert("No active vote."))
            return
        if not self._is_expeditioner(ctx.author):
            await ctx.send(embed=make_alert("Only an expeditioner can end the vote."))
            return
        await ctx.message.delete()

        text = "Are you sure to end the vote?"
        await ConfirmMessage(ctx, text, None, self._end_vote_cb, ctx, anonymous).init()

    async def _end_vote_cb(self, ctx: commands.Context, anonymous):
        maxDescLen = max(max(map(len, self.options.values())), 6) + 2

        if self.default:
            votedNum = len(self.expeditioners)
            entries = [f"[%-{maxDescLen - 1}s  [Count]  [Vote%%]" % "Option]"]
            template = f"%-{maxDescLen}s   %-2d        %3d%%"
        else:
            votedNum = len(list(filter(bool, self.vote.values())))
            entries = [f"[%-{maxDescLen - 1}s  [Count]  [Vote%%]  [Global%%]" % "Option]"]
            template = f"%-{maxDescLen}s   %-2d        %3d%%       %3d%%"

        for emoji, desc in self.options.items():
            desc = f"<{desc}>"
            count = len(list(filter(lambda v: v == emoji, self.vote.values())))
            if emoji == self.default:
                count += len(list(filter(operator.not_, self.vote.values())))

            votePercent = int(count / votedNum * 100)
            if self.default:
                entries.append(template % (desc, count, votePercent))
            else:
                totalPercent = int(count / len(self.expeditioners) * 100)
                entries.append(template % (desc, count, votePercent, totalPercent))
        
        await ctx.send(decorate_text("\n".join(entries), sh="apache"))

        if not anonymous:
            config: Configuration = self.bot.get_cog("Configuration")
            nameMap = {emoji: set()  for emoji in self.options}
            for id_, emoji in self.vote.items():
                if emoji:
                    name = config.guild.get_member(id_).display_name
                    nameMap[emoji].add(name)
            
            embed = Embed()
            for emoji, names in nameMap.items():
                names = ", ".join(names) if names else "No one"
                embed.add_field(name=self.options[emoji], value=names, inline=False)
            
            await ctx.send(embed=embed)

        self.memberMsg = None
        self.voteMsg = None