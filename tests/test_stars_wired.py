"""Starred drops in mining and farming: the further down the list of mines / fields, the better the star."""

from collections import Counter
from random import Random

from cococap.registry import get_registry
from cococap.services import farming as f
from cococap.services import mining as m
from cococap.services import stars
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
    return [await user.item_quantity(i) for i in IRON_IDS]


IRON_IDS = ["material_iron_ore"] + [stars.star_id("material_iron_ore", n) for n in (1, 2, 3)]  # plain, 1-, 2-, 3-star


async def test_the_first_mine_never_pays_two_or_three_stars_but_the_last_does(db):
    plain, one, two, three = await stars_from_mining(0)
    assert plain > 0 and one > 0 and two == 0 and three == 0  # the curve gives no 2- or 3-star at progress 0
    last = await stars_from_mining(len(REG.mining.mines) - 1)
    assert last[3] > 0 and last[2] > 0  # (counts include what the first mine gave)


async def test_a_mine_run_summary_shows_the_starred_ids(db):
    user = await User.get(1)
    for i in range(40):
        run = await m.start_run(user, Random(i))
        run.site = REG.mining.mines[-1]
        run.haul = Counter({"material_iron_ore": 10})
        run.leave()
        summary = await m.settle_run(user, run)
        assert sum(summary.haul.values()) == 10 and set(summary.haul) <= set(IRON_IDS)


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
    late = await harvest_extras_stars("seed_ambrosia", 3)
    assert late["material_beeswax_s2"] + late["material_beeswax_s3"] > 0
