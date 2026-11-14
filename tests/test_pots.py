import asyncio
from collections import Counter
from random import Random

import pytest

from cococap.models.skills.fishing import Pot
from cococap.registry import get_registry
from cococap.services import fishing as f
from cococap.services import pets, pots
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, choose, click, find_button, hub, select_named

REG = get_registry()
RULES = REG.fishing
P = RULES.pots
T0 = 1_000_000.0
BEST_PET = {"pot_speed": 0.25, "pot_luck": 0.5}


async def angler(user_id=1, level=None, bits=10**9, materials=None):
    user = await User.get(user_id)
    await user.add_xp("fishing", User.level_to_xp(level or P.min_level) + 1)
    await set_columns(user, purse=bits)
    for item_id, quantity in (materials or {}).items():
        await user.add_item(item_id, quantity)
    return user


async def crafted(user, **materials):
    for item_id, quantity in {**P.craft_items, **materials}.items():
        await user.add_item(item_id, quantity)
    return await pots.craft(user, T0, REG)


# ---- the numbers ----------------------------------------------------------------------------------------------------------------
def test_better_pots_catch_faster_and_hold_more_and_cost_more_to_reach():
    levels = P.levels
    assert [lv.interval_minutes for lv in levels] == sorted((lv.interval_minutes for lv in levels), reverse=True)
    assert [lv.capacity for lv in levels] == sorted(lv.capacity for lv in levels)
    assert [lv.upgrade_bits for lv in levels[1:]] == sorted(lv.upgrade_bits for lv in levels[1:])
    assert levels[0].upgrade_bits == 0 and all(lv.upgrade_items for lv in levels[1:])


def test_you_may_own_more_pots_as_you_level():
    assert [pots.slots_for(lvl, RULES) for lvl in (1, P.min_level - 1, P.min_level, P.slot_levels[1], P.slot_levels[2], 99)] == [0, 0, 1, 2, 3, 3]


def test_there_is_bait_for_sale_and_bait_that_is_only_found():
    baits = [i for i in REG.items.values() if i.bait]
    assert len(baits) >= 4 and all(i.category == "bait" for i in baits)
    assert any(i.buyable for i in baits) and any(not i.buyable for i in baits)  # (the golden roe is only ever found)
    by_price = sorted((i for i in baits if i.buyable), key=lambda i: i.price)
    assert [i.bait.luck for i in by_price] == sorted(i.bait.luck for i in by_price)  # dearer bait is better
    assert [i.bait.speed for i in by_price] == sorted(i.bait.speed for i in by_price)


def manual_per_hour(water, power=3):
    rng = Random(1)
    worth = sum(f.roll_fish(rng, REG, water).sell_price for _ in range(6000)) / 6000
    wait = sum(f.wait_seconds(power, RULES, rng) for _ in range(500)) / 500 * water.wait_multiplier
    return worth * 3600 / (wait + 13)  # (about 13 seconds to pull up and reel in)


@pytest.mark.parametrize("water", RULES.waters, ids=lambda w: w.id)
def test_pots_are_a_side_dish_not_the_main_earner(water):
    """The point of the design: even a fully optimised set of pots earns a fraction of fishing by hand, and a basic one a trifle."""
    manual = manual_per_hour(water)
    basic = pots.hourly_value(Pot(level=1, water=water.id, bait="worm"), REG)
    assert basic < 0.04 * manual, (basic, manual)
    nets = []
    for bait in (i for i in REG.items.values() if i.bait and i.buyable):  # whichever bait pays best in this water, bait cost and all
        top = Pot(level=len(P.levels), water=water.id, bait=bait.id)
        gross = len(P.slot_levels) * pots.hourly_value(top, REG, BEST_PET)
        catches = len(P.slot_levels) * 3600 / pots.interval_seconds(top, REG, BEST_PET)
        nets.append(gross - catches * bait.price)
    assert 0 < max(nets) < 0.40 * manual, (max(nets), manual)  # worth setting up, never worth skipping the rod


@pytest.mark.parametrize("water", RULES.waters, ids=lambda w: w.id)
def test_optimising_really_does_pay_more(water):
    base = pots.hourly_value(Pot(level=1, water=water.id, bait="worm"), REG)
    leveled = pots.hourly_value(Pot(level=5, water=water.id, bait="worm"), REG)
    baited = pots.hourly_value(Pot(level=5, water=water.id, bait="squid_chunk"), REG)
    pet = pots.hourly_value(Pot(level=5, water=water.id, bait="squid_chunk"), REG, BEST_PET)
    assert base < leveled < baited < pet
    assert pet > 5 * base


# ---- making a pot ------------------------------------------------------------------------------------------------------------------
async def test_pots_open_at_the_level_and_cost_bits_and_materials(db):
    newbie = await angler(1, level=P.min_level - 1, materials=P.craft_items)
    with pytest.raises(pots.PotError, match=f"level {P.min_level}"):
        await pots.craft(newbie, T0, REG)
    user = await angler(2, materials={k: v - 1 for k, v in P.craft_items.items()})
    with pytest.raises(pots.PotError, match=r"\d+/\d+"):
        await pots.craft(user, T0, REG)
    assert user.purse == 10**9 and (await user.skill("fishing")).pots == []  # nothing was taken
    pot = await crafted(user)
    assert pot.level == 1 and (await user.skill("fishing")).pots[0].water == "river"  # in the best water you have opened
    await user.refresh()
    assert user.purse == 10**9 - P.craft_bits
    for item_id, quantity in P.craft_items.items():  # crafting used the materials up (the player had one fewer, then was handed a full set)
        assert await user.item_quantity(item_id) == quantity - 1


async def test_you_cannot_own_more_pots_than_your_level_allows(db):
    user = await angler(1)
    await crafted(user)
    with pytest.raises(pots.PotError, match=f"until fishing level {P.slot_levels[1]}"):
        await crafted(user)
    await user.add_xp("fishing", User.level_to_xp(P.slot_levels[1]) + 1)
    await crafted(user)
    assert len((await user.skill("fishing")).pots) == 2


# ---- bait ------------------------------------------------------------------------------------------------------------------------------
async def test_loading_bait_uses_it_up_starts_the_clock_and_stops_at_the_pots_capacity(db):
    user = await angler(1, materials={"worm": 50})
    await crafted(user)
    loaded, returned = await pots.load_bait(user, 0, "worm", 50, T0 + 100, REG)
    assert loaded == P.levels[0].capacity and returned == 0 and await user.item_quantity("worm") == 50 - loaded
    pot = (await user.skill("fishing")).pots[0]
    assert pot.bait == "worm" and pot.bait_left == loaded and pot.since == T0 + 100
    with pytest.raises(pots.PotError, match="already full"):
        await pots.load_bait(user, 0, "worm", 5, T0 + 200, REG)
    with pytest.raises(pots.PotError, match="isn't bait"):
        await pots.load_bait(user, 0, "cod", 1, T0, REG)
    with pytest.raises(pots.PotError, match="don't have any"):
        await pots.load_bait(user, 0, "shrimp", 1, T0, REG)


async def test_topping_up_keeps_the_clock_and_switching_bait_gives_the_old_back(db):
    user = await angler(1, materials={"worm": 20, "shrimp": 20})
    await crafted(user)
    await pots.load_bait(user, 0, "worm", 3, T0, REG)
    await pots.load_bait(user, 0, "worm", 2, T0 + 500, REG)
    pot = (await user.skill("fishing")).pots[0]
    assert pot.bait_left == 5 and pot.since == T0  # topping up doesn't restart the pot
    loaded, returned = await pots.load_bait(user, 0, "shrimp", 4, T0 + 900, REG)
    assert (loaded, returned) == (4, 5) and await user.item_quantity("worm") == 20 - 5 + 5
    pot = (await user.skill("fishing")).pots[0]
    assert pot.bait == "shrimp" and pot.bait_left == 4 and pot.since == T0 + 900


# ---- catching ------------------------------------------------------------------------------------------------------------------------
async def loaded_pot(user_id=1, bait="worm", n=6, level=None, materials=None):
    user = await angler(user_id, level=level, materials={bait: n, **(materials or {})})
    await crafted(user)
    await pots.load_bait(user, 0, bait, n, T0, REG)
    return user


def step_of(user_pot, pet=None):
    return pots.interval_seconds(user_pot, REG, pet)


async def test_nothing_is_ready_at_first_and_catches_accrue_one_per_interval(db):
    user = await loaded_pot()
    pot = (await user.skill("fishing")).pots[0]
    step = step_of(pot)
    assert [pots.ready(pot, T0 + k * step - 1, REG) for k in (1, 2, 3)] == [0, 1, 2]
    assert pots.ready(pot, T0 + 3 * step, REG) == 3
    assert pots.ready(pot, T0 + 10**7, REG) == P.levels[0].capacity  # never more than it holds


async def test_collecting_gives_rare_fish_only_uses_bait_and_a_second_collect_gets_nothing(db):
    user = await loaded_pot(n=6)
    step = step_of((await user.skill("fishing")).pots[0])
    haul = await pots.collect(user, 0, T0 + 4 * step + 5, REG)
    assert haul.catches == 4 and sum(haul.fish.values()) == 4 and haul.xp > 0
    assert all(REG.item(i).rarity >= P.min_rarity for i in haul.fish)  # nothing common ever
    for fish_id, quantity in haul.fish.items():
        assert await user.item_quantity(fish_id) == quantity
    pot = (await user.skill("fishing")).pots[0]
    assert pot.bait_left == 2
    again = await pots.collect(user, 0, T0 + 4 * step + 6, REG)
    assert again.catches == 0 and again.fish == Counter()
    assert pot.since == pytest.approx(T0 + 4 * step)  # the leftover 5 seconds are kept, not thrown away


async def test_the_same_fish_come_up_however_often_you_look(db):
    user = await loaded_pot(n=6)
    pot = (await user.skill("fishing")).pots[0]
    step = step_of(pot)
    a = Counter(pots.roll_catch(pot.water, REG.item("worm"), Random(f"pot:{user.id}:0:{pot.since}"), REG).id for _ in range(1))
    haul = await pots.collect(user, 0, T0 + step + 1, REG)
    assert haul.fish == a  # the one fish is the seeded first roll: looking first changes nothing


async def test_a_pot_that_runs_out_of_bait_stops_and_a_full_pot_wastes_the_wait(db):
    user = await loaded_pot(n=2)
    step = step_of((await user.skill("fishing")).pots[0])
    haul = await pots.collect(user, 0, T0 + 50 * step, REG)
    assert haul.catches == 2  # only two bait
    pot = (await user.skill("fishing")).pots[0]
    assert pot.bait_left == 0 and pot.since == 0.0 and pots.ready(pot, T0 + 99 * step, REG) == 0  # idle until reloaded
    full = await loaded_pot(user_id=2, n=P.levels[0].capacity + 4)
    cap = P.levels[0].capacity
    assert (await full.skill("fishing")).pots[0].bait_left == cap  # it only takes what it can hold
    assert (await pots.collect(full, 0, T0 + 500 * step, REG)).catches == cap  # however long it sat, never more than that


async def test_collect_all_empties_every_pot(db):
    user = await angler(1, level=P.slot_levels[1], materials={"worm": 20})
    await crafted(user)
    await crafted(user)
    for i in (0, 1):
        await pots.load_bait(user, i, "worm", 3, T0, REG)
    step = step_of((await user.skill("fishing")).pots[0])
    haul = await pots.collect_all(user, T0 + 3 * step + 1, REG)
    assert haul.catches == 6 == sum(haul.fish.values())


async def test_pets_and_bait_change_how_fast_and_how_rare(db):
    user = await loaded_pot()
    pot = (await user.skill("fishing")).pots[0]
    assert step_of(pot, {"pot_speed": 0.25}) == pytest.approx(step_of(pot) / 1.25)
    shrimp = Pot(level=1, water="river", bait="shrimp", bait_left=3, since=T0)
    assert step_of(shrimp) == pytest.approx(P.levels[0].interval_minutes * 60 / REG.item("shrimp").bait.speed)

    def rare_share(bait_id, pet):
        rng = Random(7)
        bait = REG.item(bait_id)
        return sum(pots.roll_catch("deep_sea", bait, rng, REG, pet).rarity >= 4 for _ in range(6000)) / 6000

    assert rare_share("worm", None) < rare_share("squid_chunk", None) < rare_share("squid_chunk", BEST_PET)
    assert pots.ready(Pot(bait="worm", bait_left=9, since=T0, level=1), T0 + 5000, REG, {"pot_speed": 1.0}) > \
        pots.ready(Pot(bait="worm", bait_left=9, since=T0, level=1), T0 + 5000, REG)


async def test_a_python_pet_really_speeds_the_pot_up_when_collecting(db):
    user = await loaded_pot(n=6)
    step = step_of((await user.skill("fishing")).pots[0])
    await user.update_pethouse(lambda h: (h.pets.update({"python": __import__("cococap.models.pethouse", fromlist=["x"]).OwnedPet(xp=pets.level_xp(20, REG))}),
                                          setattr(h, "active", "python")))
    haul = await pots.collect(user, 0, T0 + 2.5 * step, REG)
    assert haul.catches > 2  # (without the pet, 2.5 intervals is only two catches)


async def test_the_catch_can_only_be_rare_even_in_the_shallowest_water(db):
    rng = Random(3)
    for water in RULES.waters:
        got = {pots.roll_catch(water.id, REG.item("worm"), rng, REG).rarity for _ in range(2000)}
        assert min(got) >= P.min_rarity, water.id


# ---- levelling and moving pots ---------------------------------------------------------------------------------------------------------
async def test_upgrading_costs_what_the_level_says_and_stops_at_the_top(db):
    user = await angler(1)
    await crafted(user)
    for level in range(2, len(P.levels) + 1):
        cost = P.levels[level - 1]
        with pytest.raises(pots.PotError, match="You still need"):
            await pots.upgrade(user, 0, REG)  # without the materials
        before = user.purse
        for item_id, quantity in cost.upgrade_items.items():
            await user.add_item(item_id, quantity)
        assert (await pots.upgrade(user, 0, REG)).level == level
        await user.refresh()
        assert user.purse == before - cost.upgrade_bits
    with pytest.raises(pots.PotError, match="already at its best"):
        await pots.upgrade(user, 0, REG)


async def test_two_upgrade_clicks_at_once_upgrade_once_and_charge_once(db):
    user = await angler(1)
    await crafted(user)
    cost = P.levels[1]
    for item_id, quantity in cost.upgrade_items.items():
        await user.add_item(item_id, quantity * 2)
    results = await asyncio.gather(pots.upgrade(user, 0, REG), pots.upgrade(user, 0, REG), return_exceptions=True)
    assert sum(isinstance(r, Pot) for r in results) == 1
    await user.refresh()
    assert (await user.skill("fishing")).pots[0].level == 2
    for item_id, quantity in cost.upgrade_items.items():
        assert await user.item_quantity(item_id) == quantity  # only one set was spent


async def test_moving_a_pot_needs_an_open_water_and_nothing_waiting(db):
    user = await loaded_pot(n=6)
    with pytest.raises(pots.PotError, match="haven't opened"):
        await pots.set_water(user, 0, "deep_sea", T0, REG)
    step = step_of((await user.skill("fishing")).pots[0])
    with pytest.raises(pots.PotError, match="Collect"):
        await pots.set_water(user, 0, "pond", T0 + 2 * step, REG)
    await pots.collect(user, 0, T0 + 2 * step, REG)
    await pots.set_water(user, 0, "pond", T0 + 2 * step, REG)
    assert (await user.skill("fishing")).pots[0].water == "pond"


# ---- the screen ----------------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def clock(monkeypatch):
    from cococap.screens import fish as fish_screen

    now = [T0]
    monkeypatch.setattr(fish_screen, "now", lambda: now[0])
    return now


async def test_the_pots_page_is_locked_until_the_level_and_linked_from_fishing(db):
    nav, _ = await hub("fish")
    assert find_button(nav, "Crab pots").disabled
    nav, _ = await hub("fishpots")
    assert "open at fishing level" in all_text(nav)
    await angler(2)
    nav, inter = await hub("fish", user_id=2)
    await click(nav, inter, "Crab pots")
    assert nav.screen.id == "fishpots" and "no pots yet" in all_text(nav)


async def test_crafting_loading_and_collecting_on_the_screen(db, clock):
    user = await angler(1, materials={**P.craft_items, "worm": 10})
    nav, inter = await hub("fishpots")
    await click(nav, inter, "Craft a pot")
    assert "crafted a crab pot" in all_text(nav) and "Pot 1" in all_text(nav) and "no bait" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Load bait"), "worm")
    modal = inter.response.send_modal.await_args.args[0]
    await modal._handler(inter, "all")
    assert "Loaded 6" in all_text(nav) and "Worm ×6" in all_text(nav)
    assert find_button(nav, "Collect all").disabled  # nothing caught yet
    step = step_of((await user.skill("fishing")).pots[0])
    clock[0] = T0 + 3 * step + 1
    await nav.screen.nav.refresh(inter)
    assert "3/6" in all_text(nav) and not find_button(nav, "Collect all").disabled
    await click(nav, inter, "Collect all")
    assert nav.screen.id == "result" and "pots are emptied" in all_text(nav) and "xp" in all_text(nav)
    await click(nav, inter, "Back to the pots")
    assert nav.screen.id == "fishpots" and "Worm ×3" in all_text(nav)  # three baits went into the three catches
    assert (await user.skill("fishing")).stats.fish_caught == 0  # pots don't count as casting yourself


async def test_the_pots_page_shows_upgrade_costs_and_what_a_pot_is_worth(db):
    await angler(1, materials=P.craft_items)
    nav, inter = await hub("fishpots")
    await click(nav, inter, "Craft a pot")
    page = all_text(nav)
    assert find_button(nav, "Upgrade pot 1") and "level 2" in page and "bits an hour" in page and "Fishing yourself earns far more" in page
