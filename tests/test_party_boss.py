"""Party boss fights: a boss one member hooks can be joined by the rest of the party; everyone reels their own arrows and is paid."""

from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import fishing as f
from cococap.services import party_boss as pb
from cococap.services.equipment import equip
from cococap.services.party import Party
from cococap.user import User
from tests.test_fishing import T0, clock, open_fishing, player, reel_in  # noqa: F401
from tests.test_hub import all_text, buttons, click, find_button, hub

REG = get_registry()
RULES = REG.fishing
BOSS = RULES.boss
P = BOSS.party


async def team(size=2, rod="starter_rod"):
    users = [await player(i, rod) for i in range(1, size + 1)]
    party = await Party.create(1)
    for i in range(2, size + 1):
        await party.add_member(i)
    return users


# ---- the rules -------------------------------------------------------------------------------------------------------------------------------
def test_the_team_bonus_grows_with_each_extra_member_who_lands_theirs_up_to_a_cap():
    assert pb.team_bonus(1, REG) == 0 and pb.team_bonus(2, REG) == P.bonus_per_extra
    assert pb.team_bonus(3, REG) == 2 * P.bonus_per_extra and pb.team_bonus(99, REG) == P.max_bonus


async def test_only_a_party_of_two_or_more_opens_a_fight_and_only_one_at_a_time(db):
    alone = await player(1)
    assert await pb.open_fight(alone, "Old Whiskers", [], T0, REG) is None  # no party: it is yours alone
    users = await team(2)
    fight = await pb.open_fight(users[0], "Old Whiskers", ["mirror"], T0, REG)
    assert fight.boss == "Old Whiskers" and fight.you == "reeling" and fight.is_open and fight.closes_at == T0 + P.fight_seconds
    assert await pb.open_fight(users[1], "Big Mama", [], T0 + 5, REG) is None  # (one at a time: a second boss is a solo fight)


async def test_a_teammate_can_join_once_while_it_is_open(db):
    users = await team(3)
    await pb.open_fight(users[0], "Old Whiskers", [], T0, REG)
    joined = await pb.join(users[1], T0 + 10, REG)
    assert joined.you == "reeling" and joined.reeling == 2
    with pytest.raises(pb.PartyBossError, match="already"):
        await pb.join(users[1], T0 + 11, REG)
    with pytest.raises(pb.PartyBossError, match="closed|no boss fight"):
        await pb.join(users[2], T0 + P.fight_seconds + 1, REG)  # too late: it has ended
    solo = await player(9)
    with pytest.raises(pb.PartyBossError, match="party"):
        await pb.join(solo, T0, REG)


async def test_everyone_who_lands_their_reel_is_paid_with_a_team_bonus_and_only_once(db):
    users = await team(3)
    await pb.open_fight(users[0], "Old Whiskers", [], T0, REG)
    await pb.join(users[1], T0 + 5, REG)
    await pb.join(users[2], T0 + 6, REG)
    assert await pb.claim(users[0], T0 + 10, REG) == []  # nothing is paid until the fight is over
    await pb.report(users[0], "done", 2, T0 + 20, REG)
    await pb.report(users[1], "done", 0, T0 + 21, REG)
    assert await pb.claim(users[0], T0 + 22, REG) == []  # (one reel is still out)
    final = await pb.report(users[2], "done", 0, T0 + 23, REG)
    assert final.status == "won"
    paid = {u.id: await pb.claim(u, T0 + 24, REG) for u in users}
    assert all(len(p) == 1 for p in paid.values())
    bonus = 2 * P.bonus_per_extra
    for p in paid.values():
        assert p[0].teammates == 2 and p[0].bonus == pytest.approx(bonus) and p[0].xp >= round(BOSS.xp * (1 + bonus))
    assert paid[1][0].slack_bits > 0 and paid[2][0].slack_bits == 0  # the starter kept slack to spare
    assert await pb.claim(users[0], T0 + 30, REG) == []  # once only
    assert (await users[0].skill("fishing")).stats.bosses_beaten == 1


async def test_a_teammate_who_slips_off_only_loses_their_own_share(db):
    users = await team(3)
    await pb.open_fight(users[0], "Big Mama", [], T0, REG)
    await pb.join(users[1], T0 + 5, REG)
    await pb.join(users[2], T0 + 6, REG)
    await pb.report(users[0], "done", 0, T0 + 20, REG)
    await pb.report(users[1], "failed", 0, T0 + 21, REG)
    await pb.report(users[2], "done", 0, T0 + 22, REG)
    assert len(await pb.claim(users[0], T0 + 30, REG)) == 1 and len(await pb.claim(users[2], T0 + 30, REG)) == 1
    assert await pb.claim(users[1], T0 + 30, REG) == []  # the one who slipped is paid nothing...
    paid = await pb.view(users[0], T0 + 31, REG)
    assert paid.status == "won" and paid.failed == 1 and paid.done == 2  # ...but the fight was still won


async def test_a_fight_nobody_finishes_is_lost_and_time_running_out_ends_it(db):
    users = await team(2)
    await pb.open_fight(users[0], "Old Whiskers", [], T0, REG)
    await pb.join(users[1], T0 + 5, REG)
    await pb.report(users[0], "failed", 0, T0 + 10, REG)
    assert (await pb.view(users[1], T0 + 11, REG)).is_open  # (a teammate is still reeling)
    ended = await pb.view(users[1], T0 + P.fight_seconds + 1, REG)
    assert ended.status == "lost" and await pb.claim(users[1], T0 + P.fight_seconds + 2, REG) == []
    new = await pb.open_fight(users[1], "Big Mama", [], T0 + P.fight_seconds + 3, REG)  # and a new one can open
    assert new.is_open and new.number == 2


async def test_someone_still_reeling_when_time_runs_out_loses_their_share_but_the_others_are_paid(db):
    users = await team(2)
    await pb.open_fight(users[0], "Old Whiskers", [], T0, REG)
    await pb.join(users[1], T0 + 5, REG)
    await pb.report(users[0], "done", 0, T0 + 20, REG)
    late = await pb.report(users[1], "done", 0, T0 + P.fight_seconds + 5, REG)  # (too late: the fight ended while they reeled)
    assert late.status == "won" and late.you == "failed"
    assert len(await pb.claim(users[0], T0 + P.fight_seconds + 6, REG)) == 1 and await pb.claim(users[1], T0 + P.fight_seconds + 6, REG) == []


async def test_two_claims_at_once_pay_once(db):
    import asyncio

    users = await team(2)
    await pb.open_fight(users[0], "Old Whiskers", [], T0, REG)
    await pb.report(users[0], "done", 0, T0 + 5, REG)
    a, b = await asyncio.gather(pb.claim(users[0], T0 + 6, REG), pb.claim(users[0], T0 + 6, REG))
    assert len(a) + len(b) == 1


def test_everyone_reels_their_own_set_of_arrows_of_the_same_boss():
    from cococap.services.equipment import EffectiveStats

    stats = EffectiveStats(power=3, requirement=0, stats={"power": 3.0})
    casts = [f.join_boss_cast(stats, Random(seed), T0, "Old Whiskers", REG) for seed in range(8)]
    assert all(c.boss == "Old Whiskers" and c.hooked and c.modifiers == casts[0].modifiers for c in casts)
    assert all(len(c.pattern) >= BOSS.length for c in casts) and len({tuple(c.pattern) for c in casts}) > 4  # a different reel for each person
    assert all(not c.chest and c.status(T0) == "reeling" for c in casts)


# ---- on the screens --------------------------------------------------------------------------------------------------------------------------
async def hook_a_boss(nav, inter, clock, name="Old Whiskers"):
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    f.make_boss(cast, name, RULES, Random(5))
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    return cast


async def test_hooking_a_boss_in_a_party_opens_a_fight_the_others_can_join_from_their_fishing_page(db, clock):
    users = await team(2)
    nav, inter = await hub("fish")
    cast = await hook_a_boss(nav, inter, clock)
    assert cast.party_fight == 1 and "Party fight" in all_text(nav) and "party can join" in all_text(nav)
    mate, mate_inter = await hub("fish", user_id=2)
    assert "Old Whiskers" in all_text(mate) and find_button(mate, "Join the fight")
    assert mate.screen.refresh_every  # the page keeps itself fresh while a fight is open
    await click(mate, mate_inter, "Join the fight")
    their = mate.screen.cast
    assert their.boss == "Old Whiskers" and their.party_fight == 1 and their is not cast and their.hooked
    assert users


async def test_a_solo_player_hooking_a_boss_gets_the_ordinary_fight(db, clock):
    await player(1)
    nav, inter = await hub("fish")
    cast = await hook_a_boss(nav, inter, clock)
    assert cast.party_fight is None and "Party fight" not in all_text(nav)
    await reel_in(nav, inter, cast)
    assert "You beat Old Whiskers" in all_text(nav)  # paid straight away, as before


async def test_the_whole_party_fight_end_to_end_each_reels_their_own_and_both_are_paid_with_the_bonus(db, clock):
    await team(2)
    nav, inter = await hub("fish")
    cast = await hook_a_boss(nav, inter, clock)
    mate, mate_inter = await hub("fish", user_id=2)
    await click(mate, mate_inter, "Join the fight")
    mate_cast = mate.screen.cast
    await reel_in(nav, inter, cast)  # the starter lands theirs first: the fight is still open
    assert nav.screen.id == "result" and "landed your part" in all_text(nav) and "reels are all in" in all_text(nav)
    await click(nav, inter, "Back to fishing")
    assert "still reeling" in all_text(nav) and (await User.get(1)).purse == 1000  # not paid yet: a teammate is still reeling
    await reel_in(mate, mate_inter, mate_cast)  # the second lands theirs: the fight is over, and they are paid on the spot
    assert mate.screen.id == "result" and "beaten" in all_text(mate) and "team bonus" in all_text(mate)
    await nav.screen.nav.refresh(inter)
    assert nav.screen.id == "result" and "beaten" in all_text(nav)  # the starter collects theirs when they look
    assert (await User.get(1)).purse > 1000 and (await User.get(2)).purse > 1000


async def test_letting_the_boss_go_or_slipping_ends_only_your_part(db, clock):
    users = await team(2)
    nav, inter = await hub("fish")
    await hook_a_boss(nav, inter, clock)
    mate, mate_inter = await hub("fish", user_id=2)
    await click(mate, mate_inter, "Join the fight")
    await click(nav, inter, "Let it go")  # the starter gives up
    view = await pb.view(users[1], clock[0], REG)
    assert view.is_open and view.failed == 1 and view.reeling == 1  # the teammate's fight carries on
    await reel_in(mate, mate_inter, mate.screen.cast)
    assert (await pb.view(users[1], clock[0] + 1, REG)).status == "won"  # and is won by the one who landed theirs
