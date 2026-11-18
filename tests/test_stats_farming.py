from pathlib import Path
from random import Random

from cococap.registry import get_registry
from cococap.services import farming as f
from cococap.services import stats_farming
from cococap.user import User
from tests.test_farming import HOUR, MARKET_OPEN, SURE, T0, registry_with, ripe_farm, with_can
from tests.test_hub import all_text, choose, hub, select_named

REG = get_registry()
RULES = REG.farming


async def rows_for(user):
    page = await stats_farming.page(user, await user.stats())
    return page, {label: value for _, lines in page.groups for label, value in lines}


async def test_an_existing_farmer_sees_their_old_numbers_without_any_counter_rows(db):
    user = await User.get(1)

    def old(m):
        m.stats.crops_grown = 40
        m.rain_god_blessings = 2

    await user.update_skill("farming", old)
    _, values = await rows_for(user)
    assert values["Crops harvested"] == 40 and values["Blessings waiting"] == 2
    assert values["Plots watered"] == 0 and values["Most plots ready at once"] == 0


async def test_one_harvest_adds_exactly_its_crop_and_the_total(db):
    user = await User.get(1)
    await ripe_farm(user)
    _, before = await rows_for(user)
    result = await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=SURE)
    _, after = await rows_for(user)
    assert after["Crops harvested"] == before["Crops harvested"] + result.amount
    assert after[REG.item("crop_apple").name] == result.amount
    assert after["Most plots ready at once"] == 1


async def test_one_watering_counts_the_plots_it_took(db):
    user = await User.get(1)
    await with_can(user)
    await user.add_item("seed_apple", 1)
    dry = registry_with(grow_chance=0.0, blessing_chance=0.0)  # no rain, so the seed does not ripen before the watering
    await f.plant(user, 1, "seed_apple", now=T0, registry=dry)
    report = await f.water(user, now=T0 + HOUR, registry=dry)
    _, values = await rows_for(user)
    assert values["Plots watered"] == report.watered == 1


async def test_one_deed_bought_adds_exactly_one(db):
    user = await User.get(1)
    await user.add_item(RULES.deed_item, 1)
    await f.buy_plot(user, RULES.free_plots + 1)
    _, values = await rows_for(user)
    assert values["Deeds bought"] == 1


async def test_market_sales_add_exactly_the_bits_earned(db):
    user = await User.get(1)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.add_item("crop_apple", 10)
    earned, _ = await f.sell_crops(user, MARKET_OPEN)
    _, values = await rows_for(user)
    assert values["Bits from crops sold"] == earned


def test_every_new_counter_is_written_in_the_services():
    services = "".join(p.read_text(encoding="utf-8") for p in (Path(__file__).resolve().parents[1] / "cococap" / "services").glob("*.py"))
    for name in ("harvested:", "anomalies", "tends", "cycles_tended", "plots_watered", "most_ready_at_once", "deeds_bought",
                 "crop_bits_sold", "blessings_deposited", "deeds_from_blessings"):
        assert name in services, name


async def test_the_farming_page_renders_in_the_stats_tab(db):
    user = await User.get(1)
    await user.inc_stat("tends", 3)
    nav, inter = await hub("player", tab="stats")
    await choose(nav, inter, select_named(nav, "Pick a page"), "farming")
    assert "Tends: `3`" in all_text(nav)
