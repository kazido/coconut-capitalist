import asyncio
from datetime import datetime
import os
from pprint import pprint

# discord imports
import discord
from discord.ext import commands
from discord import app_commands
from pydis_core import StartupError

# file imports
import src
from src import exts, constants
from src.bot import Bot
from src.utils.extensions import walk_extensions


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
        http_session=None
    )
    src.instance.remove_command('help')

    async with src.instance as _bot:
        await _bot.start(constants.TOKEN, reconnect=True)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except StartupError as e:
        message = "Unknown Startup Error Occurred."
