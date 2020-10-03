from discord.ext import commands

from logger import Logger
from util.pickleutil import PickleUtil


class SnapshotManager(commands.Cog):

    _cogs = set()

    @classmethod
    def register(cls, class_):
        cls._cogs.add(class_)
        return class_
    
    def make_snapshot(self):
        # for cog in SnapshotManager
        pass