"""Run every slash command that needs no arguments through discord.py's own check path and its
callback, with a fake interaction. Catches wiring mistakes (like awaiting a non-awaitable) that unit
tests of the game rules can't see. A command may refuse the user (CustomError) but must not crash."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands
from discord.ext import commands

import cococap
import cococap.exts
from cococap.constants import DISABLED_EXTENSIONS
from cococap.errors import CustomError
from utils.extensions import walk_extensions

# Commands that need a real guild/channel/network and are covered elsewhere or can't be faked cheaply.
SKIP = {"explore", "embed", "admin_pay", "tictactoe"}


def fake_interaction(bot):
    inter = MagicMock()
    inter.user = MagicMock(id=1, name="tester", display_name="tester", display_avatar="http://x/a.png")
    inter.user.name = "tester"
    inter.extras = {}
    inter.client = bot
    inter.data = {"options": []}
    inter.response = MagicMock(
        send_message=AsyncMock(), edit_message=AsyncMock(), defer=AsyncMock(), send_modal=AsyncMock(),
        is_done=MagicMock(return_value=False),
    )
    inter.original_response = AsyncMock()
    inter.edit_original_response = AsyncMock()
    inter.followup = MagicMock(send=AsyncMock())
    return inter


@pytest.fixture
async def bot(db):
    bot = commands.Bot(command_prefix="-", intents=discord.Intents.none(), help_command=None)
    previous, cococap.instance = cococap.instance, bot
    for name in sorted(walk_extensions(cococap.exts) - DISABLED_EXTENSIONS):
        try:
            await bot.load_extension(name)
        except commands.NoEntryPointError:
            pass
    yield bot
    cococap.instance = previous
    await bot.close()


def argument_free(command: app_commands.Command) -> bool:
    return all(not p.required for p in command.parameters)


async def test_every_argument_free_command_runs(bot):
    ran = []
    for command in bot.tree.walk_commands():
        if not isinstance(command, app_commands.Command) or command.name in SKIP or not argument_free(command):
            continue
        inter = fake_interaction(bot)
        inter.command = command
        try:
            assert await command._check_can_run(inter) is True, f"/{command.qualified_name} check failed"
            args = [command.binding] if command.binding is not None else []
            kwargs = {  # optional parameters: what Discord passes when the user leaves them blank
                param.name: (None if param.default is discord.utils.MISSING else param.default)
                for param in command.parameters
            }
            await command._callback(*args, inter, **kwargs)
        except CustomError:
            pass  # a friendly refusal is fine
        ran.append(command.qualified_name)
    assert {"play", "profile", "rank", "check-in", "stats", "shop", "mine", "inventory", "top", "megadrop", "settings", "flashcard", "unscramble", "sequence", "trivia"} <= set(ran), ran


async def test_casino_commands_take_the_bet_and_open_the_game_in_the_hub(bot):
    for user_id, name in ((77, "highlow"), (78, "blackjack")):
        command = bot.tree.get_command(name)
        inter = fake_interaction(bot)
        inter.command = command
        inter.user.id = user_id
        inter.user.display_name = "tester"
        inter.user.display_avatar = MagicMock(url="http://x/a.png")
        assert await command._check_can_run(inter) is True
        await command._callback(command.binding, inter, "100")
        view = inter.response.send_message.await_args.kwargs["view"]
        assert view.screen.id == "games" and view.screen.tab == name and view.screen.game.bet == 100, name
