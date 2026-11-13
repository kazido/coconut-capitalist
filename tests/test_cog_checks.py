"""Each cog's interaction_check runs before its commands: it loads the user (and for the casino,
takes the bet). discord.py may or may not await the result, so call it the way discord.py does."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from cococap.exts.core.party_system import PartySystemCog
from cococap.exts.core.rank import RanksCog
from cococap.exts.gambling.blackjack import Blackjack
from cococap.exts.gambling.high_low import Highlow
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


@pytest.mark.parametrize("cog_class", [Highlow, Blackjack])
async def test_casino_check_passes_and_takes_the_bet(db, cog_class):
    inter = interaction(bet="250")
    assert await run_check(cog_class(), inter) is True
    assert inter.extras["bet"] == 250
    assert (await User.get(1)).purse == 1000 - 250
    assert await (await User.get(1)).get_stat("highlow_games" if cog_class is Highlow else "blackjack_games") == 1


@pytest.mark.parametrize("cog_class", [Highlow, Blackjack])
async def test_casino_check_rejects_a_bet_bigger_than_the_balance(db, cog_class):
    from cococap.errors import InvalidAmount

    with pytest.raises(InvalidAmount):
        await run_check(cog_class(), interaction(bet="999999"))
    assert (await User.get(1)).purse == 1000  # nothing was taken


async def test_rank_check_loads_rank_and_next_rank(db):
    inter = interaction()
    assert await run_check(RanksCog(), inter) is True
    assert inter.extras["rank"].rank_id == 0 and inter.extras["next_rank"].rank_id == 1


async def test_rank_check_at_max_rank_has_no_next_rank(db):
    user = await User.get(1)
    await set_columns(user, rank=8)
    inter = interaction()
    assert await run_check(RanksCog(), inter) is True and inter.extras["next_rank"] is None


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
