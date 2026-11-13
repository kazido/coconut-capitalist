import asyncio

import pytest

from cococap.services import economy
from cococap.services.economy import OnCooldown
from cococap.user import Cooldowns, User
from tests.conftest import set_columns


async def test_work_pays_the_rank_wage_once_then_goes_on_cooldown(db):
    user = await User.get(1)
    reward = await economy.claim_work(user)
    assert reward.wage == 2500 and not reward.deposited
    assert await user.get_bits() == 1000 + 2500 and await user.get_stat("claimed_work") == 1
    with pytest.raises(OnCooldown) as e:
        await economy.claim_work(user)
    assert 0 < e.value.seconds_left <= 6 * 3600
    assert await user.get_bits() == 3500


async def test_auto_deposit_setting_moves_the_wage_to_the_bank(db):
    user = await User.get(1)
    await user.set_setting("auto_deposit", True)
    reward = await economy.claim_work(user)
    assert reward.deposited and (user.purse, user.bank) == (1000, 2500)


async def test_many_open_menus_cannot_claim_twice(db):
    await User.get(1)
    handles = [await User.get(1) for _ in range(5)]
    results = await asyncio.gather(*(economy.claim_work(h) for h in handles), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 1
    assert (await User.get(1)).purse == 3500


async def test_daily_pays_interest_and_a_token(db):
    user = await User.get(1)
    await set_columns(user, bank=1_000_000)
    reward = await economy.claim_daily(user)
    assert reward.interest == economy.bank_interest(1_000_000) > 0 and reward.tokens == 1
    assert (user.bank, user.tokens) == (1_000_000 + reward.interest, 1)
    with pytest.raises(OnCooldown):
        await economy.claim_daily(user)


async def test_weekly_pays_luckbucks(db):
    user = await User.get(1)
    assert await economy.claim_weekly(user) == 100 and user.luckbucks == 100 + 100  # starting balance + weekly


def test_interest_rate_shrinks_as_the_bank_grows():
    small, huge = economy.bank_interest(1_000_000) / 1_000_000, economy.bank_interest(10**9) / 10**9
    assert small > huge and huge == pytest.approx(0.003)


async def test_cooldown_state_reports_remaining_time(db):
    user = await User.get(1)
    assert economy.cooldown_state(user, Cooldowns.WORK).ready
    await user.claim_cooldown(Cooldowns.WORK)
    state = economy.cooldown_state(user, Cooldowns.WORK)
    assert not state.ready and 21000 < state.seconds_left <= 21600
