import logging
import os
import gzip
from colorama import *
from queue import Queue
from sys import stdout

from util.pickleutil import PickleUtil
from util.timeutil import now


LOG_FOLDER = "./log/"
ARCHIVE_FOLDER = "./log/archive/"
LOG_FILE = LOG_FOLDER + "latest.log"
DEBUG_FILE = LOG_FOLDER + "debug.log"
META_FILE = LOG_FOLDER + "meta"

MAX_DEBUG_ARCHIVE = 5


# init()
COLORS = {
    logging.INFO: Back.BLUE,
    logging.WARNING: Back.YELLOW,
    logging.ERROR: Back.RED,
    logging.CRITICAL: Back.RED
}


statusLog = {"WARNING": set(), "ERROR": 0, "CRITICAL": 0}
IGNORED_WARN = [
    "PyNaCl is not installed, voice will NOT be supported",
    "Shard ID None has stopped responding to the gateway. Closing and restarting."
]


class CustomTermFormatter(logging.Formatter):

    def __init__(self):
        super().__init__(fmt=f"%(asctime)s %(levelname)s %(message)s",
            datefmt="%H:%M:%S")

    def format(self, record: logging.LogRecord):
        s = super().format(record)
        if record.levelno == logging.WARNING:
            if record.message not in IGNORED_WARN:
                statusLog["WARNING"].add(record.message)
        elif record.levelno != logging.INFO:
            statusLog[record.levelname] += 1
        print(s, end="")
        return ""

    def formatTime(self, record, datefmt):
        s = super().formatTime(record, datefmt)
        levelColor = COLORS[record.levelno]
        return f"{Style.BRIGHT}{Back.WHITE}{Fore.BLACK} {s} {Fore.LIGHTWHITE_EX}{levelColor}"


formatter = logging.Formatter(fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s", 
    datefmt="%H:%M:%S")

infoHandler = logging.FileHandler(filename=LOG_FILE, mode="w", encoding="utf-8")
infoHandler.setFormatter(formatter)
infoHandler.setLevel(logging.INFO)

debugHandler = logging.FileHandler(filename=DEBUG_FILE, mode="w", encoding="utf-8")
debugHandler.setFormatter(formatter)
debugHandler.setLevel(logging.DEBUG)

termHandler = logging.StreamHandler(stream=stdout)
termHandler.setFormatter(formatter)
termHandler.setLevel(logging.INFO)

discordLogger = logging.getLogger("discord")
discordLogger.setLevel(logging.INFO)
discordLogger.addHandler(infoHandler)
discordLogger.addHandler(debugHandler)
discordLogger.addHandler(termHandler)

backoffLogger = logging.getLogger("backoff")
backoffLogger.addHandler(infoHandler)
backoffLogger.addHandler(debugHandler)
backoffLogger.addHandler(termHandler)


class LoggerPair:

    def __init__(self, name):
        self._infoLogger = logging.getLogger("HaxBotJr." + name)
        self._infoLogger.setLevel(logging.INFO)

        self._debugLogger = logging.getLogger("HaxBotJr.debug." + name)
        self._debugLogger.setLevel(logging.DEBUG)

    def _add_handler(self):
        self._infoLogger.addHandler(infoHandler)
        self._infoLogger.addHandler(debugHandler)
        self._infoLogger.addHandler(termHandler)

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
    em = LoggerPair("em")

    @classmethod
    def init(cls):
        cls.bot._add_handler()
        cls.war._add_handler()
        cls.guild._add_handler()
        cls.xp._add_handler()
        cls.em._add_handler()

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
        
        debugArchiveName = "debug-" + archiveName
        cls._archive_file(DEBUG_FILE, ARCHIVE_FOLDER + debugArchiveName)
        archivedDebugs.append(debugArchiveName)

        if today == logDate:
            logVersion += 1
        else:
            logVersion = 0

        PickleUtil.save(META_FILE, (today, logVersion, archivedDebugs))

        return archiveName, debugArchiveName
    
    @classmethod
    def reset(cls):
        archiveNames = cls.archive_logs()

        infoHandler.close()
        with open(LOG_FILE, "w") as f:
            f.write("")

        debugHandler.close()
        with open(DEBUG_FILE, "w") as f:
            f.write("")
        
        cls._create_meta()

        return archiveNames

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