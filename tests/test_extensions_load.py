"""Load every enabled extension into a real (but never connected) Bot.

Importing a module isn't enough: command/group/task decorators, cog names and ``setup()`` bodies
only run on load, which is where mistakes like duplicate command names or bad signatures surface.
"""

import discord
import pytest
from discord.ext import commands

import cococap
from cococap.constants import DISABLED_EXTENSIONS
from cococap.exts import __name__ as exts_name  # noqa: F401
from utils.extensions import walk_extensions


@pytest.fixture
async def bot(db):
    bot = commands.Bot(command_prefix="-", intents=discord.Intents.none(), help_command=None)
    bot.mongo = db.client
    previous = cococap.instance
    cococap.instance = bot
    yield bot
    cococap.instance = previous
    await bot.close()


async def test_all_enabled_extensions_load_and_unload(bot):
    enabled = sorted(walk_extensions(cococap.exts) - DISABLED_EXTENSIONS)
    assert enabled, "no extensions discovered"
    helpers = set()
    for name in enabled:
        try:
            await bot.load_extension(name)
        except commands.NoEntryPointError:
            helpers.add(name)  # helper module under exts/; Bot.load_extension tolerates these
    enabled = [name for name in enabled if name not in helpers]
    assert set(bot.extensions) == set(enabled)
    assert bot.tree.get_commands(), "expected slash commands to be registered"
    for name in enabled:
        await bot.unload_extension(name)


async def test_drops_cog_seeds_megadrop_document_on_fresh_database(bot):
    from bson import ObjectId

    await bot.load_extension("cococap.exts.economy.drops")
    doc = await bot.mongo.discordbot.special_entities.find_one({"_id": ObjectId("65b76d73ee9f83c970604935")})
    assert doc is not None and doc["amount"] == 0 and doc["times_missed"] == 0
