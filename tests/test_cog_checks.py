"""Each cog's interaction_check runs before its commands: it loads the user (and for the casino,
takes the bet). discord.py may or may not await the result, so call it the way discord.py does."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from cococap.exts.core.party_system import PartySystemCog
from cococap.user import User
from tests.conftest import set_columns
from utils.base_cog import BaseCog


def interaction(user_id=1, bet=None):
    options = [{"name": "bet", "value": bet}] if bet is not None else []
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id, name="tester", display_name="tester", display_avatar="http://x/a.png"),
        data={"options": options},
        extras={},
        response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()),
    )


async def run_check(cog, inter):
    return await discord.utils.maybe_coroutine(cog.interaction_check, inter)


async def test_party_check_loads_party_for_members_only(db):
    from cococap.exts.core.party_system import Party

    cog = PartySystemCog(bot=None)
    inter = interaction(1)
    assert await run_check(cog, inter) is True and inter.extras["party"] is None
    await Party.create(1)
    inter = interaction(1)
    await run_check(cog, inter)
    assert inter.extras["party"].owner == 1


async def test_base_cog_attaches_the_user(db):
    inter = interaction(5)
    assert await run_check(BaseCog(), inter) is True
    assert inter.extras["user"].id == 5
