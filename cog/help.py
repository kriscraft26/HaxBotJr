import os
import re

from discord.ext import commands

from msgmaker import decorate_text, make_alert, COLOR_INFO
from util.cmdutil import parser
from cog.configuration import Configuration


HELP_FOLDER = "./help/"


class Help(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.patterns = {
            "trusted": re.compile(r"(T#([^#]+)#)"),
            "staff": re.compile(r"(S#([^#]+)#)")
        }

        self._config: Configuration = bot.get_cog("Configuration")

    @parser("help", "cmd*")
    async def get_help(self, ctx: commands.Context, cmd):
        if cmd:
            f = "-".join(cmd)
        else:
            f = "DEFAULT"
        f = HELP_FOLDER + f + ".txt"

        if os.path.isfile(f):
            with open(f, "r") as helpFile:
                text = "".join(helpFile.readlines())

            for group, pattern in self.patterns.items():
                match = list(pattern.finditer(text))
                if match:
                    rep = r"\2" if self._config.is_of_group(group, ctx.author) else ""
                    text = pattern.sub(rep, text)

            [title, text, *fields, subtext] = text.split("\n\n\n")

            title = "" if title == "NONE" else title
            text = "" if text == "NONE" else text
            subtext = "" if subtext == "NONE" else subtext

            embed = make_alert(text, title=title, subtext=subtext, color=COLOR_INFO)
            for field in fields:
                [fName, fVal] = field.split("=")
                embed.add_field(name=fName, value=fVal.strip(), inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("🔫 **there are no help** for `" + " ".join(cmd) + "`")