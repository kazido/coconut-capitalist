"""Smithing parts drop from every skill action (one roll per action), never into the stackable items."""

from collections import Counter
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import farming as farm
from cococap.services import fishing as f
from cococap.services import foraging as fg
from cococap.services import mining as m
from cococap.services import smithing
from cococap.user import User
from tests.test_farming import HOUR, SURE, T0 as FARM_T0, ripe_farm
from tests.test_fishing import T0 as FISH_T0, cast_of
from tests.test_hub import all_text, enter_mines, hub, click

REG = get_registry()
RULES = REG.smithing
FOREST = REG.foraging
HARDWOOD = "material_hardwood"


def set_part_chance(monkeypatch, chance: float) -> None:
    rules = RULES.model_copy(update={"part_drop_chance": chance})
    monkeypatch.setattr(smithing, "_rules", lambda registry=None: rules)


async def parts_held(user: User) -> int:
    """Stackable items named part_* must stay at zero: parts are instances, not stock."""
    total = 0
    for part_id in ("part_base", "part_trim", "part_accent"):
        total += await user.item_quantity(part_id)
    return total


def assert_one_part(part, area: int) -> None:
    assert part is not None
    assert part.template_id in ("part_base", "part_trim", "part_accent")
    assert 1 <= part.rolled["tier"] <= RULES.max_tier_for_area(area)


# ---- the helper ---------------------------------------------------------------------------------------------

async def test_chance_one_always_gives_one_part_within_the_area_cap(db, monkeypatch):
    set_part_chance(monkeypatch, 1.0)
    user = await User.get(1)
    for i in range(20):
        part = await smithing.maybe_drop_part(user, 1, Random(i), REG)
        assert_one_part(part, 1)


async def test_chance_zero_never_gives_a_part(db, monkeypatch):
    set_part_chance(monkeypatch, 0.0)
    user = await User.get(1)
    for i in range(50):
        assert await smithing.maybe_drop_part(user, 1, Random(i), REG) is None


# ---- one part per action, in each skill ---------------------------------------------------------------------

async def test_felling_a_tree_drops_one_part(db, monkeypatch):
    set_part_chance(monkeypatch, 1.0)
    monkeypatch.setattr(fg, "roll_drops", lambda *a, **k: Counter({HARDWOOD: 5}))
    user = await User.get(1)
    tree = fg.Tree(1, 100, 100)
    tree.chop(100, 1.0)
    reward = await fg.fell_private(user, tree, Random(3), REG)
    assert_one_part(reward.part, 1)
    assert sum(reward.drops.values()) == 5 and await parts_held(user) == 0


async def test_landing_a_fish_drops_one_part(db, monkeypatch):
    set_part_chance(monkeypatch, 1.0)
    user = await User.get(1)
    cast = cast_of("fish_cod")
    cast.water = REG.fishing.waters[0]
    for arrow in cast.pattern:
        cast.press(arrow, FISH_T0 + 11)
    caught = await f.land(user, cast, REG)
    assert_one_part(caught.part, 1)
    assert await parts_held(user) == 0


async def test_harvesting_a_crop_drops_one_part(db, monkeypatch):
    set_part_chance(monkeypatch, 1.0)
    user = await User.get(1)
    await ripe_farm(user)
    result = await farm.harvest(user, 1, Random(1), now=FARM_T0 + 1000 * HOUR, registry=SURE)
    assert_one_part(result.part, 1)
    assert await parts_held(user) == 0


async def test_settling_a_mine_run_drops_one_part(db, monkeypatch):
    set_part_chance(monkeypatch, 1.0)
    user = await User.get(1)
    run = await m.start_run(user, Random(1))
    run.site = REG.mining.mines[0]
    run.haul = Counter({"material_iron_ore": 10})
    run.leave()
    summary = await m.settle_run(user, run)
    assert_one_part(summary.part, 1)
    assert sum(summary.haul.values()) == 10 and await parts_held(user) == 0


async def test_no_part_when_the_chance_is_zero_in_every_skill(db, monkeypatch):
    set_part_chance(monkeypatch, 0.0)
    monkeypatch.setattr(fg, "roll_drops", lambda *a, **k: Counter({HARDWOOD: 5}))
    user = await User.get(1)
    tree = fg.Tree(1, 100, 100)
    tree.chop(100, 1.0)
    assert (await fg.fell_private(user, tree, Random(3), REG)).part is None
    await ripe_farm(user)
    assert (await farm.harvest(user, 1, Random(1), now=FARM_T0 + 1000 * HOUR, registry=SURE)).part is None


# ---- the result screens say what you found -----------------------------------------------------------------------

def fake_part_drop(monkeypatch, slot: str = "trim", tier: int = 3, traits: list[str] | None = None) -> None:
    """Every skill's one roll gives a part of this type and tier, with the first pool trait (no randomness)."""
    picked = [RULES.trait_pool[0].id] if traits is None else traits

    async def drop(user, location, rng, registry=None):
        return await user.give_instance(f"part_{slot}", rolled={"tier": tier}, traits=picked)

    monkeypatch.setattr(smithing, "maybe_drop_part", drop)


async def test_part_line_names_tier_type_and_traits(db, monkeypatch):
    fake_part_drop(monkeypatch, "trim", 3)
    user = await User.get(1)
    part = await smithing.maybe_drop_part(user, 1, Random(1), REG)
    line = smithing.part_line(part, REG)
    assert "Tier 3" in line and "Trim part" in line
    assert RULES.trait_pool[0].name in line
    assert "Smith with it" in line


async def test_part_line_has_no_parentheses_without_traits(db, monkeypatch):
    fake_part_drop(monkeypatch, "base", 1, traits=[])
    user = await User.get(1)
    part = await smithing.maybe_drop_part(user, 1, Random(1), REG)
    line = smithing.part_line(part, REG)
    assert "Base part" in line and "(" not in line


async def test_mining_result_screen_shows_the_part(db, monkeypatch):
    fake_part_drop(monkeypatch, "trim", 3)
    nav, inter = await enter_mines()
    mine = nav.screen
    mine.run.leave()
    await mine._end(None)
    mine._show_loot()
    await mine.refresh(inter)
    text = all_text(nav)
    assert "Tier 3" in text and "Trim part" in text


async def test_farm_harvest_screen_shows_the_part(db, monkeypatch):
    from tests.test_hub import ripen, open_all_zones

    fake_part_drop(monkeypatch, "accent", 2)
    user = await User.get(1)
    await user.update_skill("farming", lambda m: setattr(m, "starter_given", True))
    await open_all_zones(user)
    await user.add_item("seed_lemon", 5)
    await ripen(user, 1)
    nav, inter = await hub("farm")
    await click(nav, inter, "Harvest all")
    text = all_text(nav)
    assert "Tier 2" in text and "Accent part" in text
