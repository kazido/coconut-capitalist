import pytest

from cococap.registry import get_registry
from cococap.services import rewards
from cococap.services.rewards import ExchangeError, exchange_bits, pay_minigame, with_streak
from cococap.user import User
from tests.conftest import set_columns

RULES = get_registry().economy


def test_streak_bonus_grows_and_is_capped():
    assert with_streak(10, 1) == (10, 0)
    assert with_streak(10, 2)[0] == 11 and with_streak(10, 5)[0] == 14
    top = RULES.minigames.streak_bonus_max_steps
    assert with_streak(10, 1000) == with_streak(10, top + 1)  # no runaway multiplier


async def test_new_players_start_with_luckbucks(db):
    assert (await User.get(1)).luckbucks == RULES.starting_luckbucks


async def test_minigame_wins_pay_luckbucks_never_bits(db):
    user = await User.get(1)
    reward = await pay_minigame(user, 10, streak=1)
    assert reward.granted == 10 and not reward.capped
    assert user.luckbucks == 110 and user.purse == 1000
    assert await user.get_stat("luckbucks_earned") == 10


async def test_spamming_minigames_hits_the_daily_cap(db):
    user = await User.get(1)
    cap = RULES.minigames.daily_cap
    total = 0
    for _ in range(100):  # a player grinding trivia all day
        total += (await pay_minigame(user, 10, streak=1)).granted
    assert total == cap and user.luckbucks == RULES.starting_luckbucks + cap
    last = await pay_minigame(user, 10)
    assert last.granted == 0 and last.capped


async def test_cap_trims_the_last_reward_then_resets_the_next_day(db):
    user = await User.get(1)
    cap = RULES.minigames.daily_cap
    assert await user.grant_daily_capped("minigames", "luckbucks", cap - 5, cap, day=100) == cap - 5
    assert await user.grant_daily_capped("minigames", "luckbucks", 50, cap, day=100) == 5  # trimmed
    assert await user.grant_daily_capped("minigames", "luckbucks", 50, cap, day=100) == 0
    assert await user.grant_daily_capped("minigames", "luckbucks", 50, cap, day=101) == 50  # new day


async def test_concurrent_wins_cannot_exceed_the_cap(db):
    import asyncio

    await User.get(1)
    handles = [await User.get(1) for _ in range(30)]
    results = await asyncio.gather(*(pay_minigame(h, 50) for h in handles))
    assert sum(r.granted for r in results) == RULES.minigames.daily_cap


async def test_caps_are_per_player_and_per_key(db):
    a, b = await User.get(1), await User.get(2)
    cap = RULES.minigames.daily_cap
    await a.grant_daily_capped("minigames", "luckbucks", cap, cap)
    assert await b.grant_daily_capped("minigames", "luckbucks", 10, cap) == 10
    assert await a.grant_daily_capped("other", "luckbucks", 10, cap) == 10


async def test_exchange_converts_bits_one_way_at_the_posted_rate(db):
    user = await User.get(1)
    await set_columns(user, purse=100_000)
    got, spent = await exchange_bits(user, 10)
    assert (got, spent) == (10, 10 * RULES.exchange.bits_per_luckbuck)
    assert user.luckbucks == 110 and user.purse == 100_000 - spent


async def test_exchange_validation_and_daily_limit_refund(db):
    user = await User.get(1)
    await set_columns(user, purse=10**9)
    with pytest.raises(ExchangeError):
        await exchange_bits(user, 0)
    poor = await User.get(2)
    with pytest.raises(ExchangeError, match="need"):
        await exchange_bits(poor, 1)
    limit = RULES.exchange.daily_limit
    got, _ = await exchange_bits(user, limit - 1)
    got2, spent2 = await exchange_bits(user, 10)  # only 1 fits today
    assert (got2, spent2) == (1, RULES.exchange.bits_per_luckbuck)
    bits_after = user.purse
    with pytest.raises(ExchangeError, match="limit"):
        await exchange_bits(user, 5)
    assert (await User.get(1)).purse == bits_after  # a refused exchange costs nothing
