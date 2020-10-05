import os
import gzip
import zipfile
from pprint import pformat
from io import StringIO, BytesIO

from discord import File, Message
from discord.ext import commands

from logger import DEBUG_FILE, ARCHIVE_FOLDER
from msgmaker import *
from reactablemessage import ListSelectionMessage, ReactableMessage
from util.cmdutil import parser
from util.pickleutil import PickleUtil
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
        await ListSelectionMessage(ctx, self.archives, self.send_archive_cb).init()
    
    async def send_archive_cb(self, msg: ReactableMessage, fileName):
        with gzip.open(os.path.join(ARCHIVE_FOLDER, fileName), "r") as f:
            await msg.msg.channel.send(file=File(f, filename=fileName[:-3]))

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
    
    @parser("debug rawdata", parent=debug_root)
    async def get_raw_data(self, ctx: commands.Context):
        f = BytesIO()
        zFile = zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED)

        for fileName in os.listdir("./data/"):
            if fileName.endswith(".data"):
                zFile.write("./data/" + fileName, fileName)
        
        zFile.close()
        f.seek(0)
        await ctx.send(file=File(f, filename=f"raw_data.zip"))
        
    def search_archives(self):
        debugChecker = lambda f: f.startswith("debug") and f.endswith(".log.gz")
        self.archives = list(filter(debugChecker, os.listdir(ARCHIVE_FOLDER)))
        self.archives.sort()
    
    async def cog_check(self, ctx: commands.Context):
        return await self._config.perm_check(ctx, "user.dev")