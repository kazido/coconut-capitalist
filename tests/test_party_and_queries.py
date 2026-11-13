import asyncio

import pytest

from cococap.db import queries
from cococap.exts.core.party_system import AlreadyInParty, Party, UserNotInParty
from cococap.user import User
from tests.conftest import set_columns


async def test_party_lifecycle(db):
    party = await Party.create(1)
    assert party.is_owner(1) and party.members == [1] and 1000 <= party.party_id <= 9999
    await party.add_member(2)
    reloaded = await Party.load(party.party_id)
    assert sorted(reloaded.members) == [1, 2]
    assert (await Party.for_user(2)).party_id == party.party_id

    await reloaded.change_owner(2)
    assert (await Party.load(party.party_id)).owner == 2  # owner change is persisted

    await reloaded.remove_member(1)
    assert await Party.for_user(1) is None
    with pytest.raises(UserNotInParty):
        await reloaded.remove_member(1)

    await reloaded.delete()
    assert await Party.load(party.party_id) is None
    assert await Party.for_user(2) is None  # members released by the cascade


async def test_one_party_per_user(db):
    first = await Party.create(1)
    with pytest.raises(AlreadyInParty):
        await Party.create(1)
    other = await Party.create(2)
    with pytest.raises(AlreadyInParty):
        await other.add_member(1)  # already in `first`
    with pytest.raises(AlreadyInParty):
        await first.add_member(1)


async def test_concurrent_joins_never_double_book_a_user(db):
    a, b = await Party.create(1), await Party.create(2)
    results = await asyncio.gather(a.add_member(3), b.add_member(3), return_exceptions=True)
    assert sum(isinstance(r, AlreadyInParty) for r in results) == 1
    assert (await Party.for_user(3)) is not None


async def test_leaderboards(db):
    for uid, purse, bank in [(1, 100, 0), (2, 50, 500), (3, 10, 10), (99, 10_000, 0)]:
        await set_columns(await User.get(uid), purse=purse, bank=bank, name=f"p{uid}")
    await (await User.get(1)).inc_stat("drops_claimed", 4)
    await (await User.get(3)).inc_stat("drops_claimed", 9)
    await (await User.get(2)).add_xp("mining", 300)

    bits = await queries.leaderboard("bits", exclude=99)  # 99 is the "house"
    assert [(e.rank, e.discord_id, e.value) for e in bits] == [(1, 2, 550), (2, 1, 100), (3, 3, 20)]
    drops = await queries.leaderboard("stat:drops_claimed")
    assert [(e.discord_id, e.value) for e in drops] == [(3, 9), (1, 4)]
    assert [e.discord_id for e in await queries.leaderboard("skill:mining")] == [2]
    assert [e.discord_id for e in await queries.leaderboard("bits", limit=1, exclude=99)] == [2]

    me = await queries.position_of("bits", 3, exclude=99)
    assert (me.rank, me.value) == (3, 20)
    assert await queries.position_of("skill:farming", 1) is None  # no score yet
    assert await queries.bits_in_circulation(exclude=99) == 670


async def test_megadrop_row(db):
    await queries.ensure_megadrop("01-01-2026")
    await queries.ensure_megadrop("12-31-2099")  # second call must not reset anything
    await asyncio.gather(*(queries.update_megadrop(inc={"amount": 100, "counter": 1}) for _ in range(5)))
    await queries.update_megadrop(last_winner=42)
    row = await queries.get_megadrop()
    assert (row.amount, row.counter, row.last_winner, row.date_started) == (500, 5, 42, "01-01-2026")


async def test_unknown_leaderboard_category_is_an_error(db):
    with pytest.raises(KeyError):
        await queries.leaderboard("nonsense")
