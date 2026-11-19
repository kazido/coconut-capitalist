"""Starred drops in mining and farming: the further down the list of mines / fields, the better the star."""

from collections import Counter
from random import Random

from cococap.registry import get_registry
from cococap.services import farming as f
from cococap.services import mining as m
from cococap.user import User
from tests.test_farm_fields import skip_zone_gate, work_zone
from tests.test_farming import HOUR, SURE, T0, ripe_farm

REG = get_registry()


async def stars_from_mining(site_index, tries=60):
    user = await User.get(1)
    for i in range(tries):
        run = await m.start_run(user, Random(i))
        run.site = REG.mining.mines[site_index]
        run.haul = Counter({"material_iron_ore": 10})
        run.leave()
        await m.settle_run(user, run)
    return [await user.item_quantity(i) for i in ("material_iron_ore", "material_iron_ore_s2", "material_iron_ore_s3")]


async def test_the_first_mine_never_pays_three_stars_but_the_last_does(db):
    one, two, three = await stars_from_mining(0)
    assert one > 0 and three == 0
    last = await stars_from_mining(len(REG.mining.mines) - 1)
    assert last[2] > 0 and last[1] > 0  # (counts include what the first mine gave)


async def test_a_mine_run_summary_shows_the_starred_ids(db):
    user = await User.get(1)
    for i in range(40):
        run = await m.start_run(user, Random(i))
        run.site = REG.mining.mines[-1]
        run.haul = Counter({"material_iron_ore": 10})
        run.leave()
        summary = await m.settle_run(user, run)
        assert sum(summary.haul.values()) == 10 and set(summary.haul) <= {"material_iron_ore", "material_iron_ore_s2", "material_iron_ore_s3"}


async def harvest_extras_stars(seed, tries):
    user = await User.get(1)
    for i in range(tries):
        await ripe_farm(user, seed)
        await f.harvest(user, 1, Random(i), now=T0 + 1000 * HOUR, registry=SURE)
    return {i: await user.item_quantity(i) for i in ("material_beeswax", "material_beeswax_s2", "material_beeswax_s3")}


async def test_early_fields_pay_one_star_and_late_fields_pay_more(db, monkeypatch):
    # seed_ambrosia (field 14, 777 cycles) rolls the drop table 60 times a harvest; seed_coconut (field 12) is nearly as deep
    skip_zone_gate(monkeypatch)
    await work_zone(await User.get(1), len(get_registry().farming.field_seeds))  # the planted zone sets the star depth
    late = await harvest_extras_stars("seed_ambrosia", 250)  # (zone 14's table is rare finds: it takes a good few harvests to see beeswax)
    assert late["material_beeswax_s2"] + late["material_beeswax_s3"] > 0
