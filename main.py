from dotenv import load_dotenv
from os import getenv

from haxbotjr import HaxBotJr


load_dotenv()


haxBotJr = HaxBotJr(command_prefix="]")
haxBotJr.run(getenv("BOT_TOKEN"))
haxBotJr.exit()