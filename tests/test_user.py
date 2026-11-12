import asyncio

import pytest

from cococap.models.models import UserDocument
from cococap.user import Cooldowns, InsufficientFunds, User


async def make_user(discord_id=1, **fields) -> User:
    user = await User.get(discord_id)
    if fields:
        await UserDocument.find_one(UserDocument.discord_id == discord_id).update({"$set": fields})
        await user.refresh()
    return user


async def test_get_creates_once_even_when_called_concurrently(db):
    users = await asyncio.gather(*(User.get(42) for _ in range(10)))
    assert await UserDocument.find(UserDocument.discord_id == 42).count() == 1
    assert len({u._document.id for u in users}) == 1


async def test_remove_bits_never_goes_negative(db):
    user = await make_user(purse=100)
    with pytest.raises(InsufficientFunds):
        await user.remove_bits(101)
    assert await user.get_bits() == 100


async def test_concurrent_spends_cannot_overdraw(db):
    user = await make_user(purse=1000)
    results = await asyncio.gather(*(_try_spend(600) for _ in range(10)))
    assert results.count(True) == 1
    assert await user.get_bits() == 400


async def _try_spend(amount):
    handle = await User.get(1)  # separate handle, like a separate command invocation
    try:
        await handle.remove_bits(amount)
        return True
    except InsufficientFunds:
        return False


async def test_pay_conserves_bits_and_checks_balance(db):
    alice = await make_user(1, purse=500)
    bob = await make_user(2, purse=0)
    await alice.pay(bob, 200)
    assert await alice.get_bits() == 300 and await bob.get_bits() == 200
    with pytest.raises(InsufficientFunds):
        await alice.pay(bob, 301)
    assert await alice.get_bits() + await bob.get_bits() == 500


async def test_deposit_and_withdraw_are_bounded(db):
    user = await make_user(purse=100, bank=50)
    await user.deposit_bits(100)
    assert await user.get_field_fresh("purse") == 0
    assert await user.get_field_fresh("bank") == 150
    with pytest.raises(InsufficientFunds):
        await user.deposit_bits(1)
    with pytest.raises(InsufficientFunds):
        await user.withdraw_bits(151)


async def test_cooldown_can_only_be_claimed_once_across_handles(db):
    await make_user()
    handles = [await User.get(1) for _ in range(5)]  # e.g. five open /check-in menus
    results = await asyncio.gather(*(h.claim_cooldown(Cooldowns.WORK) for h in handles))
    assert results.count(True) == 1
    assert not await handles[0].claim_cooldown(Cooldowns.WORK)


async def test_cooldown_claimable_again_after_it_elapses(db):
    user = await make_user()
    await user.claim_cooldown(Cooldowns.WORK)
    long_ago = 1.0
    await user.set_field("cooldowns.work", long_ago)
    assert await user.claim_cooldown(Cooldowns.WORK)


async def test_items_add_remove_are_atomic(db):
    user = await make_user()
    await asyncio.gather(*(user.add_item("apple", 2) for _ in range(10)))
    assert (await user.get_field_fresh("items"))["apple"]["quantity"] == 20
    with pytest.raises(ValueError):
        await user.remove_item("apple", 21)
    await user.remove_item("apple", 20)
    assert "apple" not in await user.get_field_fresh("items")
    with pytest.raises(ValueError):
        await user.remove_item("pear", 1)


async def test_stats_roundtrip(db):
    user = await make_user()
    await user.inc_stat("hl_wins")
    await user.inc_stat("claimed_work", 3)
    assert await user.get_stat("hl_wins") == 1
    assert await user.get_stat("claimed_work") == 3
    await user.set_stat("hl_wins", 0)
    assert await user.get_stat("hl_wins") == 0


async def test_rank_up_charges_tokens_and_cannot_be_replayed_or_skipped(db):
    user = await make_user(tokens=25, rank=1)
    assert await user.rank_up(2, 10)
    assert await user.get_field_fresh("tokens") == 15
    assert await user.get_field_fresh("rank") == 2
    assert not await user.rank_up(2, 10)  # stale button: already rank 2
    assert not await user.rank_up(4, 10)  # can't skip rank 3
    assert await user.get_field_fresh("tokens") == 15
    broke = await make_user(2, tokens=5, rank=1)
    assert not await broke.rank_up(2, 10)
    assert await broke.get_field_fresh("rank") == 1


async def test_add_tokens_rejects_negative_amounts(db):
    user = await make_user()
    with pytest.raises(ValueError):
        await user.add_tokens(-10)  # used to silently *add* 10 (abs()), making rank-ups pay out
