"""The Releaf Foundation: one server-wide meter, rare-only gifts, a temporary shared Bloom."""

import asyncio
import math
import time
from collections import Counter
from random import Random

import pytest

from cococap.models.skills.foraging import Foraging
from cococap.registry import get_registry
from cococap.services import foraging as f
from cococap.services import party_tree, releaf
from cococap.services.party import xp_multiplier
from cococap.user import User
from tests.test_hub import all_text, buttons, choose, click, find_button, freeze_time, hub, select_named, with_axe

REG = get_registry()
R = REG.foraging.releaf
CAP = releaf.cap_points(R)
RARE = max((i for i in REG.items.values() if releaf.can_give(i, R)), key=lambda i: R.worth(i.rarity)).id  # the most valuable item it takes
LOW = min((i for i in REG.items.values() if releaf.can_give(i, R)), key=lambda i: R.worth(i.rarity)).id  # the least valuable one it takes
POINTS = releaf.points_of(RARE, REG)
COMMON = next(i.id for i in REG.items.values() if i.skill == "foraging" and i.category == "material" and i.rarity < R.min_rarity)


async def forager(user_id=1, level=None, items=None):
    user = await User.get(user_id)
    await user.add_xp("foraging", User.level_to_xp(level or R.min_level) + 1)
    for item_id, quantity in (items or {}).items():
        await user.add_item(item_id, quantity)
    return user


async def fill(now, users=None):
    """Fill the meter exactly with several different players (the cap stops one person doing it). Returns the users."""
    users = users or []
    uid = 100
    while (await releaf.foundation(now)).meter < R.meter_goal:
        uid += 1
        user = await forager(uid, items={RARE: 50})
        users.append(user)
        await releaf.donate(user, RARE, 50, now)
    return users


# ---- the rules -------------------------------------------------------------------------------------------------------------------
def test_the_numbers_are_sane():
    assert R.min_rarity >= 4 and all(r >= R.min_rarity for r in R.points)
    assert CAP < R.meter_goal and math.ceil(R.meter_goal / CAP) >= 3  # it takes several people to fill a meter
    assert R.worth(R.min_rarity - 1) == 0 and R.worth(R.min_rarity) > 0
    assert releaf.can_give(REG.item(RARE), R) and not releaf.can_give(REG.item(COMMON), R)
    assert not any(releaf.can_give(i, R) for i in REG.items.values() if i.category == "tool")


async def test_only_rare_foraging_items_can_be_given_and_nothing_is_lost_when_refused(db):
    user = await forager(items={COMMON: 5})
    with pytest.raises(releaf.ReleafError, match="rarity"):
        await releaf.donate(user, COMMON, 2)
    assert await user.item_quantity(COMMON) == 5
    mining_rare = next(i.id for i in REG.items.values() if i.skill == "mining" and i.rarity >= R.min_rarity and i.category != "tool")
    await user.add_item(mining_rare, 1)
    with pytest.raises(releaf.ReleafError):
        await releaf.donate(user, mining_rare, 1)
    assert await user.item_quantity(mining_rare) == 1
    assert (await releaf.foundation()).meter == 0


async def test_giving_takes_the_item_for_good_and_fills_the_shared_meter(db):
    user = await forager(items={RARE: 3})
    done = await releaf.donate(user, RARE, 2)
    assert done.given == 2 and done.points == 2 * POINTS and done.meter == 2 * POINTS
    assert await user.item_quantity(RARE) == 1  # a real loss
    other = await forager(2, items={LOW: 1})
    await releaf.donate(other, LOW, 1)
    found = await releaf.foundation()
    assert found.meter == 2 * POINTS + releaf.points_of(LOW, REG)  # one meter for everybody
    assert (await user.skill("foraging")).stats.releaf_donations == 1


async def test_you_need_the_level_and_the_items(db):
    low = await forager(level=R.min_level - 5, items={RARE: 1})
    with pytest.raises(releaf.ReleafError, match=f"level {R.min_level}"):
        await releaf.donate(low, RARE, 1)
    assert await low.item_quantity(RARE) == 1
    user = await forager(2)
    with pytest.raises(releaf.ReleafError, match="don't have"):
        await releaf.donate(user, RARE, 1)
    with pytest.raises(releaf.ReleafError):
        await releaf.donate(user, RARE, 0)


async def test_one_player_can_only_give_their_cap_and_the_rest_comes_back(db):
    user = await forager(items={RARE: 100})
    fits = CAP // POINTS
    done = await releaf.donate(user, RARE, 100)
    assert done.given == fits and done.returned == 100 - fits and done.points == fits * POINTS <= CAP
    assert await user.item_quantity(RARE) == 100 - fits
    with pytest.raises(releaf.ReleafError, match="as much as one person"):
        await releaf.donate(user, RARE, 1)
    assert await user.item_quantity(RARE) == 100 - fits  # refused: nothing taken
    assert (await releaf.status(user)).yours == fits * POINTS
    assert (await releaf.foundation()).meter == fits * POINTS


async def test_the_bloom_starts_exactly_at_the_goal_and_the_meter_never_overfills(db):
    now = time.time()
    users = await fill(now)
    found = await releaf.foundation(now)
    assert found.meter == R.meter_goal and found.bloom_active and found.full and not found.open
    assert found.bloom_until == pytest.approx(now + R.bloom_hours * 3600)
    assert len(users) >= math.ceil(R.meter_goal / CAP)
    just_below = await releaf.foundation(now)  # (and it started once, not once per gift)
    assert len((await releaf.windows())) == 1 and just_below.meter == R.meter_goal


async def test_giving_is_closed_while_the_meter_is_full_and_the_item_is_refunded(db):
    now = time.time()
    await fill(now)
    late = await forager(500, items={RARE: 2})
    with pytest.raises(releaf.ReleafError, match="closed"):
        await releaf.donate(late, RARE, 2, now + 60)
    assert await late.item_quantity(RARE) == 2
    assert (await releaf.foundation(now + 60)).meter == R.meter_goal
    assert len(await releaf.windows()) == 1


async def test_the_bloom_expires_then_the_meter_resets_and_giving_reopens(db):
    now = time.time()
    await fill(now)
    end = now + R.bloom_hours * 3600
    assert (await releaf.foundation(end - 1)).bloom_active
    after = await releaf.foundation(end + 1)
    assert not after.bloom_active and after.meter == 0 and after.open and not after.top  # round tallies reset...
    user = await forager(600, items={RARE: 1})
    await releaf.donate(user, RARE, 1, end + 2)
    assert (await releaf.foundation(end + 3)).meter == POINTS
    assert (await releaf.status(user, end + 3)).lifetime == POINTS  # ...lifetime tallies stay
    assert (await releaf.status(await forager(101), end + 3)).lifetime > 0
    assert not await releaf.active(end + 3)


async def fill_almost(now, leave):
    """Give with fresh players until at most `leave` points are missing (and more than 0). Returns how many players it took."""
    uid = 10
    while R.meter_goal - (await releaf.foundation(now)).meter > leave:
        uid += 1
        missing = R.meter_goal - (await releaf.foundation(now)).meter
        take = min(CAP // POINTS, (missing - 1) // POINTS)  # never the whole meter
        await releaf.donate(await forager(uid, items={RARE: 99}), RARE, max(1, take), now)
    return uid


async def test_the_last_gift_tops_the_meter_off_and_the_surplus_is_not_counted(db):
    now = time.time()
    await fill_almost(now, POINTS - 1)  # fewer points missing than one item is worth
    left = R.meter_goal - (await releaf.foundation(now)).meter
    assert 0 < left < POINTS
    last = await forager(77, items={RARE: 99})
    done = await releaf.donate(last, RARE, 99, now)
    assert done.bloom_started and done.meter == R.meter_goal and done.given == 1 and done.points == left and done.returned == 98
    assert await last.item_quantity(RARE) == 98


async def test_two_people_giving_at_once_start_one_bloom(db):
    now = time.time()
    await fill_almost(now, POINTS)
    a, b = await forager(701, items={RARE: 5}), await forager(702, items={RARE: 5})
    results = await asyncio.gather(releaf.donate(a, RARE, 5, now), releaf.donate(b, RARE, 5, now), return_exceptions=True)
    wins = [r for r in results if isinstance(r, releaf.Donation)]
    assert len(wins) == 1 and wins[0].bloom_started and isinstance(next(r for r in results if r is not wins[0]), releaf.ReleafError)
    assert (await releaf.foundation(now)).meter == R.meter_goal and len(await releaf.windows()) == 1
    # the loser got everything back, the winner lost only what it gave
    owned = sorted([await a.item_quantity(RARE), await b.item_quantity(RARE)])
    assert owned == [5 - wins[0].given, 5]


async def test_donor_list_ranks_this_rounds_givers(db):
    now = time.time()
    big = await forager(1, items={RARE: 50})
    small = await forager(2, items={LOW: 1})
    await big.set_name("Birch")
    await small.set_name("Alder")
    await releaf.donate(small, LOW, 1, now)
    await releaf.donate(big, RARE, 3, now)
    found = await releaf.foundation(now)
    assert [d.name for d in found.top] == ["Birch", "Alder"] and found.top[0].points == 3 * POINTS and found.givers == 2


# ---- the Bloom's bonus ------------------------------------------------------------------------------------------------------------
async def test_the_bloom_boosts_foraging_xp_for_anyone_and_only_foraging_and_only_while_it_lasts(db):
    outsider = await forager(900)
    before = await xp_multiplier(outsider.id, REG, "foraging")
    await fill(time.time())
    assert await xp_multiplier(outsider.id, REG, "foraging") == pytest.approx(before * (1 + R.bloom_xp))  # (they never gave)
    assert await xp_multiplier(outsider.id, REG, "fishing") < await xp_multiplier(outsider.id, REG, "foraging")  # only foraging gets it
    assert await releaf.xp_bonus(REG) == R.bloom_xp
    assert await releaf.xp_bonus(REG, time.time() + R.bloom_hours * 3600 + 5) == 0


async def test_a_felled_private_tree_pays_more_xp_in_a_bloom(db):
    user = await with_axe(1)
    tree = lambda: f.Tree(1, 100, 0, effort=10.0)  # noqa: E731
    plain = await f.fell_private(user, tree(), Random(1), REG)
    await fill(time.time())
    boosted = await f.fell_private(user, tree(), Random(1), REG)
    assert boosted.xp == round(10.0 * REG.foraging.xp_per_swing * (await xp_multiplier(user.id, REG, "foraging")))
    assert boosted.xp > plain.xp


def test_the_drop_boost_raises_drop_chances_and_zero_boost_changes_nothing():
    reg = REG
    same = f.roll_drops(300, Random(4), reg)
    assert f.roll_drops(300, Random(4), reg, boost=0.0) == same
    rare = next(i for i in f.drop_pool(reg) if i.rarity >= 4 and i.drop.rate >= 100)
    plain = sum(f.roll_drops(60_000, Random(s), reg)[rare.id] for s in range(3))
    boosted = sum(f.roll_drops(60_000, Random(s), reg, boost=1.0)[rare.id] for s in range(3))  # +100%: about twice as many
    assert boosted > plain * 1.5


async def test_a_bloom_boosts_drops_on_private_community_and_party_trees(db):
    now = time.time()
    user = await with_axe(1)
    # private: the boost is read inside fell_private
    seen = []
    real = f.roll_drops

    def spy(*args, **kwargs):
        seen.append(kwargs.get("boost", args[5] if len(args) > 5 else 0.0))
        return real(*args, **kwargs)

    f.roll_drops = spy
    try:
        await f.fell_private(user, f.Tree(1, 100, 0), Random(1), REG)
        assert seen[-1] == 0
        await fill(now)
        await f.fell_private(user, f.Tree(1, 100, 0), Random(1), REG)
        assert seen[-1] == R.bloom_drops
    finally:
        f.roll_drops = real
    # community shares and party trees take the boost too
    shares = f.community_shares(10_000, True, {1: 10_000}, REG.foraging, Random(3), REG, 1, boost=R.bloom_drops)
    assert 1 in shares
    blooms = await releaf.windows()
    hour = f.window_times(f.window_of(now), REG.foraging)
    assert releaf.boost_between(blooms, *hour, R) == R.bloom_drops
    assert releaf.boost_between(blooms, now - 7200, now - 3600, R) == 0
    assert party_tree.releaf is releaf  # (the party tree stores the Bloom it chopped under on the tree)


# ---- screens ---------------------------------------------------------------------------------------------------------------------
async def test_the_releaf_screen_is_reachable_from_foraging_from_the_minimum_level(db, monkeypatch):
    freeze_time(monkeypatch)
    await with_axe(1)
    low, _ = await hub("forage")
    assert not [b for b in buttons(low) if b.label == "Releaf Foundation"]
    user = await forager(2)
    inst = await user.give_instance("tool_axe_starter")
    from cococap.services.equipment import equip

    await equip(user, "foraging", inst.id)
    nav, inter = await hub("forage", user_id=2)
    await click(nav, inter, "Releaf Foundation")
    assert nav.screen.id == "releaf" and f"0/{R.meter_goal}" in all_text(nav)


async def test_giving_from_the_screen_shows_the_loss_and_the_tallies(db):
    user = await forager(1, items={RARE: 4})
    nav, inter = await hub("releaf")
    await choose(nav, inter, select_named(nav, "Give"), RARE)
    text = all_text(nav)
    assert f"{REG.item(RARE).sell_price * 4:,}" in text  # what you would lose
    await click(nav, inter, "Give 1")
    assert await user.item_quantity(RARE) == 3 and f"{POINTS}/{R.meter_goal}" in all_text(nav)
    await click(nav, inter, "Give all (3)")
    assert await user.item_quantity(RARE) == 0 and f"{4 * POINTS}/{R.meter_goal}" in all_text(nav)
    assert f"{4 * POINTS}/{CAP}" in all_text(nav)


async def test_the_screen_shows_the_bloom_and_closes_giving(db):
    await fill(time.time())
    await forager(1, items={RARE: 2})
    nav, inter = await hub("releaf")
    assert "Bloom is up" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Give"), RARE)
    assert all(b.disabled for b in buttons(nav) if b.label and b.label.startswith("Give"))
    forage, _ = await hub("forage")
    assert "Bloom" in all_text(forage)


async def test_the_old_donate_buttons_are_gone_from_the_reward_pages(db, monkeypatch):
    freeze_time(monkeypatch)
    user = await forager(items={})
    inst = await user.give_instance("tool_axe_starter")
    from cococap.services.equipment import equip

    await equip(user, "foraging", inst.id)
    nav, inter = await hub("tree", tree=f.Tree(1, 1, 1))

    class Lucky(Random):
        def random(self):
            return 0.0

    nav.screen.rng = Lucky(1)
    await click(nav, inter, "Overhead")
    assert nav.screen.id == "result" and "TIMBER" in all_text(nav) and not nav.screen.shown.actions
    assert not [b for b in buttons(nav) if b.label and "onate" in b.label]
    assert "Re-leaf" not in all_text(nav) and "double tree" not in all_text(nav).lower()


def test_old_saves_with_the_legacy_double_tree_fields_still_load():
    old = Foraging.model_validate({"xp": 5, "releaf_meter": 30, "double_ready": True, "donations_made_today": 2,
                                   "stats": {"trees_chopped": 3, "double_trees_chopped": 1, "releaf_donations": 4}})
    assert old.xp == 5 and old.stats.releaf_donations == 4
    assert not hasattr(f.Tree(1, 1, 1), "double") and not hasattr(R, "daily_limit")


async def test_the_shared_state_lives_in_the_existing_community_state_table(db):
    from cococap.services import community

    user = await forager(items={RARE: 1})
    await releaf.donate(user, RARE, 1)
    doc = await community.read(releaf.KEY, {})
    assert doc["meter"] == POINTS and doc["lifetime"] == {str(user.id): POINTS}
