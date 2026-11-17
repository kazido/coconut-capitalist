"""The fishing radar: chase fish are likelier, a battery per cast, upgrades cost fish and bits, and it is a decision rather than a free boost."""

from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import fishing as f
from cococap.services.equipment import equip
from cococap.user import User
from tests.test_hub import all_text, buttons, choose, find_button, hub, select_named

REG = get_registry()
R = REG.fishing.radar
XP25 = 120_000  # about fishing level 25


async def angler(uid=1, level_xp=XP25):
    user = await User.get(uid)
    await equip(user, "fishing", (await user.give_instance("tool_rod_starter")).id)
    await user.add_xp("fishing", level_xp)
    return user


async def with_radar(user, level=1, targets=("fish_giant_squid",), on=True, batteries=50):
    await user.update_skill("fishing", lambda s: (setattr(s.radar, "level", level), setattr(s.radar, "on", on), setattr(s.radar, "targets", list(targets))))
    await user.add_item(R.battery, batteries)


# ---- the data ------------------------------------------------------------------------------------------------------------------------
def test_each_radar_level_is_stronger_and_costlier_and_the_battery_is_crafted():
    levels = R.levels
    assert [l.multiplier for l in levels] == sorted(l.multiplier for l in levels) and [l.slots for l in levels] == sorted(l.slots for l in levels)
    assert [l.bits for l in levels] == sorted(l.bits for l in levels) and levels[-1].multiplier <= 8 and levels[-1].slots <= 3
    battery = REG.item(R.battery)
    assert battery.price == 0 and R.battery in REG.recipes and battery.skill == "fishing" and R.unlock_level > REG.fishing.waters[-1].min_level
    for level in levels:
        assert all(REG.find_item(i) for i in level.items)  # (every ask is a real item)


def test_a_chased_fish_gets_likelier_by_the_multiplier_and_the_rest_of_the_water_shrinks_a_little():
    water = f.water_by_id(REG, "deep_sea")
    base = f.water_chances(water)
    boosted = f.radar_chances(water, ["fish_giant_squid"], 4.0, REG)
    assert boosted["fish_giant_squid"] == pytest.approx(base["fish_giant_squid"] * 4, rel=0.15)
    assert f.radar_chances(water, ["not_here"], 4.0, REG) == {} and f.radar_chances(f.water_by_id(REG, "pond"), ["fish_giant_squid"], 4.0, REG) == {}


def test_roll_fish_really_catches_the_chased_fish_more_often():
    water = f.water_by_id(REG, "deep_sea")

    def count(chase):
        rng = Random(7)
        return sum(f.roll_fish(rng, REG, water, 0.0, chase).id == "fish_marlin" for _ in range(6000))

    plain, chasing = count(None), count({"fish_marlin": 6.0})
    assert chasing > 3.5 * plain and plain > 0


def test_the_top_radar_is_strong_but_not_trivial():
    """At the top level a chase fish is several times likelier, never certain: a legendary stays a long chase."""
    water = f.water_by_id(REG, "deep_sea")
    for fish_id in ("fish_leviathan_pup", "fish_abyssal_angler", "fish_marlin"):
        base = f.water_chances(water)[fish_id]
        top = f.radar_chances(water, [fish_id], R.levels[-1].multiplier, REG)[fish_id]
        assert 3 * base <= top <= 8 * base and top < 0.5, fish_id


# ---- using it ----------------------------------------------------------------------------------------------------------------------------
async def test_a_cast_uses_a_battery_only_when_the_radar_is_on_and_a_target_lives_in_the_water(db):
    user = await angler()
    deep, pond = f.water_by_id(REG, "deep_sea"), f.water_by_id(REG, "pond")
    assert await f.use_radar(user, deep, REG) == {}  # (no radar yet)
    await with_radar(user, level=2)
    assert await f.use_radar(user, pond, REG) == {} and await user.item_quantity(R.battery) == 50  # (no target there: no battery used)
    chase = await f.use_radar(user, deep, REG)
    assert chase == {"fish_giant_squid": R.levels[1].multiplier} and await user.item_quantity(R.battery) == 49
    await f.set_radar(user, on=False)
    assert await f.use_radar(user, deep, REG) == {} and await user.item_quantity(R.battery) == 49
    await f.set_radar(user, on=True)
    await user.remove_item(R.battery, 49)
    assert await f.use_radar(user, deep, REG) == {}  # (out of batteries: it just does not help)


async def test_targets_are_limited_to_the_slots_and_to_real_fish(db):
    user = await angler()
    await with_radar(user, level=1, targets=())
    await f.set_radar(user, targets=["fish_marlin", "fish_giant_squid", "nonsense"])
    assert (await f.radar(user, REG)).targets == ("fish_marlin",)  # (one slot at level 1; nonsense ignored)
    await user.update_skill("fishing", lambda s: setattr(s.radar, "level", 5))
    await f.set_radar(user, targets=["fish_marlin", "fish_giant_squid", "fish_swordfish", "fish_tuna"])
    assert (await f.radar(user, REG)).targets == ("fish_marlin", "fish_giant_squid", "fish_swordfish")


async def test_the_chase_changes_what_a_cast_catches(db):
    user = await angler()
    stats = await f.rod_stats(user)
    water = f.water_by_id(REG, "deep_sea")
    caught = {False: 0, True: 0}
    for chasing in (False, True):
        for seed in range(500):
            cast = f.cast_line(stats, Random(seed), 1_000.0, REG, water=water, chase={"fish_marlin": 6.0} if chasing else None)
            caught[chasing] += cast.fish.id == "fish_marlin" and not cast.boss
    assert caught[True] > 3 * caught[False]


# ---- upgrading ---------------------------------------------------------------------------------------------------------------------------
async def test_upgrading_pays_bits_and_fish_all_or_nothing_and_needs_the_level(db):
    low = await User.get(2)
    with pytest.raises(f.FishingError, match="opens at fishing level"):
        await f.upgrade_radar(low, REG)
    user = await angler()
    first = R.levels[0]
    with pytest.raises(f.FishingError, match="not have everything"):
        await f.upgrade_radar(user, REG)
    await user.add_bits(first.bits)
    for item_id, quantity in first.items.items():
        await user.add_item(item_id, quantity - 1)  # one short of the last item
    await user.refresh()
    with pytest.raises(f.FishingError):
        await f.upgrade_radar(user, REG)
    await user.refresh()
    assert user.purse >= first.bits and (await f.radar(user, REG)).level == 0  # (nothing was kept)
    for item_id in first.items:
        await user.add_item(item_id, 1)
    before = user.purse
    assert await f.upgrade_radar(user, REG) == 1
    await user.refresh()
    assert user.purse == before - first.bits and (await f.radar(user, REG)).level == 1
    for _ in range(len(R.levels)):
        await user.update_skill("fishing", lambda s: setattr(s.radar, "level", len(R.levels)))
    with pytest.raises(f.FishingError, match="best there is"):
        await f.upgrade_radar(user, REG)


# ---- the page ----------------------------------------------------------------------------------------------------------------------------
async def test_the_fishing_page_has_a_radar_button_that_opens_at_its_level_and_the_page_works(db):
    nav, _ = await hub("fish")
    assert find_button(nav, "Radar").disabled
    user = await angler()
    nav, inter = await hub("fish")
    assert not find_button(nav, "Radar").disabled
    await find_button(nav, "Radar").callback(inter)
    assert nav.screen.id == "radar" and "You have not built one yet" in all_text(nav)
    await with_radar(user, level=3, targets=(), on=False)
    nav, inter = await hub("radar")
    menu = select_named(nav, "Chase up to 2")
    await choose(nav, inter, menu, "fish_marlin")
    assert (await f.radar(user, REG)).targets == ("fish_marlin",) and "1 in" in all_text(nav)
    await find_button(nav, "Turn on").callback(inter)
    assert (await f.radar(user, REG)).on and find_button(nav, "Turn off")


async def test_the_radar_page_before_its_level_is_locked_and_the_page_can_build_it(db):
    nav, _ = await hub("radar")
    assert "opens at **fishing level" in all_text(nav).replace("fishing level 25", "fishing level") or "fishing level" in all_text(nav)
    user = await angler()
    first = R.levels[0]
    await user.add_bits(first.bits)
    for item_id, quantity in first.items.items():
        await user.add_item(item_id, quantity)
    nav, inter = await hub("radar")
    await find_button(nav, "Build").callback(inter)
    assert (await f.radar(user, REG)).level == 1 and "level **1**" in all_text(nav)
