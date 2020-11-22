from typing import Dict
from asyncio import sleep
import operator

from discord import Message, Emoji, Embed

from msgmaker import make_alert, COLOR_INFO, decorate_text
from util.discordutil import Discord


NUMBER_EMOJIS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


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

    def make_member_embed(self, expeditioners) -> Embed:
        names = set()

        votedCount = 0
        for id_ in expeditioners:
            name = Discord.guild.get_member(id_).display_name.split(" ")[-1]
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
    
    async def add_expeditioner(self, id_):
        self.vote[id_] = None
        await self.update_member_msg()
    
    async def remove_expeditioner(self, id_):
        del self.vote[id_]
        await self.update_member_msg()

    async def update_member_msg(self):
        embed = self.make_member_embed(list(self.vote.keys()))
        msg = await Discord.Channels.expedition.fetch_message(self.memberMsg)
        await msg.edit(embed=embed)
    
    async def refresh(self, expeditioners):
        msg = await Discord.Channels.expedition.fetch_message(self.memberMsg)
        await msg.delete()
        msg = await Discord.Channels.expedition.fetch_message(self.voteMsg)
        await msg.delete()
        
        await self._send_messages(expeditioners)
    
    async def _send_messages(self, expeditioners):
        msg = await Discord.Channels.expedition.send(
            embed=self.make_member_embed(expeditioners))
        self.memberMsg = msg.id
        msg = await Discord.Channels.expedition.send(embed=self.make_vote_embed())
        self.voteMsg = msg.id

        for emoji in self.options:
            await msg.add_reaction(emoji)
            await sleep(0.25)
        
        await msg.pin(reason="Vote message.")

    async def start(self, expeditioners):
        self.vote = {id_: None for id_ in expeditioners}
        await self._send_messages(expeditioners)
    
    def should_auto_end(self):
        if not self.target:
            return False
        for emoji in self.options:
            count = len(list(filter(lambda v: v == emoji, self.vote.values())))
            totalPercent = int(count / len(self.vote) * 100)
            if totalPercent >= self.target:
                return True
        return False
    
    async def end(self, anonymous):
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
        
        await Discord.Channels.expedition.send(
            decorate_text("\n".join(entries), sh="apache"))

        if not anonymous:
            nameMap = {emoji: set()  for emoji in self.options}
            for id_, emoji in self.vote.items():
                if emoji:
                    name = Discord.guild.get_member(id_).display_name.split(" ")[-1]
                    nameMap[emoji].add(name)
            
            embed = Embed()
            for emoji, names in nameMap.items():
                names = ", ".join(names) if names else "No one"
                embed.add_field(name=self.options[emoji], value=names)
            
            await Discord.Channels.expedition.send(embed=embed)
        
        message = await Discord.Channels.expedition.fetch_message(self.voteMsg)
        await message.delete()
    
    async def check(self, ctx):
        if self.default and self.default not in self.options:
            await ctx.send(embed=make_alert("Default isn't part of options."))
            return
        return True

    async def set_vote(self, id_, emoji):
        self.vote[id_] = emoji
        await self.update_member_msg()


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
    
    async def start(self, expeditioners):
        self.default = \
            NUMBER_EMOJIS[self.options.index(self.default)] if self.default else None
        self.options = {NUMBER_EMOJIS[i]: s for i, s in enumerate(self.options)}
        await super().start(expeditioners)
    
    async def add_option(self, option):
        if len(self.options) == 10:
            await Discord.Channels.expedition.send(embed=make_alert("Can't add more option."))
            return
        
        emoji = NUMBER_EMOJIS[len(self.options)]
        self.options[emoji] = option
        
        msg: Message = await Discord.Channels.expedition.fetch_message(self.voteMsg)
        await msg.add_reaction(emoji)
        await msg.edit(embed=self.make_vote_embed())
        
        return True
    
    async def remove_option(self, option):
        if option not in self.options.values():
            await Discord.Channels.expedition.send("There are no such option.")
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

        msg: Message = await Discord.Channels.expedition.fetch_message(self.voteMsg)
        await msg.remove_reaction(emoji, msg.author)
        await msg.edit(embed=self.make_vote_embed())

        await self.update_member_msg()

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