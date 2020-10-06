import os
import gzip
import zipfile
from pprint import pformat
from io import StringIO, BytesIO
from typing import List

from discord import File, Message
from discord.ext import commands

from logger import DEBUG_FILE, ARCHIVE_FOLDER, LOG_FILE
from msgmaker import *
from reactablemessage import ListSelectionMessage, ReactableMessage
from util.cmdutil import parser
from util.pickleutil import PickleUtil
from cog.configuration import Configuration


class RemoteDebugger(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.debugArchives = []
        self.infoArchives = []

        self._config: Configuration = bot.get_cog("Configuration")

        self._search_archives()

    @parser("debug", isGroup=True)
    async def debug_root(self, ctx: commands.Context):
        pass

    @parser("debug log", ["info"], parent=debug_root)
    async def get_log(self, ctx: commands.Context, info):
        await ctx.send(file=File(LOG_FILE if info else DEBUG_FILE))
    
    @parser("debug archives", ["info"], parent=debug_root)
    async def list_archives(self, ctx: commands.Context, info):
        archives = self.infoArchives if info else self.debugArchives
        await ListSelectionMessage(ctx, archives, self.send_archive_cb).init()
    
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
        
    def _search_archives(self):
        files = filter(lambda f: f.endswith(".log.gz"), os.listdir(ARCHIVE_FOLDER))
        for f in files:
            if f.startswith("debug"):
                self.debugArchives.append(f)
            else:
                self.infoArchives.append(f)
        self.debugArchives.sort(key=self._sort_archives_key)
        self.infoArchives.sort(key=self._sort_archives_key)
        
    def _sort_archives_key(self, archive: str):
        [date, version, *_] = archive.split(".")
        [year, month, day] = list(map(int, date.split("-")[-3:]))
        return int(version) + day * 1000 + month * 100000 + year * 10000000
    
    def add_archives(self, infoArchiveName, debugArchiveName):
        self.infoArchives.append(infoArchiveName)
        self.debugArchives.append(debugArchiveName)
    
    async def cog_check(self, ctx: commands.Context):
        return await self._config.perm_check(ctx, "user.dev")