"""Farm zones: the zone you work decides what you can plant and which byproducts a plot makes; a plot keeps the zone it was planted in."""

from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import farming as f
from cococap.user import User
from tests.test_farm_fields import open_all_zones, work_zone
from tests.test_hub import all_text, choose, hub, select_named

REG = get_registry()
RULES = REG.farming
T0 = 1_800_000_000 // 3600 * 3600


def base(item_id: str) -> str:
    return item_id.split("_s")[0] if item_id[-3:-1] == "_s" else item_id


async def grown(user, number, seed, cycle):
    await user.update_skill("farming", lambda m: setattr(f.plot_of(m, number), "unlocked", True))
    await user.add_item(seed, 1)
    await f.plant(user, number, seed, now=T0, registry=REG)
    await user.update_skill("farming", lambda m: setattr(f.plot_of(m, number), "cycle", cycle))


async def test_only_the_zones_own_seed_and_cheaper_ones_can_be_planted(db):
    user = await User.get(1)
    await open_all_zones(user)
    await work_zone(user, 3)
    await user.update_skill("farming", lambda m: setattr(m.farm.plot_2, "unlocked", True))
    for seed in RULES.field_seeds[:3]:
        await user.add_item(seed, 1)
    await user.add_item(RULES.field_seeds[3], 1)
    with pytest.raises(f.FarmingError):
        await f.plant(user, 1, RULES.field_seeds[3], now=T0, registry=REG)
    await f.plant(user, 1, RULES.field_seeds[2], now=T0, registry=REG)
    await f.plant(user, 2, RULES.field_seeds[0], now=T0, registry=REG)


async def test_a_zone_that_is_not_open_cannot_be_picked(db):
    user = await User.get(1)
    with pytest.raises(f.FarmingError):
        await f.set_zone(user, len(RULES.field_seeds), REG)
    await f.set_zone(user, 1, REG)
    assert await f.current_zone(user, REG) == 1


async def test_a_plot_keeps_its_zone_and_tend_pays_from_that_zones_table(db):
    user = await User.get(1)
    await open_all_zones(user)
    low, high = 1, len(RULES.field_seeds)
    await work_zone(user, low)
    await grown(user, 1, RULES.field_seeds[0], 3)
    await work_zone(user, high)  # moving on does not touch the crop in plot 1
    assert f.plot_zone(f.plot_of(await user.skill("farming"), 1), RULES) == low
    await grown(user, 2, RULES.field_seeds[-1], 3)
    report = await f.tend(user, Random(1), T0, REG)
    allowed = {i.id for z in (low, high) for i in f.zone_materials(z, REG)}
    assert {base(i) for i in report.found} <= allowed
    only_high = {i.id for i in f.zone_materials(high, REG)} - {i.id for i in f.zone_materials(low, REG)}
    assert report.found and only_high & {base(i) for i in report.found}


async def test_tend_in_zone_one_never_finds_another_zones_signature_material(db):
    user = await User.get(1)
    await grown(user, 1, RULES.field_seeds[0], 3)
    found = (await f.tend(user, Random(2), T0, REG)).found
    table = {i.id for i in f.zone_materials(1, REG)}
    assert found and {base(i) for i in found} <= table


async def test_an_old_plot_without_a_zone_uses_its_seeds_own_zone(db):
    user = await User.get(1)
    seed = RULES.field_seeds[4]
    await user.update_skill("farming", lambda m: (setattr(m.farm.plot_1, "crop_id", seed), setattr(m.farm.plot_1, "zone", 0)))
    assert f.plot_zone(f.plot_of(await user.skill("farming"), 1), RULES) == 5


def test_every_zone_has_its_own_signature_material_first():
    assert len(RULES.zone_materials) == len(RULES.field_seeds)
    firsts = [ids[0] for ids in RULES.zone_materials]
    assert len(set(firsts)) == len(firsts)
    for ids in RULES.zone_materials:
        assert all(REG.item(i).skill == "farming" and REG.item(i).drop for i in ids)


async def test_the_farm_page_shows_a_zone_dropdown_once_a_second_zone_is_open(db):
    user = await User.get(1)
    nav, _ = await hub("farm")
    assert "Zone 1" in all_text(nav)
    with pytest.raises(StopIteration):
        select_named(nav, "Zone to work")
    await open_all_zones(user)
    await work_zone(user, 1)
    nav, inter = await hub("farm")
    await choose(nav, inter, select_named(nav, "Zone to work"), "2")
    assert (await user.skill("farming")).zone == 2
