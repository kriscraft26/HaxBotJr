import logging
import os
import gzip
from queue import Queue

from util.pickleutil import PickleUtil
from util.timeutil import now


LOG_FOLDER = "./log/"
ARCHIVE_FOLDER = "./log/archive/"
LOG_FILE = LOG_FOLDER + "latest.log"
DEBUG_FILE = LOG_FOLDER + "debug.log"
META_FILE = LOG_FOLDER + "meta"

MAX_DEBUG_ARCHIVE = 5


formatter = logging.Formatter(fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s", 
    datefmt="%H:%M:%S")

infoHandler = logging.FileHandler(filename=LOG_FILE, mode="w", encoding="utf-8")
infoHandler.setFormatter(formatter)
infoHandler.createLock()

debugHandler = logging.FileHandler(filename=DEBUG_FILE, mode="w", encoding="utf-8")
debugHandler.setFormatter(formatter)
debugHandler.createLock()

discordLogger = logging.getLogger("discord")
discordLogger.setLevel(logging.INFO)
discordLogger.addHandler(infoHandler)
discordLogger.addHandler(debugHandler)


discordLogPipe = Queue()


class LoggerPair:

    def __init__(self, name):
        self._infoLogger = logging.getLogger("HaxBotJr." + name)
        self._infoLogger.setLevel(logging.INFO)

        self._debugLogger = logging.getLogger("HaxBotJr.debug." + name)
        self._debugLogger.setLevel(logging.DEBUG)

    def _add_handler(self):
        self._infoLogger.addHandler(infoHandler)
        self._infoLogger.addHandler(debugHandler)

        self._debugLogger.addHandler(debugHandler)

    def debug(self, msg, *args, **kwargs):
        self._debugLogger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._infoLogger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._infoLogger.warning(msg, *args, **kwargs)

    def error(self, *args, **kwargs):
        self._infoLogger.error(*args, **kwargs)

    def critical(self, *args, **kwargs):
        self._infoLogger.critical(*args, **kwargs)


class Logger:

    bot = LoggerPair("bot")
    war = LoggerPair("war")
    guild = LoggerPair("guild")
    xp = LoggerPair("xp")

    @classmethod
    def init(cls):
        cls.bot._add_handler()
        cls.war._add_handler()
        cls.guild._add_handler()
        cls.xp._add_handler()

        cls._create_meta()

    @classmethod
    def archive_logs(cls):
        today = now().date()

        (logDate, logVersion, archivedDebugs) = PickleUtil.load(META_FILE)
        archiveName = f"{logDate.strftime('%Y-%m-%d')}.{logVersion}.log.gz"

        cls._archive_file(LOG_FILE, ARCHIVE_FOLDER + archiveName)
        
        if len(archivedDebugs) >= MAX_DEBUG_ARCHIVE:
            [delete, *archivedDebugs] = archivedDebugs
            os.remove(ARCHIVE_FOLDER + delete)
        
        cls._archive_file(DEBUG_FILE, ARCHIVE_FOLDER + "debug-" + archiveName)
        archivedDebugs.append("debug-" + archiveName)

        if today == logDate:
            logVersion += 1
        else:
            logVersion = 0

        PickleUtil.save(META_FILE, (today, logVersion, archivedDebugs))
    
    @classmethod
    def reset(cls):
        cls.archive_logs()

        infoHandler.close()
        with open(LOG_FILE, "w") as f:
            f.write("")

        debugHandler.close()
        with open(DEBUG_FILE, "w") as f:
            f.write("")
        
        cls._create_meta()

    @staticmethod
    def _create_meta():
        today = now().date()
        todayFormatted = today.strftime('%Y-%m-%d')
        archivedDebugs = []
        logVersion = 0

        for file in os.listdir(ARCHIVE_FOLDER):
            if file.startswith(todayFormatted):
                version = int(file.split(".")[1])
                if version >= logVersion:
                    logVersion = version + 1
            elif file.startswith("debug") and file.endswith(".log.gz"):
                archivedDebugs.append(file)
        
        PickleUtil.save(META_FILE, (today, logVersion, sorted(archivedDebugs)))

    @staticmethod
    def _archive_file(target, dest):
        Logger.bot.debug(f"archived {target} to {dest}")
        with open(target, "rb") as logFile:
            data = bytearray(logFile.read())
            with gzip.open(dest, "wb") as archiveFile:
                archiveFile.write(data)