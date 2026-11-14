from types import SimpleNamespace

import pytest
from sqlalchemy import select

from cococap.db import get_database
from cococap.db.tables import UserRow
from cococap.registry import get_registry
from cococap.services import activity
from cococap.services.party import Party
from cococap.user import User
from tests.conftest import set_columns

REG = get_registry()
HOUR = 3600
NOW = 2_000_000_000.0
LIMIT = 24  # hours. The tests use their own limit, so changing party_idle_hours in the config (to try it out) cannot break them
IDLE = LIMIT * HOUR
RULES = SimpleNamespace(economy=SimpleNamespace(party_idle_hours=LIMIT))


@pytest.fixture(autouse=True)
def _forget_writes():
    activity._last_written.clear()


async def stamp(user_id):
    async with get_database().session() as session:
        return await session.scalar(select(UserRow.last_active).where(UserRow.discord_id == user_id))


async def seen(user_id, ago):
    await set_columns(await User.get(user_id), last_active=NOW - ago)


async def party_of(*members, owner=None):
    party = await Party.create(owner or members[0])
    for m in members:
        if m != party.owner:
            await party.add_member(m)
    return party


async def test_pressing_things_stamps_when_you_were_last_around_at_most_once_a_minute(db):
    await seen(1, ago=10 * HOUR)
    await activity.touch(1, NOW)
    assert await stamp(1) == NOW
    await activity.touch(1, NOW + 30)  # too soon: not written again
    assert await stamp(1) == NOW
    await activity.touch(1, NOW + 61)
    assert await stamp(1) == NOW + 61
    await activity.touch(404, NOW)  # a stranger is not given a row
    assert await Party.for_user(404) is None


async def test_an_idle_member_is_taken_out_and_an_active_one_stays(db):
    await party_of(1, 2, 3)
    await seen(1, 5 * HOUR)
    await seen(2, IDLE + HOUR)
    await seen(3, 1 * HOUR)
    kicked = await activity.sweep(NOW, RULES)
    assert [(k.user_id, k.disbanded, k.new_owner) for k in kicked] == [(2, False, None)]
    party = await Party.for_user(1)
    assert sorted(party.members) == [1, 3] and await Party.for_user(2) is None


async def test_the_cutoff_is_exact(db):
    await party_of(1, 2)
    await seen(1, 0)
    await seen(2, IDLE - 1)  # a second short of the limit: still in
    assert await activity.sweep(NOW, RULES) == []
    await seen(2, IDLE + 1)
    assert [k.user_id for k in await activity.sweep(NOW, RULES)] == [2]


async def test_an_idle_owner_hands_the_party_to_whoever_was_around_most_recently(db):
    party = await party_of(1, 2, 3)
    await seen(1, IDLE + HOUR)
    await seen(2, 8 * HOUR)
    await seen(3, 2 * HOUR)
    kicked = await activity.sweep(NOW, RULES)
    assert [(k.user_id, k.new_owner) for k in kicked] == [(1, 3)]
    after = await Party.load(party.party_id)
    assert after.owner == 3 and sorted(after.members) == [2, 3]


async def test_a_party_where_everyone_has_gone_quiet_is_disbanded_and_a_lone_active_player_keeps_theirs(db):
    gone = await party_of(1, 2)
    await seen(1, IDLE + 5 * HOUR)
    await seen(2, IDLE + HOUR)
    solo = await party_of(3)
    await seen(3, HOUR)
    kicked = await activity.sweep(NOW, RULES)
    assert {k.user_id for k in kicked} == {1, 2} and all(k.disbanded for k in kicked)
    assert await Party.load(gone.party_id) is None
    assert await Party.load(solo.party_id) is not None


async def test_players_without_a_party_and_a_second_sweep_do_nothing(db):
    await User.get(9)
    await seen(9, IDLE * 5)
    assert await activity.sweep(NOW, RULES) == []
    await party_of(1, 2)
    await seen(1, 0)
    await seen(2, IDLE * 2)
    assert len(await activity.sweep(NOW, RULES)) == 1
    assert await activity.sweep(NOW, RULES) == []


async def test_it_is_a_setting_not_a_constant(db):
    assert REG.economy.party_idle_hours > 0
    await party_of(1, 2)
    await seen(1, 0)
    await seen(2, 2 * HOUR)
    short = SimpleNamespace(economy=SimpleNamespace(party_idle_hours=1))
    assert [k.user_id for k in await activity.sweep(NOW, short)] == [2]
