from typing import Dict, List, Tuple

from discord.ext import tasks, commands

from util.pickleutil import PickleUtil
from logger import Logger


SAVE_INTERVAL = 10

class DataCog:

    _subClasses = {}
    _bot: commands.Bot = None

    @classmethod
    def init(cls, bot: commands.Bot):
        cls._bot = bot

    @classmethod
    def register(cls, *attributes):
        def decorator(class_):
            Logger.bot.debug(f"{class_} registered as data cog with attributes {attributes}")
            cls._subClasses[class_] = [attributes, None]
            return class_
        return decorator
    
    @classmethod
    def _get_data_file(cls, targetCls: type) -> str:
        return f"./data/{targetCls.__name__}.data"
    
    @classmethod
    def load(cls, targetCls: type, *args, **kwargs) -> commands.Cog:
        Logger.bot.debug(f"loading data cog {targetCls}")
        data = PickleUtil.load(cls._get_data_file(targetCls))

        cog = targetCls(*args, **kwargs)
        cls._subClasses[targetCls][1] = cog

        loadCb = getattr(cog, "__loaded__", lambda: 0)

        if not data:
            Logger.bot.debug(f"No data file found for data cog {targetCls}")
            loadCb()
            return cog
        
        attributes = cls._subClasses[targetCls][0]
        attrMap = list(zip(attributes, data))
        Logger.bot.debug(f"Data file found for data cog {targetCls}: {list(attrMap)}")

        for attr, val in attrMap:
            setattr(cog, attr, val)
        loadCb()

        return cog
    
    @classmethod
    def save(cls):
        for class_, [attributes, instance] in cls._subClasses.items():
            values = list(map(lambda attr: getattr(instance, attr), attributes))
            PickleUtil.save(cls._get_data_file(class_), values)

    def start_saving_loop(self):
        self._save_loop.start()

    @tasks.loop(seconds=SAVE_INTERVAL)
    async def _save_loop(self):
        DataCog.save()
    
    @_save_loop.before_loop
    async def _before_save_loop(self):
        Logger.bot.debug("Starting data saving loop")