from logger import Logger
from util.pickleutil import PickleUtil


class State:

    registry = {}

    @classmethod
    def register(cls, *attributes):
        def wrapper(targetCls):
            cls.registry[targetCls] = attributes
            return targetCls
        return wrapper
    
    @classmethod
    def make_file_path(cls, targetCls):
        return f"./data/{targetCls.__name__}.data"

    @classmethod
    async def load(cls, targetCls):
        dataFile = cls.make_file_path(targetCls)
        Logger.bot.debug(f"Loading {dataFile}")

        attrMap = PickleUtil.load(dataFile)
        if attrMap:
            Logger.bot.debug(f"data found: {attrMap}")

            for attr, val in attrMap.items():
                if hasattr(targetCls, attr):
                    setattr(targetCls, attr, val)
        else:
            Logger.bot.debug(f"data not found")
        
        if hasattr(targetCls, "__loaded__"):
            await getattr(targetCls, "__loaded__")()
    
    @classmethod
    def save(cls):
        for targetCls, attributes in cls.registry.items():
            attrMap = {attr: getattr(targetCls, attr) for attr in attributes \
                if hasattr(targetCls, attr)}
            dataFile = cls.make_file_path(targetCls)
            Logger.bot.debug(f"saving {dataFile} with {attrMap}")
            PickleUtil.save(dataFile, attrMap)