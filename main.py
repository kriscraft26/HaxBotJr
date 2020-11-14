from dotenv import load_dotenv
from os import getenv

from discord import Intents, MemberCacheFlags
# import uvloop

from haxbotjr import HaxBotJr


load_dotenv()
# uvloop.install()


intents: Intents = Intents.none()
intents.guilds = True
intents.members = True
intents.guild_messages = True
intents.guild_reactions = True


haxBotJr = HaxBotJr(command_prefix="]", help_command=None, intents=intents,
                    member_cache_flags=MemberCacheFlags.from_intents(intents))
haxBotJr.run(getenv("BOT_TOKEN"))
haxBotJr.exit()