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
    for uid, purse in [(1, 100), (2, 550), (3, 20), (99, 10_000)]:
        await set_columns(await User.get(uid), purse=purse, name=f"p{uid}")
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


async def test_leaving_rules(db):
    from cococap.errors import CustomError

    party = await Party.create(1)
    await party.add_member(2)
    with pytest.raises(CustomError, match="leader"):
        await party.leave(1)  # the leader can't leave a team
    assert await party.leave(2) is False and party.members == [1]
    assert await party.leave(1) is True and await Party.load(party.party_id) is None  # the last one out closes it
    with pytest.raises(UserNotInParty):
        await party.leave(1)


async def test_who_may_invite_whom(db):
    from cococap.errors import CustomError

    party = await Party.create(1)
    await party.add_member(2)
    party.check_invite(1, 3)  # the leader may
    for inviter, member, bot, message in ((2, 3, False, "leader"), (1, 1, False, "already here"), (1, 3, True, "Bots")):
        with pytest.raises(CustomError, match=message):
            party.check_invite(inviter, member, is_bot=bot)


# ---- the party xp bonus (applies to every skill) --------------------------------------------------------------------
async def test_the_xp_bonus_needs_a_party_of_two_or_more_and_grows_with_its_size_up_to_a_cap(db):
    from cococap.services.party import bonus_for_size, xp_bonus, xp_multiplier

    await User.get(1)
    assert await xp_multiplier(1) == 1.0  # no party
    party = await Party.create(1)
    assert await xp_multiplier(1) == 1.0  # a party of one
    expected = {2: 1.10, 3: 1.25, 4: 1.50, 5: 1.50, 6: 1.50}
    for size in range(2, 7):
        await party.add_member(size)
        assert await xp_multiplier(1) == pytest.approx(expected[size]), size
        assert await xp_multiplier(size) == pytest.approx(expected[size])  # every member gets it
    assert await xp_bonus(1) == pytest.approx(0.50)
    assert [bonus_for_size(n) for n in (1, 2, 3, 4, 9)] == [0.0, 0.10, 0.25, 0.50, 0.50]
    for leaver in (6, 5, 4, 3):
        await party.leave(leaver)
    assert await xp_multiplier(1) == pytest.approx(1.10)  # back down to a pair
    await party.leave(2)
    assert await xp_multiplier(2) == 1.0 and await xp_multiplier(1) == 1.0


async def test_mining_xp_is_boosted_in_a_party_and_banked_once(db):
    from random import Random

    from cococap.services import mining

    async def run_for(user_id):
        user = await User.get(user_id)
        run = await mining.start_run(user, Random(1))
        run.lodes, run.outcome = 4, "left"
        summary = await mining.settle_run(user, run)
        return user, run, summary

    _, _, plain = await run_for(1)
    party = await Party.create(2)
    await party.add_member(3)
    user, run, boosted = await run_for(2)
    assert plain.xp == 40 and boosted.xp == 44  # a pair gets +10%
    assert (await user.skill("mining")).xp == 44
    await party.leave(3)
    again = await mining.settle_run(user, run)  # settling twice neither re-pays nor changes the report
    assert again.xp == 44 and (await user.skill("mining")).xp == 44


async def test_farming_xp_is_boosted_in_a_party(db):
    from random import Random

    from cococap.services import farming

    async def harvest_xp(user_id):
        user = await User.get(user_id)
        await user.add_item("apple_seed", 1)
        await farming.plant(user, 1, "apple_seed", now=0)
        await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
        return (await farming.harvest(user, 1, Random(1), now=0)).xp

    plain = await harvest_xp(1)
    party = await Party.create(2)
    await party.add_member(3)
    assert await harvest_xp(2) == round(plain * 1.10)
