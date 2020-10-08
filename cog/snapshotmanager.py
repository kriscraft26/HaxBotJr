from datetime import timedelta, datetime
from io import StringIO
from pprint import pformat

from discord import File
from discord.ext import commands

from logger import Logger
from msgmaker import make_alert
from util.cmdutil import parser
from util.pickleutil import PickleUtil, pickle
from util.timeutil import now, get_bw_range
from cog.configuration import Configuration


class SnapshotManager(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self._objects = {}
        self._snapCache = {}

        self._config: Configuration = bot.get_cog("Configuration")
    
    def add(self, id_, obj):
        self._objects[id_] = obj
    
    def make_snapshot_path(self, snapId):
        return f"./snapshot/{snapId}.snapshot"
    
    def make_snapshot_id(self, date):
        lower, upper = get_bw_range(date)
        return lower.strftime("%Y.%m.%d-") + upper.strftime("%Y.%m.%d")
    
    def save_snapshot(self, offset=True):
        snapId = self.make_snapshot_id(now().date() - timedelta(days=offset))
        Logger.bot.debug(f"Saving snapshot with id {snapId}")
        snapshot = self.make_snapshot()
        self._snapCache[snapId] = snapshot
        PickleUtil.save(self.make_snapshot_path(snapId), snapshot)
        return snapId
    
    def make_snapshot(self):
        return {id_: obj.__snap__() for id_, obj in self._objects}
    
    async def get_snapshot(self, ctx: commands.Context, index: str):
        if index.isnumeric():
            index = int(index)
            snapId = self.make_snapshot_id(now().date() - timedelta(days=14 * index))
        else:
            index = index.replace("/", ".")
            if "-" in index:
                snapId = index
            else:
                try:
                    snapId = self.make_snapshot_id(
                        datetime.strptime(index, "%Y.%m.%d").date())
                except:
                    alert = make_alert(f"bad snapshot index format")
                    await ctx.send(embed=alert)
                    return

        if snapId in self._snapCache:
            return self._snapCache[snapId]

        try:
            with open(self.make_snapshot_path(snapId), "rb") as f:
                snapshot = pickle.load(f)
        except FileNotFoundError:
            alert = make_alert(f"Snapshot with id {snapId} doesn't exist")
            await ctx.send(embed=alert)
            return

        self._snapCache[snapId] = snapshot
        return snapshot
    
    @parser("snap", isGroup=True)
    async def display_snapshots(self, ctx: commands.Context):
        await ctx.send("not implemented uwu")

    @parser("snap forcemake", parent=display_snapshots)
    async def force_make_snapshot(self, ctx: commands.Context):
        if not await self._config.perm_check(ctx, "user.dev"):
            return
        snapId = self.save_snapshot(offset=False)
        ctx.send(f"Snapshot saved with the id {snapId}")
    
    @parser("snap data", "index", parent=display_snapshots)
    async def get_snapshot_data(self, ctx: commands.Context, index: str):
        if not await self._config.perm_check(ctx, "user.dev"):
            return
        snapshot = await self.get_snapshot(ctx, index)
        if not snapshot:
            return
        await ctx.send(file=File(StringIO(pformat(snapshot)), filename="snapshot.txt"))