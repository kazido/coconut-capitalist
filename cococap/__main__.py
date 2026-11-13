import argparse
import asyncio
import logging
import os
import sys

import discord
from discord.ext import commands

import cococap
from cococap import constants
from cococap.bot import Bot, StartupError

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser("Run the discord bot.")
    parser.add_argument("--drops", action="store_true", help="run the bot with drops enabled")
    return parser.parse_args(argv)


def build_intents() -> discord.Intents:
    # Privileged intents (members, message content) must also be enabled in the developer portal.
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return intents


async def main(argv: list[str] | None = None) -> None:
    constants.require_secrets()  # fail fast with a readable message instead of a login traceback
    cococap.args = parse_args(argv)

    cococap.instance = Bot(
        guild_id=constants.GUILD_ID,
        command_prefix=commands.when_mentioned_or(constants.BOT_PREFIX),
        activity=discord.Game(name=f"Commands: {constants.BOT_PREFIX}help"),
        case_insensitive=True,
        max_messages=10_000,
        allowed_mentions=discord.AllowedMentions(everyone=False),
        intents=build_intents(),
        strip_after_prefix=True,
        allowed_roles=None,
        http_session=None,
        help_command=None,  # a custom help command is used instead of discord.py's default
    )

    async with cococap.instance as bot:
        log.info("Bot starting in %s", os.getcwd())
        await bot.start(constants.TOKEN, reconnect=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.critical("Bot shutting down due to manual interrupt.")
    except discord.LoginFailure:
        print("Startup failed: Discord rejected BOT_TOKEN. Reset it in the developer portal.", file=sys.stderr)
        sys.exit(1)
    except (StartupError, RuntimeError) as e:
        print(f"Startup failed: {e}", file=sys.stderr)
        sys.exit(1)
