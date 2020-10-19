from inspect import iscoroutinefunction

from discord.ext import commands, tasks

from logger import Logger
from util.pickleutil import PickleUtil


SAVE_INTERVAL = 10  # in minutes

class DataManager(commands.Cog):

    _classes = {}
    _idFuncs = {}
    _mappers = {}

    @classmethod
    def register(cls, *attributes, idFunc=None, mapper=None):
        def decorator(targetCls):
            Logger.bot.debug(f"registered {targetCls} with attributes {attributes}")
            cls._classes[targetCls] = [attributes, set()]
            if idFunc:
                cls._idFuncs[targetCls] = idFunc
            if mapper:
                cls._mappers[targetCls] = mapper
            return targetCls
        return decorator
    
    @classmethod
    def make_data_file_path(cls, obj):
        targetCls = obj.__class__
        id_ = "." + cls._idFuncs[targetCls](obj) if targetCls in cls._idFuncs else ""
        return f"./data/{targetCls.__name__}{id_}.data"

    @classmethod
    async def load(cls, obj):
        targetCls = obj.__class__
        dataFile = cls.make_data_file_path(obj)
        Logger.bot.debug(f"loading {dataFile} into {obj}")

        attrMap = PickleUtil.load(dataFile)
        if attrMap:
            Logger.bot.debug(f"data found: {attrMap}")

            if type(attrMap) != dict:
                Logger.bot.debug(f"outdated data format detected")
                attributes = cls._classes[targetCls][0]
                attrMap = dict(zip(attributes, attrMap))
                Logger.bot.debug(f"-> {attrMap}")

            for attr, val in attrMap.items():
                if hasattr(obj, attr):
                    setattr(obj, attr, val)
                elif attr in cls._mappers.get(targetCls, {}):
                    setattr(obj, cls._mappers[targetCls][attr], val)
                else:
                    Logger.bot.debug(f"failed to load {attr}")
        else:
            Logger.bot.debug(f"data not found")
        
        if hasattr(obj, "__loaded__"):
            cb = getattr(obj, "__loaded__")
            if iscoroutinefunction(cb):
                await cb()
            else:
                cb()
        
        DataManager._classes[targetCls][1].add(obj)
        return obj
    
    def __init__(self, bot):
        self.bot = bot
        self._save_loop.start()

    def save(self):
        for [attributes, instances] in DataManager._classes.values():
            for obj in instances:
                attrMap = {attr: getattr(obj, attr) for attr in attributes \
                    if hasattr(obj, attr)}
                dataFile = self.make_data_file_path(obj)
                Logger.bot.debug(f"saving {obj} {attrMap} into {dataFile}")
                PickleUtil.save(dataFile, attrMap)

    def cog_unload(self):
        self.save()
    
    @tasks.loop(minutes=SAVE_INTERVAL)
    async def _save_loop(self):
        self.save()
    
    @_save_loop.before_loop
    async def _before_save_loop(self):
        await self.bot.wait_until_ready()
        Logger.bot.debug("Starting data saving loop")