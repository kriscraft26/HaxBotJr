from random import choice, randrange
from math import trunc
from datetime import datetime, timedelta

from discord import Message, TextChannel, AllowedMentions
from discord.ext import commands
from discord.utils import find

from util.cmdutil import parser
from cog.configuration import Configuration


class Misc(commands.Cog):

    def __init__(self, bot: commands.Bot):
        config: Configuration = bot.get_cog("Configuration")

        self.quoteChannel: TextChannel  = find(
            lambda c: c.name == "hax-quotes", config.guild.channels)
        self.quoteTimeMin = datetime(year=2020, month=7, day=19)

    @parser("quote", ["image"])
    async def quote(self, ctx: commands.Context, image, i=1):
        if not self.quoteChannel:
            return

        curr = datetime.now()
        dt = curr - self.quoteTimeMin
        randDt = randrange(0, trunc(dt.total_seconds()))
        target = curr - timedelta(seconds=randDt)

        messages = await self.quoteChannel.history(limit=100, around=target).flatten()
        if not messages:
            await ctx.send("failed.")

        if image:
            messages = list(filter(lambda m: m.attachments, messages))
            if not messages:
                if i == 3:
                    await ctx.send("unable to find an image :( try again")
                else:
                    await self.quote.restart(ctx, image, i=i+1)
                return
        msg: Message = choice(messages)

        files = []
        for attachment in msg.attachments:
            files.append(await attachment.to_file())

        embedNum = len(msg.embeds)
        mention = AllowedMentions(everyone=False, users=False, roles=False)
        
        if embedNum == 1:
            await ctx.send(content=msg.content, files=files, embed=msg.embeds[0], 
                allowed_mentions=mention)
        else:
            await ctx.send(content=msg.content, files=files, allowed_mentions=mention)
            if embedNum:
                for embed in msg.embeds:
                    await ctx.send(embed=embed)