import os
import re

from discord import Member
from discord.ext import commands

from msgmaker import decorate_text, make_alert, COLOR_INFO
from util.cmdutil import parser
from cog.configuration import Configuration


HELP_FOLDER = "./help/"


class Help(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self._config: Configuration = bot.get_cog("Configuration")

        self.permChecks = {
            "S": lambda m: self._config.is_of_group("staff", m),
            "T": lambda m: self._config.is_of_group("trusted", m),
            "E": lambda m: self._config.has_role("expedition", m),
            "R": lambda m: self._invite_perm_check(m)
        }
    
    def _invite_perm_check(self, m: Member):
        rank = self._config.get_rank(m)
        if not rank:
            return False
        rank = rank[0]
        return rank not in ["MoonWalker", "Cadet"]

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

            [title, text, *fields, subtext] = text.split("\n\n\n")

            title = "" if title == "NONE" else title
            text = "" if text == "NONE" else text
            subtext = "" if subtext == "NONE" else subtext

            embed = make_alert(text, title=title, subtext=subtext, color=COLOR_INFO)
            for field in fields:
                sections = field.split("=")

                if cmd:
                    [fName, fVal] = sections
                else:
                    [fPerm, fName, fVal] = sections
                    if fPerm and not self.permChecks[fPerm](ctx.author):
                        continue

                    for perm, checker in self.permChecks.items():
                        pattern = perm + r"(`.+\n?)"
                        match = list(re.finditer(pattern, fVal))
                        if match:
                            rep = r"\1" if checker(ctx.author) else ""
                            fVal = re.sub(pattern, rep, fVal)
                
                embed.add_field(name=fName, value=fVal.strip(), inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("🔫 **there are no help** for `" + " ".join(cmd) + "`")