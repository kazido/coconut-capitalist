from cococap.models.settings import Settings
import asyncio

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from cococap.db import get_database
from cococap.db.tables import ItemRow, UserRow
from cococap.models.skills.farming import Farming
from cococap.models.skills.mining import Mining
from cococap.user import Cooldowns, InsufficientFunds, User
from tests.conftest import set_columns


async def make_user(discord_id=1, **columns) -> User:
    user = await User.get(discord_id)
    if columns:
        await set_columns(user, **columns)
    return user


async def test_get_creates_once_even_when_called_concurrently(db):
    users = await asyncio.gather(*(User.get(42) for _ in range(10)))
    async with db.session() as session:
        assert len((await session.scalars(select(UserRow).where(UserRow.discord_id == 42))).all()) == 1
    assert {u.id for u in users} == {42}
    assert users[0].purse == 1000  # starting balance


async def test_find_does_not_create(db):
    assert await User.find(7) is None
    await User.get(7)
    assert (await User.find(7)).id == 7


async def test_remove_bits_never_goes_negative(db):
    user = await make_user(purse=100)
    with pytest.raises(InsufficientFunds):
        await user.remove_bits(101)
    assert await user.get_bits() == 100


async def test_database_itself_refuses_negative_balances(db):
    user = await make_user(purse=100)
    with pytest.raises(IntegrityError):
        await set_columns(user, purse=-1)  # CHECK constraint, regardless of application code


async def test_concurrent_spends_cannot_overdraw(db):
    user = await make_user(purse=1000)

    async def try_spend(amount):
        handle = await User.get(1)  # a separate handle, like a separate command invocation
        try:
            await handle.remove_bits(amount)
            return True
        except InsufficientFunds:
            return False

    results = await asyncio.gather(*(try_spend(600) for _ in range(10)))
    assert results.count(True) == 1
    assert await user.get_bits() == 400


async def test_pay_conserves_bits_and_checks_balance(db):
    alice = await make_user(1, purse=500)
    bob = await make_user(2, purse=0)
    await alice.pay(bob, 200)
    assert await alice.get_bits() == 300 and await bob.get_bits() == 200
    with pytest.raises(InsufficientFunds):
        await alice.pay(bob, 301)
    assert await alice.get_bits() + await bob.get_bits() == 500


async def test_cooldown_can_only_be_claimed_once_across_handles(db):
    await make_user()
    handles = [await User.get(1) for _ in range(5)]  # e.g. five open /check-in menus
    results = await asyncio.gather(*(h.claim_cooldown(Cooldowns.WORK) for h in handles))
    assert results.count(True) == 1
    assert not await handles[0].claim_cooldown(Cooldowns.WORK)


async def test_cooldown_claimable_again_after_it_elapses(db):
    user = await make_user()
    await user.claim_cooldown(Cooldowns.WORK)
    await set_columns(user, work_cooldown=1.0)
    assert await user.claim_cooldown(Cooldowns.WORK)
    await user.reset_cooldowns()
    assert user.get_cooldown(Cooldowns.WORK) == 0


async def test_items_add_remove_are_atomic(db):
    user = await make_user()
    await asyncio.gather(*(user.add_item("crop_apple", 2) for _ in range(10)))
    assert await user.items() == {"crop_apple": 20}
    with pytest.raises(ValueError):
        await user.remove_item("crop_apple", 21)
    await user.remove_item("crop_apple", 20)
    assert await user.items() == {}  # emptied stacks are deleted
    with pytest.raises(ValueError):
        await user.remove_item("pear", 1)
    with pytest.raises(ValueError):
        await user.remove_item("crop_apple", -5)  # must never add items


async def test_concurrent_item_removals_cannot_go_negative(db):
    user = await make_user()
    await user.add_item("crop_apple", 5)

    async def take():
        try:
            await user.remove_item("crop_apple", 3)
            return True
        except ValueError:
            return False

    assert (await asyncio.gather(*(take() for _ in range(4)))).count(True) == 1
    assert await user.item_quantity("crop_apple") == 2


async def test_item_ids_with_dots_or_symbols_are_rejected(db):
    user = await make_user()
    for bad in ("apple.seed", "$x", ""):
        with pytest.raises(ValueError):
            await user.add_item(bad)
        with pytest.raises(ValueError):
            await user.remove_item(bad)
    assert await user.items() == {}


async def test_stats_roundtrip_and_defaults(db):
    user = await make_user()
    assert await user.get_stat("hl_wins") == 0  # never recorded
    await asyncio.gather(*(user.inc_stat("hl_wins") for _ in range(5)))
    await user.inc_stat("claimed_work", 3)
    assert await user.get_stat("hl_wins") == 5
    assert await user.stats() == {"hl_wins": 5, "claimed_work": 3}
    await user.set_stat("hl_wins", 0)
    assert await user.get_stat("hl_wins") == 0


async def test_skills_default_and_xp_accumulates(db):
    user = await make_user()
    assert (await user.skill("mining")) == Mining()
    await asyncio.gather(*(user.add_xp("mining", 10) for _ in range(5)))
    assert (await user.skill("mining")).xp == 50


async def test_update_skill_persists_nested_data_and_columns(db):
    user = await make_user()
    hoe = await user.give_instance("tool_axe_starter")  # any real instance id will do

    def plant(farming: Farming):
        farming.farm.plot_2.crop_id = "crop_apple"
        farming.farm.plot_2.cycle = 3
        farming.equipped_instance_id = hoe.id
        farming.xp += 7

    await user.update_skill("farming", plant)
    loaded = await user.skill("farming")
    assert loaded.farm.plot_2.crop_id == "crop_apple" and loaded.farm.plot_2.cycle == 3
    assert loaded.farm.plot_1.crop_id is None
    assert (loaded.equipped_instance_id, loaded.xp) == (hoe.id, 7)


async def test_concurrent_skill_updates_do_not_overwrite_each_other(db):
    user = await make_user()

    def bump(farming: Farming):
        farming.stats.crops_grown += 1

    await asyncio.gather(*(user.update_skill("farming", bump) for _ in range(10)))
    assert (await user.skill("farming")).stats.crops_grown == 10


async def test_rank_up_charges_tokens_and_cannot_be_replayed_or_skipped(db):
    user = await make_user(tokens=25, rank=1)
    assert await user.rank_up(2, 10)
    assert (user.tokens, user.rank) == (15, 2)
    assert not await user.rank_up(2, 10)  # stale button: already rank 2
    assert not await user.rank_up(4, 10)  # can't skip rank 3
    assert await user.get_bits() == 1000 and user.tokens == 15
    broke = await make_user(2, tokens=5, rank=1)
    assert not await broke.rank_up(2, 10)
    assert broke.rank == 1


async def test_add_tokens_rejects_negative_amounts(db):
    user = await make_user()
    with pytest.raises(ValueError):
        await user.add_tokens(-10)


async def test_settings_roundtrip_and_validation(db):
    user = await make_user()
    assert user.settings.model_dump() == Settings().model_dump()  # the defaults: asks before Sell all, until you turn it off
    await user.set_setting("anything", True)  # unknown keys are not stored
    assert (await User.get(1)).settings.model_dump() == Settings().model_dump()
    await user.set_setting("confirm_upgrades", True)
    assert (await User.get(1)).settings.confirm_upgrades is True


async def test_deleting_a_user_cascades(db):
    user = await make_user()
    await user.add_item("crop_apple", 1)
    await user.inc_stat("x")
    async with get_database().session() as session:
        await session.execute(text("DELETE FROM users WHERE discord_id = 1"))
        assert (await session.scalars(select(ItemRow))).all() == []


# ---- rank buffs --------------------------------------------------------------------------------------------------------------------
async def test_a_higher_rank_gives_more_xp_in_every_skill(db):
    from cococap.registry import get_registry
    from cococap.services.party import xp_multiplier

    reg = get_registry()
    ranks = sorted(reg.ranks)
    bonuses = [reg.rank(r).xp_bonus for r in ranks]
    assert bonuses == sorted(bonuses) and bonuses[0] == 0 and bonuses[-1] == 0.15
    prices = [reg.rank(r).token_price for r in ranks]
    assert prices == sorted(prices) and [reg.rank(r).wage for r in ranks] == sorted(reg.rank(r).wage for r in ranks)
    plain = await make_user(1, rank=1)
    expert = await make_user(2, rank=8)
    top = await make_user(3, rank=max(ranks))
    for skill in ("mining", "farming", "foraging", "fishing"):
        assert await xp_multiplier(1, reg, skill) == pytest.approx(1.01)
        assert await xp_multiplier(2, reg, skill) == pytest.approx(1.08)
        assert await xp_multiplier(3, reg, skill) == pytest.approx(1.15)
    assert plain.rank == 1 and expert.rank == 8 and top.rank == 15
