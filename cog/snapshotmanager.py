from discord.ext import commands

from logger import Logger
from util.pickleutil import PickleUtil
from util.timeutil import now


class SnapshotManager(commands.Cog):

    def __init__(self):
        self._objects = {}
        self._snapCache = {}
    
    def add(self, id_, obj):
        self._objects[id_] = obj
    
    def save_snapshot(self):
        snapId = now().date().strftime("%Y-%m-%d")
    
    def make_snapshot(self):
        return {id_: obj.__snap__() for id_, obj in self._objects}