import os
import gzip
from pprint import pformat
from io import StringIO

from discord import File, Message
from discord.ext import commands

from logger import DEBUG_FILE, ARCHIVE_FOLDER
from msgmaker import *
from util.cmdutil import parser
from util.pickleutil import PickleUtil
from cog.datacog import DataCog
from cog.configuration import Configuration


class RemoteDebugger(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.archives = []

        self._config: Configuration = bot.get_cog("Configuration")

    @parser("debug", isGroup=True)
    async def debug_root(self, ctx: commands.Context):
        pass

    @parser("debug log", parent=debug_root)
    async def get_log(self, ctx: commands.Context):
        await ctx.send(file=File(DEBUG_FILE))
    
    @parser("debug archives", parent=debug_root)
    async def list_archives(self, ctx: commands.Context):
        if not self.archives:
            self.search_archives()
        text = "\n".join([f"[{i}] {f}" for i, f in enumerate(self.archives)])
        await ctx.send(decorate_text(text))
    
    @parser("debug archive", "index", parent=debug_root)
    async def get_archive(self, ctx: commands.Context, index):
        if not self.archives:
            self.search_archives()

        if not index.isnumeric() or int(index) >= len(self.archives):
            alert = make_alert("Invalid archive index", 
                subtext="use `]debug archives` to get archive indices.")
            await ctx.send(embed=alert)
            return
        
        archiveFile = self.archives[int(index)]
        with gzip.open(os.path.join(ARCHIVE_FOLDER, archiveFile), "r") as f:
            await ctx.send(file=File(f, filename=archiveFile[:-3]))

    @parser("debug data", "dataName", parent=debug_root)
    async def get_data(self, ctx: commands.Context, dataName):
        fileName = f"./data/{dataName}.data"
        data = PickleUtil.load(fileName)

        if not data:
            alert = make_alert("Data doesn't exist")
            await ctx.send(embed=alert)
            return
        
        f = StringIO(pformat(data))
        await ctx.send(file=File(f, filename=f"{dataName}.data.txt"))
        
    def search_archives(self):
        debugChecker = lambda f: f.startswith("debug") and f.endswith(".log.gz")
        self.archives = list(filter(debugChecker, os.listdir(ARCHIVE_FOLDER)))
        self.archives.sort()
    
    async def cog_check(self, ctx: commands.Context):
        isStaff = self._config.is_of_group(self._config.staffGroup, ctx.author)
        if not isStaff:
            staffGroup = ", ".join(self._config.staffGroup.val)
            alert = make_alert("You have no permission to use this command",
                subtext=f"only {staffGroup} can use it")
            await ctx.send(embed=alert)
        return isStaff