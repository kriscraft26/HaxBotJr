from random import choice

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

    @parser("quote")
    async def quote(self, ctx: commands.Context):
        if not self.quoteChannel:
            return

        messages = await self.quoteChannel.history(limit=500).flatten()
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