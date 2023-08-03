import asyncio
import discord
import src
import os

from discord.ext import commands
from pydis_core import StartupError
from src import constants
from src.bot import Bot
from logging import getLogger

log = getLogger(__name__)
log.setLevel(10)


async def main():
    intents = discord.Intents.all()
    intents.message_content = True
    intents.presences = False
    intents.dm_typing = False
    intents.dm_reactions = False
    intents.invites = False
    intents.webhooks = False
    intents.integrations = False

    src.instance = Bot(
        guild_id=constants.DiscordGuilds.PRIMARY_GUILD.value,
        command_prefix=commands.when_mentioned_or(constants.BOT_PREFIX),
        activity=discord.Game(name=f"Commands: {constants.BOT_PREFIX}help"),
        case_insensitive=True,
        max_messages=10_000,
        allowed_mentions=discord.AllowedMentions(everyone=False),
        intents=intents,
        strip_after_prefix=True,
        allowed_roles=None,
        http_session=None,
    )
    src.instance.remove_command("help")

    async with src.instance as _bot:
        log.info(f"Bot starting in {os.getcwd()}")
        await _bot.start(constants.TOKEN, reconnect=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except StartupError as e:
        message = "Unknown Startup Error Occurred."
    except KeyboardInterrupt:
            log.critical("Bot shutting down due to manual interrupt.")
