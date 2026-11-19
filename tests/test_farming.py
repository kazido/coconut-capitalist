import asyncio
import copy
import datetime
from collections import Counter
from random import Random

import pytest

from cococap.models.skills.farming import Farming
from cococap.registry import get_registry
from cococap.services import farming as f
from cococap.user import Cooldowns, User
from tests.test_farm_fields import skip_zone_gate, work_zone
from tests.test_hub import all_text, choose, click, hub, select_named

REG = get_registry()
RULES = REG.farming
HOUR = 3600
T0 = 1_800_000_000 // HOUR * HOUR  # a clean hour boundary


@pytest.fixture(autouse=True)
async def every_zone_open(db, monkeypatch):
    """Most tests here plant any crop, so skip the zone gate and work the last zone (for both test players)."""
    skip_zone_gate(monkeypatch)
    for user_id in (1, 2, 3):
        await work_zone(await User.get(user_id), len(RULES.field_seeds))


async def with_can(user, template="tool_can_tin"):
    """Give a player a watering can and equip it (watering needs one)."""
    from cococap.services.equipment import equip

    inst = await user.give_instance(template)
    await equip(user, "farming", inst.id)
    return inst


def registry_with(**changes):
    """A copy of the registry whose farming rules are tweaked (rules are frozen, so rebuild them)."""
    reg = copy.copy(REG)
    market = changes.pop("market", None)
    farming = RULES.model_copy(update=changes)
    if market:
        farming = farming.model_copy(update={"market": RULES.market.model_copy(update=market)})
    reg.farming = farming
    return reg


SURE = registry_with(grow_chance=1.0, blessing_chance=0.0)  # it rains and everything grows, no blessings
UTC = datetime.UTC


def at(year, month, day, hour=12):
    return datetime.datetime(year, month, day, hour, tzinfo=UTC).timestamp()


FRIDAY, THURSDAY, SATURDAY, SUNDAY = at(2026, 11, 13), at(2026, 11, 12), at(2026, 11, 14), at(2026, 11, 15)  # all 12:00 UTC (open)
OPENS, OPEN_HOURS = sorted(REG.farming.market.opens), REG.farming.market.open_hours
CLOSED = FRIDAY - 12 * 3600  # midnight UTC
MARKET_OPEN = FRIDAY - 12 * 3600 + OPENS[0] * 3600 + 60  # a minute after the first opening


async def farmer(**items):
    user = await User.get(1)
    for item, quantity in items.items():
        await user.add_item(item, quantity)
    return user


# ---- the rain ----------------------------------------------------------------------------------------------
def seeded_farm(seed_id="seed_coconut", since=0, plot=1):
    farming = Farming()
    p = f.plot_of(farming, plot)
    p.crop_id, p.since = seed_id, since
    return farming


def test_the_hour_boundaries():
    assert f.hour_of(T0) == f.hour_of(T0 + HOUR - 1) == T0 // HOUR
    assert f.next_rain(T0 + 5) == T0 + HOUR


def test_a_three_cycle_seed_needs_exactly_three_sure_rains():
    # hot pepper: 20 cycles; use a custom 3-cycle one by looking for any seed with few cycles
    seed = next(i for i in REG.items.values() if i.seed and i.seed.cycles == 1)  # 1 cycle seeds exist (apple, lemon...)
    farm = seeded_farm(seed.id, since=T0 // HOUR)
    report = f.apply_rain(farm, 1, T0 + HOUR, SURE)  # one rain has fallen since planting
    assert f.plot_of(farm, 1).can_harvest and report.matured == (1,)
    slow = seeded_farm("seed_hot_pepper", since=T0 // HOUR)
    f.apply_rain(slow, 1, T0 + 19 * HOUR, SURE)
    assert f.plot_of(slow, 1).cycle == 19 and not f.plot_of(slow, 1).can_harvest
    f.apply_rain(slow, 1, T0 + 20 * HOUR, SURE)
    assert f.plot_of(slow, 1).can_harvest


def test_looking_twice_in_the_same_hour_changes_nothing():
    farm = seeded_farm("seed_hot_pepper", since=T0 // HOUR)
    f.apply_rain(farm, 1, T0 + 7 * HOUR, REG)
    snapshot = farm.model_dump()
    f.apply_rain(farm, 1, T0 + 7 * HOUR + 1800, REG)
    assert farm.model_dump() == snapshot


def test_catching_up_at_once_equals_living_through_every_hour():
    """The core promise: offline time counts exactly like being there, and reopening can't re-roll anything."""
    for uid in range(1, 25):
        once = seeded_farm("seed_coconut", since=T0 // HOUR)
        stepped = seeded_farm("seed_coconut", since=T0 // HOUR)
        f.apply_rain(once, uid, T0 + 150 * HOUR, REG)
        for h in range(1, 151):
            f.apply_rain(stepped, uid, T0 + h * HOUR, REG)
        assert once.model_dump() == stepped.model_dump(), uid


def test_rain_is_deterministic_per_player_and_differs_between_players():
    def cycles(uid):
        farm = seeded_farm("seed_coconut", since=T0 // HOUR)
        f.apply_rain(farm, uid, T0 + 60 * HOUR, REG)
        return f.plot_of(farm, 1).cycle

    assert cycles(1) == cycles(1)
    assert len({cycles(uid) for uid in range(1, 30)}) > 3  # not everyone gets the same weather


def test_growth_matches_the_chance_in_the_long_run():
    total = 0
    for uid in range(1, 200):
        farm = seeded_farm("seed_ambrosia", since=T0 // HOUR)  # 777 cycles: never finishes in this window
        f.apply_rain(farm, uid, T0 + 100 * HOUR, REG)
        total += f.plot_of(farm, 1).cycle
    assert total / (199 * 100) == pytest.approx(RULES.grow_chance, abs=0.03)


def test_a_blessing_can_only_fall_in_a_rain_where_something_grew():
    reg = registry_with(grow_chance=1.0, blessing_chance=1.0)
    farm = seeded_farm("seed_ambrosia", since=T0 // HOUR)
    report = f.apply_rain(farm, 1, T0 + 10 * HOUR, reg)
    assert report.blessings == 10 and farm.rain_god_blessings == 10
    empty = Farming()
    assert f.apply_rain(empty, 1, T0 + 10 * HOUR, reg).blessings == 0  # nothing planted: no blessings


def test_two_plots_growing_in_the_same_rain_bring_one_blessing_chance_not_two():
    reg = registry_with(grow_chance=1.0, blessing_chance=1.0)
    farm = seeded_farm("seed_ambrosia", since=T0 // HOUR, plot=1)
    other = f.plot_of(farm, 2)
    other.crop_id, other.since = "seed_ambrosia", T0 // HOUR
    assert f.apply_rain(farm, 1, T0 + 4 * HOUR, reg).blessings == 4


def test_a_ripe_plot_stops_growing_and_an_empty_one_is_ignored():
    farm = seeded_farm("seed_apple", since=T0 // HOUR)
    f.apply_rain(farm, 1, T0 + 50 * HOUR, SURE)
    assert f.plot_of(farm, 1).cycle == REG.item("seed_apple").seed.cycles
    assert f.plot_of(farm, 2).crop_id is None and f.plot_of(farm, 2).cycle == 0


# ---- plots and planting -----------------------------------------------------------------------------------------
async def test_plot_one_is_free_and_the_rest_need_land_deeds(db):
    free = RULES.free_plots
    user = await farmer(key_land_deed=1)
    farming = await user.skill("farming")
    assert f.is_unlocked(farming, free, RULES) and not f.is_unlocked(farming, free + 1, RULES)
    await f.buy_plot(user, free + 1)
    assert f.is_unlocked(await user.skill("farming"), free + 1, RULES) and await user.item_quantity("key_land_deed") == 0
    with pytest.raises(f.FarmingError, match="already own"):
        await f.buy_plot(user, free + 1)
    with pytest.raises(f.FarmingError, match="Land Deed"):
        await f.buy_plot(user, free + 2)
    for bad in (0, free, 10):
        with pytest.raises(f.FarmingError, match="can't be bought"):
            await f.buy_plot(user, bad)


async def test_planting_uses_a_seed_and_only_goes_on_an_empty_plot_you_own(db):
    user = await farmer(seed_apple=2)
    await f.plant(user, 1, "seed_apple", now=T0)
    assert await user.item_quantity("seed_apple") == 1
    plot = f.plot_of(await user.skill("farming"), 1)
    assert plot.crop_id == "seed_apple" and plot.cycle == 0 and plot.since == T0 // HOUR
    with pytest.raises(f.FarmingError, match="already growing"):
        await f.plant(user, 1, "seed_apple", now=T0)
    assert await user.item_quantity("seed_apple") == 1  # the failed attempt cost nothing
    with pytest.raises(f.FarmingError, match="don't own"):
        await f.plant(user, RULES.free_plots + 1, "seed_apple", now=T0)
    assert await user.item_quantity("seed_apple") == 1


async def test_you_cannot_plant_what_is_not_a_seed_or_what_you_do_not_have(db):
    user = await farmer(material_copper_ore=5)
    with pytest.raises(f.FarmingError, match="isn't a seed"):
        await f.plant(user, 1, "material_copper_ore", now=T0)
    with pytest.raises(f.FarmingError, match="don't have any"):
        await f.plant(user, 1, "seed_apple", now=T0)
    assert await user.item_quantity("material_copper_ore") == 5


async def test_a_seed_planted_now_only_feels_the_rain_that_falls_afterwards(db):
    user = await farmer(seed_apple=1)
    await f.plant(user, 1, "seed_apple", now=T0 + 30)  # mid-hour
    farming, report = await f.sync(user, T0 + 40, SURE)
    assert report.rains == 0 and not f.plot_of(farming, 1).can_harvest  # this hour's rain already fell
    farming, report = await f.sync(user, T0 + HOUR + 1, SURE)
    assert f.plot_of(farming, 1).can_harvest


# ---- xp follows the waiting ------
async def test_a_longer_crop_pays_more_xp_in_proportion_to_its_growth_time(db):
    xp = {}
    for seed in ("seed_apple", "seed_coconut"):
        user = await farmer()
        await ripe_farm(user, seed)
        xp[seed] = (await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=SURE)).xp
        await user.update_skill("farming", lambda m: setattr(m, "xp", 0))
        await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "crop_id", None))
    assert xp["seed_apple"] == REG.item("seed_apple").seed.cycles * RULES.xp_per_cycle
    assert xp["seed_coconut"] == REG.item("seed_coconut").seed.cycles * RULES.xp_per_cycle > 50 * xp["seed_apple"]


# ---- harvesting ------------------------------------------------------------------------------------------------
async def ripe_farm(user, seed="seed_apple"):
    await user.add_item(seed, 1)
    await f.plant(user, 1, seed, now=T0, registry=SURE)
    await f.sync(user, T0 + 1000 * HOUR, SURE)


async def test_harvesting_gives_crops_xp_and_empties_the_plot_exactly_once(db):
    user = await farmer()
    await ripe_farm(user)
    crop = REG.item("crop_apple")
    result = await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=SURE)
    assert result.crop_id == "crop_apple" and crop.crop.min_harvest <= result.amount <= crop.crop.max_harvest
    assert await user.item_quantity("crop_apple") == result.amount
    skill = await user.skill("farming")
    assert skill.xp == REG.item("seed_apple").seed.cycles * RULES.xp_per_cycle == result.xp and skill.stats.crops_grown == result.amount
    assert f.plot_of(skill, 1).crop_id is None
    with pytest.raises(f.FarmingError, match="Nothing is ready"):
        await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=SURE)
    assert await user.item_quantity("crop_apple") == result.amount  # no second payout


async def test_two_harvest_clicks_at_once_pay_once(db):
    user = await farmer()
    await ripe_farm(user)
    results = await asyncio.gather(
        *(f.harvest(user, 1, Random(i), now=T0 + 1000 * HOUR, registry=SURE) for i in range(2)), return_exceptions=True
    )
    paid = [r for r in results if isinstance(r, f.Harvest)]
    assert len(paid) == 1 and await user.item_quantity("crop_apple") == paid[0].amount


async def test_an_unripe_plot_cannot_be_harvested(db):
    user = await farmer(seed_coconut=1)
    await f.plant(user, 1, "seed_coconut", now=T0)
    with pytest.raises(f.FarmingError, match="Nothing is ready"):
        await f.harvest(user, 1, Random(1), now=T0 + HOUR, registry=SURE)


async def test_an_anomaly_refreshes_work_and_daily_but_not_weekly(db):
    user = await farmer()
    for command in Cooldowns:
        await user.claim_cooldown(command)
    await ripe_farm(user)
    always = registry_with(grow_chance=1.0, blessing_chance=0.0, anomaly_odds=1)
    result = await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=always)
    assert result.anomaly
    await user.refresh()
    assert user.get_cooldown(Cooldowns.WORK) == 0 and user.get_cooldown(Cooldowns.DAILY) == 0
    assert user.get_cooldown(Cooldowns.WEEKLY) > 0


async def test_anomalies_happen_about_one_harvest_in_twenty_five(db):
    rng, hits = Random(7), 0
    for _ in range(2500):
        hits += rng.randint(1, RULES.anomaly_odds) == 1
    assert RULES.anomaly_odds == 25 and 70 < hits < 135  # the wiki's 1/25


async def test_harvest_all_takes_every_ripe_plot(db):
    user = await farmer(seed_apple=3, key_land_deed=2)
    for n in range(RULES.free_plots + 1, 4):  # (any plot you do not already have)
        await f.buy_plot(user, n)
    for n in (1, 2, 3):
        await f.plant(user, n, "seed_apple", now=T0, registry=SURE)
    results = await f.harvest_all(user, Random(1), now=T0 + 10 * HOUR, registry=SURE)
    assert [r.plot for r in results] == [1, 2, 3]
    assert await user.item_quantity("crop_apple") == sum(r.amount for r in results)
    assert await f.harvest_all(user, Random(1), now=T0 + 10 * HOUR, registry=SURE) == []


# ---- the Farmer's Market -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("day", [THURSDAY, FRIDAY, SATURDAY, SUNDAY])
def test_the_market_is_open_every_day_for_a_few_hours_at_each_opening(day):
    for hour in OPENS:
        start = day - 12 * 3600 + hour * 3600  # that day's opening
        assert f.market_window(start, REG)[0] is True
        assert f.market_window(start + OPEN_HOURS * 3600 - 1, REG)[0] is True
        assert f.market_window(start + OPEN_HOURS * 3600, REG)[0] is False
        assert f.market_window(start - 1, REG)[0] is False


def test_the_market_says_when_it_next_changes():
    first, second = (FRIDAY - 12 * 3600 + h * 3600 for h in (OPENS[0], OPENS[-1]))
    assert f.market_window(first, REG)[1] == first + OPEN_HOURS * 3600  # closes
    assert f.market_window(first + OPEN_HOURS * 3600, REG)[1] == second  # opens again later today
    assert f.market_window(second + OPEN_HOURS * 3600, REG)[1] == first + 86400  # opens tomorrow
    assert f.market_window(first - 1, REG)[1] == first  # opens today


def test_the_market_opens_twice_a_day_without_overlapping():
    assert len(OPENS) == 2 and OPENS[1] - OPENS[0] >= OPEN_HOURS and 24 - OPENS[1] + OPENS[0] >= OPEN_HOURS


async def test_the_market_needs_level_five_and_an_open_day(db):
    user = await farmer(crop_apple=10)
    with pytest.raises(f.FarmingError, match="level 5"):
        await f.sell_crops(user, MARKET_OPEN)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    with pytest.raises(f.FarmingError, match="closed"):
        await f.sell_crops(user, CLOSED)
    assert await user.item_quantity("crop_apple") == 10  # nothing was taken


async def test_selling_at_the_market_pays_the_bonus_and_only_takes_crops(db):
    user = await farmer(crop_apple=10, crop_lemon=2, material_copper_ore=7, seed_apple=3)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    before = (await User.get(1)).purse
    earned, sold = await f.sell_crops(user, MARKET_OPEN)
    expected = int(REG.item("crop_apple").sell_price * 10 * 1.5) + int(REG.item("crop_lemon").sell_price * 2 * 1.5)
    assert earned == expected and sold == Counter(crop_apple=10, crop_lemon=2)
    await user.refresh()
    assert user.purse == before + earned
    assert await user.item_quantity("material_copper_ore") == 7 and await user.item_quantity("seed_apple") == 3  # untouched
    with pytest.raises(f.FarmingError, match="no crops"):
        await f.sell_crops(user, MARKET_OPEN)


async def test_market_prices_beat_the_shop(db):
    assert f.market_price("crop_apple", 1, REG) > REG.item("crop_apple").sell_price


async def test_blessings_turn_into_land_deeds_at_the_market(db):
    user = await farmer()
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.update_skill("farming", lambda m: setattr(m, "rain_god_blessings", 5))
    with pytest.raises(f.FarmingError, match="closed"):
        await f.deposit_blessings(user, Random(1), CLOSED)
    lucky = registry_with(market={"deed_chance": 1.0})
    used, deeds = await f.deposit_blessings(user, Random(1), MARKET_OPEN, lucky)
    assert (used, deeds) == (5, 5) and await user.item_quantity("key_land_deed") == 5
    assert (await user.skill("farming")).rain_god_blessings == 0
    with pytest.raises(f.FarmingError, match="no rain god"):
        await f.deposit_blessings(user, Random(1), MARKET_OPEN, lucky)


async def test_blessings_only_sometimes_become_deeds(db):
    user = await farmer()
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.update_skill("farming", lambda m: setattr(m, "rain_god_blessings", 400))
    used, deeds = await f.deposit_blessings(user, Random(3), MARKET_OPEN)
    assert used == 400 and 15 < deeds < 70  # about 1 in 10


def test_land_deeds_and_the_farming_rules_are_real_data():
    assert REG.item("key_land_deed").category == "key_item" and RULES.market.min_level == 5
    assert RULES.free_plots >= 1 and RULES.anomaly_odds == 25 and RULES.blessing_chance == 0.1


# ---- getting started: a gift, cheap first seeds, and watering --------------------------------------------------------------------
async def test_every_farmer_gets_free_starter_seeds_once(db):
    user = await User.get(1)
    gift = await f.starter_gift(user, REG)
    assert gift == RULES.starter_seeds and await user.item_quantity("seed_apple") == RULES.starter_seeds["seed_apple"]
    assert await f.starter_gift(user, REG) == {}  # once only
    assert await user.item_quantity("seed_apple") == RULES.starter_seeds["seed_apple"]
    assert (await user.skill("farming")).starter_given


def test_the_first_seeds_are_cheap_enough_for_a_brand_new_player():
    start = 1_000  # what a new player has
    assert REG.item("seed_apple").price * 2 <= start  # a couple of apple seeds is well within reach
    assert REG.item("seed_apple").price < REG.item("seed_lemon").price < REG.item("seed_hot_pepper").price


async def test_watering_grows_plots_you_have_not_watered_this_hour_and_only_once_an_hour(db):
    user = await User.get(1)
    await with_can(user)
    await user.add_item("seed_apple", 1)
    await f.plant(user, 1, "seed_apple", now=T0, registry=REG)
    first = await f.water(user, T0, REG)
    assert first.watered == 1
    again = await f.water(user, T0 + 10, REG)  # the same hour
    assert again.watered == 0 and again.grew == 0
    plot = (await user.skill("farming")).farm.plot_1
    assert plot.watered == int(T0 // 3600)
    later = await f.water(user, T0 + 3600 * 1.1, REG)  # the next hour: allowed again (if it still grows)
    assert later.watered in (0, 1)  # (0 only if it was already ripe)


async def test_a_watering_grows_a_plot_about_as_often_as_the_water_chance_says_and_the_roll_cannot_be_redone(db):
    grew = 0
    for uid in range(1, 301):
        user = await User.get(uid)
        await with_can(user)
        await work_zone(user, len(RULES.field_seeds))
        await user.add_item("seed_coconut", 1)
        await f.plant(user, 1, "seed_coconut", now=T0, registry=REG)
        before = (await user.skill("farming")).farm.plot_1.cycle
        report = await f.water(user, T0, REG)
        grew += report.grew
        assert (await user.skill("farming")).farm.plot_1.cycle == before + report.grew
        assert (await f.water(user, T0, REG)).watered == 0  # looking again changes nothing
    assert grew == 300  # a watering ALWAYS grows a cycle now (water_chance is 100%)


async def test_watering_can_finish_a_one_cycle_crop_straight_away(db):
    for uid in range(1, 60):
        user = await User.get(uid)
        await with_can(user)
        await user.add_item("seed_apple", 1)
        await f.plant(user, 1, "seed_apple", now=T0, registry=REG)
        report = await f.water(user, T0, REG)
        plot = (await user.skill("farming")).farm.plot_1
        assert plot.can_harvest == bool(report.grew) and (report.matured == (1,)) == plot.can_harvest
    assert REG.item("seed_apple").seed.cycles == 1


async def test_watering_skips_empty_and_ripe_plots(db):
    user = await User.get(1)
    await with_can(user)
    assert (await f.water(user, T0, REG)).watered == 0
    await user.add_item("seed_apple", 1)
    await f.plant(user, 1, "seed_apple", now=T0, registry=REG)
    await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
    assert (await f.water(user, T0, REG)).watered == 0


async def test_the_farm_page_waters_and_marks_watered_plots(db):
    from tests.test_hub import all_text, click, find_button, hub

    user = await User.get(1)
    await with_can(user)
    nav, inter = await hub("farm")
    assert "free seeds" in all_text(nav) or "seeds to start" in all_text(nav)  # the welcome gift
    assert find_button(nav, "Water").disabled  # nothing is planted yet
    await click(nav, inter, "1 Plant")
    assert not find_button(nav, "Water").disabled
    await click(nav, inter, "Water")
    assert "You watered 1 plot" in all_text(nav)
    assert find_button(nav, "Water").disabled and "💧" in all_text(nav)  # watered: wait for the next hour
    assert user


# ---- how long will it take? ---------------------------------------------------------------------------------------------------------------
def test_the_estimate_says_how_long_a_crop_will_take_and_how_lucky_or_unlucky_it_could_be():
    rules = REG.farming
    one = f.estimate(1, rules)
    assert one.typical == pytest.approx(1 / rules.grow_chance) and one.early == 1 and one.late >= 3
    assert f.estimate(0, rules) == f.Estimate(0.0, 0, 0)
    for cycles in (2, 20, 100, 777):
        e = f.estimate(cycles, rules)
        assert e.early < e.typical < e.late
        assert e.typical == pytest.approx(cycles / rules.grow_chance)
    assert f.estimate(20, rules).typical > f.estimate(5, rules).typical
    watered = f.estimate(20, rules, watered=True)
    assert watered.typical == pytest.approx(20 / f.hourly_chance(rules, True))
    assert watered.typical < f.estimate(20, rules).typical / 1.5
    assert "about" in one.text() and "days" in f.estimate(100, rules).text()


def test_the_estimate_matches_what_the_rain_really_does():
    """Grow 5000 seeds for real, hour by hour, with the same odds, and see that the middle 80% falls inside the estimate."""
    rules, rng = REG.farming, Random(4)
    for cycles in (3, 20, 100):
        times = sorted(_hours_to_grow(cycles, rules.grow_chance, rng) for _ in range(3000))
        e = f.estimate(cycles, rules)
        assert abs(sum(times) / len(times) - e.typical) < 0.04 * e.typical
        assert abs(times[300] - e.early) <= 1 + 0.03 * e.early and abs(times[2700] - e.late) <= 1 + 0.03 * e.late


def _hours_to_grow(cycles, chance, rng):
    hours = grown = 0
    while grown < cycles:
        hours += 1
        grown += rng.random() < chance
    return hours


async def test_the_farm_page_and_the_seed_menu_show_the_wait_before_you_plant(db):
    user = await User.get(1)
    await user.add_item("seed_lemon", 2)
    nav, inter = await hub("farm")
    menu = select_named(nav, "Seed to plant")
    lemon = next(o for o in menu.options if o.value == "seed_lemon")
    assert f"{REG.item('seed_lemon').seed.cycles} cycles" in lemon.description and "~" in lemon.description  # a short wait in the menu
    await choose(nav, inter, menu, "seed_lemon")
    await click(nav, inter, "1 Plant")
    assert "ready in about" in all_text(nav) and "(" in all_text(nav)  # the full range once, when you plant
    line = next(l for l in all_text(nav).split("\n") if l.startswith("**1**"))
    assert "~" in line and "about" not in line and "(" not in line  # the plot's own line stays short


# ---- the watering can ---------------------------------------------------------------------------------------------------------------------
async def plant_many(user, count):
    """Own `count` plots, all planted with apples (a one-cycle crop that is never ripe before it is watered here)."""
    await user.update_skill("farming", lambda m: [setattr(getattr(m.farm, f"plot_{n}"), "unlocked", True) for n in range(1, 10)])
    await user.add_item("seed_coconut", count)
    for number in range(1, count + 1):
        await f.plant(user, number, "seed_coconut", now=T0, registry=REG)


async def test_watering_needs_a_can(db):
    user = await User.get(1)
    await user.add_item("seed_apple", 1)
    await f.plant(user, 1, "seed_apple", now=T0, registry=REG)
    with pytest.raises(f.FarmingError, match="watering can"):
        await f.water(user, T0, REG)


def test_a_watering_always_grows_a_cycle():
    assert RULES.water_chance == 1.0
    assert f.hourly_chance(RULES, watered=True) == 1.0


async def test_a_can_only_waters_as_many_plots_an_hour_as_its_power(db):
    user = await User.get(1)
    can = await with_can(user)
    await plant_many(user, 6)
    power = REG.item("tool_can_tin").tool.power
    report = await f.water(user, T0, REG)
    assert (report.watered, report.thirsty, report.capacity) == (power, 6 - power, power) and report.grew == power
    plots = (await user.skill("farming")).farm
    assert [getattr(plots, f"plot_{n}").watered == T0 // HOUR for n in range(1, 7)] == [True] * power + [False] * (6 - power)  # lowest numbers first
    again = await f.water(user, T0 + 60, REG)
    assert again.watered == 0 and again.thirsty == 6 - power  # the can is spent for this hour
    await user.update_skill("farming", lambda m: None)
    nxt = await f.water(user, T0 + HOUR + 60, REG)
    assert nxt.watered == power  # a new hour: the can is full again
    assert can.id


async def test_a_better_can_waters_more_plots(db):
    user = await User.get(1)
    await with_can(user, "tool_can_iron")
    await plant_many(user, 6)
    report = await f.water(user, T0, REG)
    assert report.watered == REG.item("tool_can_iron").tool.power == 5 and report.thirsty == 1


async def test_plots_watered_before_a_new_one_is_planted_still_use_up_the_can(db):
    user = await User.get(1)
    await with_can(user)
    await plant_many(user, 3)
    assert (await f.water(user, T0, REG)).watered == 3
    await user.add_item("seed_coconut", 1)
    await f.plant(user, 4, "seed_coconut", now=T0, registry=REG)
    late = await f.water(user, T0 + 30, REG)
    assert late.watered == 0 and late.thirsty == 1  # the can was already used on three plots this hour


def test_the_can_chain_is_a_chain_of_waters_that_ends_at_the_whole_farm():
    chain = []
    tool = REG.item("tool_can_tin")
    while tool:
        chain.append(tool)
        tool = REG.item(tool.tool.upgrade.to) if tool.tool.upgrade else None
    assert [t.tool.power for t in chain] == sorted({t.tool.power for t in chain}) and chain[0].tool.power == 3 and chain[-1].tool.power == f.PLOTS
    assert all(t.tool.kind == "can" and t.skill == "farming" for t in chain)
    assert all(t.price == 0 for t in chain)  # none is sold (the first is a free starter tool)


async def test_a_better_can_brings_bigger_harvests_and_more_drops(db):
    plain, rich = await User.get(1), await User.get(2)
    await with_can(plain)
    await with_can(rich, "tool_can_moonwell")
    amounts, drops = {}, {}
    for user in (plain, rich):
        total, found = 0, 0
        for i in range(80):
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
            await user.add_item("seed_lemon", 1)
            await f.plant(user, 1, "seed_lemon", now=T0, registry=SURE)
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
            h = await f.harvest(user, 1, Random(i), T0, SURE)
            total += h.amount
            found += sum(h.extras.values())
        amounts[user.id], drops[user.id] = total, found
    assert amounts[2] > 1.1 * amounts[1] and drops[2] > 1.2 * drops[1]


def test_longer_crops_roll_the_farming_drop_table_more_often():
    rng = Random(1)
    rolls = lambda cycles: sum(f.drop_rolls(cycles, RULES, rng) for _ in range(2000)) / 2000  # noqa: E731
    assert rolls(1) == pytest.approx(1 / RULES.drop_cycles_per_roll, abs=0.05)
    assert rolls(40) == pytest.approx(40 / RULES.drop_cycles_per_roll, abs=0.1)
    assert rolls(10_000) == RULES.max_drop_rolls  # (there is a ceiling)
    assert f.drop_rolls(8, RULES, Random(1), luck=0.5) >= 3


async def test_a_harvest_pays_farming_materials_in_proportion_to_the_crop(db):
    user = await User.get(1)
    await with_can(user)
    found = {}
    for seed in ("seed_apple", "seed_watermelon"):
        total = Counter()
        await work_zone(user, f.seed_zone(seed, RULES))  # a crop's byproducts come from the zone it was planted in
        for i in range(60):
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
            await user.add_item(seed, 1)
            await f.plant(user, 1, seed, now=T0, registry=SURE)
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
            total += (await f.harvest(user, 1, Random(i), T0, SURE)).extras
        found[seed] = total
    assert sum(found["seed_watermelon"].values()) > 8 * sum(found["seed_apple"].values())
    table = {i.id for i in f.zone_materials(f.seed_zone("seed_watermelon", RULES), REG)}
    assert "material_compost" in found["seed_watermelon"] and {i.removesuffix("_s1").removesuffix("_s2").removesuffix("_s3") for i in found["seed_watermelon"] if i.startswith("material_")} <= table  # only its own zone's table


def test_the_farming_materials_are_used_by_upgrades_across_the_game():
    made = {"material_compost", "material_dewdrop", "material_beeswax", "material_living_vine"}
    assert all(REG.item(m).skill == "farming" and REG.item(m).drop for m in made)
    used = {m for t in REG.items.values() if t.tool and t.tool.upgrade for m in t.tool.upgrade.items}
    assert made <= used  # every one of them is something you spend
    outside = {t.tool.kind for t in REG.items.values() if t.tool and t.tool.kind != "can" and t.tool.upgrade and made & set(t.tool.upgrade.items)}
    assert {"axe", "pickaxe", "rod", "sword"} <= outside  # ...in other skills' tools too, not only the can
    rates = [REG.item(m).drop.rate for m in ("material_compost", "material_dewdrop", "material_beeswax", "material_living_vine")]
    assert rates == sorted(rates) and len(set(rates)) == 4  # each rarer than the last


async def test_a_plot_you_watered_and_then_harvested_does_not_use_up_the_can(db):
    user = await User.get(1)
    await with_can(user)
    await plant_many(user, 4)
    first = await f.water(user, T0, REG)
    assert first.watered == 3 and first.thirsty == 1
    await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
    await f.harvest(user, 1, Random(1), T0 + 5, REG)  # plot 1 is empty now: its watering no longer counts
    again = await f.water(user, T0 + 10, REG)
    assert again.watered == 1  # the can had one watering left, and plot 4 takes it


# ---- pages of plots ---------------------------------------------------------------------------------------------------------------------
async def many_plots(monkeypatch, plots=18):
    monkeypatch.setattr(f, "PLOTS", plots)
    user = await User.get(1)
    await user.update_skill("farming", lambda m: [setattr(getattr(m.farm, f"plot_{n}"), "unlocked", True) for n in range(1, plots + 1)])
    await with_can(user)
    return user


async def test_a_farm_of_one_page_has_no_page_controls(db):
    nav, _ = await hub("farm")
    labels = {b.label for b in buttons_of(nav)}
    assert "Plant all" in labels and not any((l or "").startswith("Page") for l in labels)


def buttons_of(nav):
    from tests.test_hub import buttons

    return buttons(nav)


async def test_more_than_nine_plots_make_pages_and_each_page_shows_its_own_plots(db, monkeypatch):
    await many_plots(monkeypatch)
    nav, inter = await hub("farm")
    text = all_text(nav)
    assert "Plots 1-9" in text
    labels = [b.label for b in buttons_of(nav)]
    assert "Page 1/2" in labels and "9 Plant" in labels and "10 Plant" not in labels
    assert next(b for b in buttons_of(nav) if b.label == "Prev").disabled and not next(b for b in buttons_of(nav) if b.label == "Next").disabled
    await click(nav, inter, "Next")
    labels = [b.label for b in buttons_of(nav)]
    assert "Page 2/2" in labels and "10 Plant" in labels and "18 Plant" in labels and "1 Plant" not in labels
    assert next(b for b in buttons_of(nav) if b.label == "Next").disabled and "Plots 10-18" in all_text(nav)
    await click(nav, inter, "Prev")
    assert "Page 1/2" in [b.label for b in buttons_of(nav)]


async def test_plant_page_plants_only_the_plots_on_the_page_you_are_looking_at(db, monkeypatch):
    user = await many_plots(monkeypatch)
    await user.add_item("seed_apple", 30)
    nav, inter = await hub("farm")
    await click(nav, inter, "Plant page")
    farm = (await user.skill("farming")).farm
    assert [bool(getattr(farm, f"plot_{n}").crop_id) for n in range(1, 19)] == [True] * 9 + [False] * 9
    assert await user.item_quantity("seed_apple") == 30 - 9 + 3  # (and the three starter seeds)
    await click(nav, inter, "Next")
    await click(nav, inter, "Plant page")
    farm = (await user.skill("farming")).farm
    assert all(getattr(farm, f"plot_{n}").crop_id for n in range(1, 19))


async def test_harvest_all_and_water_work_across_every_page(db, monkeypatch):
    user = await many_plots(monkeypatch)
    await user.add_item("seed_apple", 30)
    for number in (2, 14):
        await f.plant(user, number, "seed_apple", now=T0, registry=REG)
        await user.update_skill("farming", lambda m, n=number: setattr(getattr(m.farm, f"plot_{n}"), "can_harvest", True))
    nav, inter = await hub("farm")
    await click(nav, inter, "Harvest all")
    farm = (await user.skill("farming")).farm
    assert not farm.plot_2.can_harvest and not farm.plot_14.can_harvest and "You got" in all_text(nav)


async def test_every_plot_of_the_big_farm_can_be_stored(db, monkeypatch):
    user = await many_plots(monkeypatch, 27)
    await user.add_item("seed_apple", 1)
    await f.plant(user, 27, "seed_apple", now=T0, registry=REG)
    assert (await user.skill("farming")).farm.plot_27.crop_id == "seed_apple"
    nav, inter = await hub("farm")
    assert "Page 1/3" in [b.label for b in buttons_of(nav)]


async def test_a_page_number_beyond_the_last_page_falls_back_to_the_last_one(db, monkeypatch):
    await many_plots(monkeypatch)
    nav, inter = await hub("farm")
    nav.screen.page = 7  # (say a plot count shrank, or a stale click)
    await nav.screen.nav.refresh(inter)
    assert "Page 2/2" in [b.label for b in buttons_of(nav)] and nav.screen.page == 1


async def test_a_sprinkler_can_sometimes_grows_a_second_cycle_and_an_alchemist_can_sometimes_doubles_a_harvest(db):
    plain, sprinkler, alchemist = [await User.get(i) for i in (1, 2, 3)]
    await with_can(plain, "tool_can_moonwell")
    await with_can(sprinkler, "tool_can_moonwell")
    await with_can(alchemist, "tool_can_athanor")
    # the Sprinkler: with the roll forced to succeed, a watered plot grows two cycles; with `sprinkle` removed it grows one
    sprinkle = sprinkler_can_stat = (await f.can_stats(sprinkler)).stats["sprinkle"]
    assert sprinkle > 0 and (await f.can_stats(alchemist)).stats["transmute"] > 0 and "sprinkle" not in (await f.can_stats(alchemist)).stats
    for user in (sprinkler,):
        await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
        await user.add_item("seed_lemon", 1)
        await f.plant(user, 1, "seed_lemon", now=T0, registry=SURE)
    cycles = set()
    for hour in range(40):
        await sprinkler.update_skill("farming", lambda m: (setattr(m.farm.plot_1, "cycle", 0), setattr(m.farm.plot_1, "watered", -1), setattr(m.farm.plot_1, "can_harvest", False)))
        await f.water(sprinkler, T0 + hour * HOUR, registry_with(grow_chance=0.0, blessing_chance=0.0))  # (no rain: only the can grows it)
        cycles.add((await sprinkler.skill("farming")).farm.plot_1.cycle)
    assert cycles == {1, 2} and sprinkler_can_stat
    # the Alchemist: some of 120 harvests come up double (a plain can never does)
    sizes = {}
    for user in (plain, alchemist):
        amounts = []
        for i in range(120):
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
            await user.add_item("seed_lemon", 1)
            await f.plant(user, 1, "seed_lemon", now=T0, registry=SURE)
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
            amounts.append((await f.harvest(user, 1, Random(i), T0, SURE)).amount)
        sizes[user.id] = amounts
    assert max(sizes[3]) >= 2 * min(sizes[3]) and sum(sizes[3]) > 1.3 * sum(sizes[1])


# ---- Mastery capstones: Evergreen, Heirloom, Haggler -----------------------------------------------------------------------------------------------
async def ripe(user, seed="seed_lemon", plot=1):
    await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
    await user.add_item(seed, 1)
    await f.plant(user, plot, seed, now=T0, registry=SURE)
    await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))


async def test_evergreen_replants_a_harvest_for_free_and_a_plain_can_never_does(db):
    plain, green = await User.get(1), await User.get(2)
    await with_can(plain)
    await with_can(green)
    await green.update_skill("farming", lambda m: m.mastery.append("evergreen"))
    await ripe(plain)
    await ripe(green)
    assert (await f.harvest(plain, 1, Random(1), T0, SURE)).replanted is False
    assert (await plain.skill("farming")).farm.plot_1.crop_id is None
    sure = type("Low", (Random,), {"random": lambda self: 0.0})(1)  # every roll succeeds
    h = await f.harvest(green, 1, sure, T0, SURE)
    plot = (await green.skill("farming")).farm.plot_1
    assert h.replanted and plot.crop_id == "seed_lemon" and plot.cycle == 0 and not plot.can_harvest and await green.item_quantity("seed_lemon") == 0


async def test_heirloom_makes_some_harvests_bigger(db):
    plain, rich = await User.get(1), await User.get(2)
    for user in (plain, rich):
        await with_can(user)
    await rich.update_skill("farming", lambda m: m.mastery.append("heirloom"))
    sizes = {}
    for user in (plain, rich):
        amounts = []
        for i in range(150):
            await ripe(user)
            amounts.append((await f.harvest(user, 1, Random(i), T0, SURE)).amount)
        sizes[user.id] = sum(amounts)
    assert 1.1 < sizes[2] / sizes[1] < 1.3  # (30% of harvests, 60% bigger: about +18%)


async def test_haggler_makes_farm_goods_sell_for_more_and_only_farm_goods(db):
    from cococap.services import shop

    plain, merchant = await User.get(1), await User.get(2)
    for user in (plain, merchant):
        await with_can(user)
        await user.add_item("crop_apple", 100)
        await user.add_item("material_copper_ore", 100)
    await merchant.update_skill("farming", lambda m: m.mastery.append("haggler"))
    cut = REG.mastery.node("haggler").effects[0].amount
    base, more = await shop.sell(plain, "crop_apple", 100), await shop.sell(merchant, "crop_apple", 100)
    assert more == round(base * (1 + cut)) and base > 0
    assert await shop.sell(plain, "material_copper_ore", 100) == await shop.sell(merchant, "material_copper_ore", 100)


def test_the_three_farming_capstones_are_about_equally_strong():
    """Farming is about the harvest's worth, so each capstone is a fraction of it: Haggler adds its price bump, Heirloom its chance x its size, and Evergreen its chance
    x about a third (the time and seed a replanted plot saves). They are tuned to land within a few points of each other."""
    node = lambda nid: REG.mastery.node(nid).effects[0].amount  # noqa: E731
    gains = {"haggler": node("haggler"), "heirloom": node("heirloom") * 0.6, "evergreen": node("evergreen") * 0.3}
    assert all(0.1 <= g <= 0.25 for g in gains.values()), gains
    assert max(gains.values()) - min(gains.values()) <= 0.08, gains


# ---- Tend: byproducts of every growth cycle ---------------------------------------------------------------------------------------
async def growing(user, seed="seed_lemon", cycle=2, number=1):
    await user.add_item(seed, 1)
    await f.plant(user, number, seed, now=T0, registry=REG)
    await user.update_skill("farming", lambda m: setattr(f.plot_of(m, number), "cycle", cycle))


async def test_tending_collects_the_byproducts_of_the_cycles_since_last_time_once(db):
    user = await User.get(1)
    with pytest.raises(f.FarmingError, match="Nothing has grown"):
        await f.tend(user, Random(1), T0, REG)
    await growing(user, cycle=2)
    report = await f.tend(user, Random(1), T0, REG)
    assert (report.plots, report.cycles) == (1, 2) and (await user.skill("farming")).farm.plot_1.tended == 2
    assert all(REG.item(i).skill == "farming" for i in report.found) and sum(report.found.values()) > 0
    for item, quantity in report.found.items():
        assert await user.item_quantity(item) == quantity
    with pytest.raises(f.FarmingError):  # nothing new has grown
        await f.tend(user, Random(1), T0, REG)
    await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "cycle", 3))
    assert (await f.tend(user, Random(2), T0, REG)).cycles == 1  # only the new cycle


async def test_a_plot_only_keeps_a_few_cycles_of_byproducts_waiting(db):
    user = await User.get(1)
    await growing(user, seed="seed_coconut", cycle=RULES.byproduct_max_cycles + 20)
    assert f.tend_waiting(await user.skill("farming"), RULES) == RULES.byproduct_max_cycles
    assert (await f.tend(user, Random(1), T0, REG)).cycles == RULES.byproduct_max_cycles
    assert f.tend_waiting(await user.skill("farming"), RULES) == 0  # the rest is lost, not saved up


async def test_tending_gives_no_xp_and_a_new_crop_starts_counting_again(db):
    user = await User.get(1)
    await growing(user, cycle=2)
    xp = (await user.skill("farming")).xp
    await f.tend(user, Random(1), T0, REG)
    assert (await user.skill("farming")).xp == xp
    await user.update_skill("farming", lambda m: (setattr(m.farm.plot_1, "crop_id", None), setattr(m.farm.plot_1, "cycle", 0), setattr(m.farm.plot_1, "tended", 0)))
    await growing(user, cycle=1)
    assert (await f.tend(user, Random(1), T0, REG)).cycles == 1


async def test_with_no_byproduct_rolls_tending_finds_nothing(db):
    user = await User.get(1)
    await growing(user, cycle=2)
    none = registry_with(byproduct_rolls=[0] * len(RULES.byproduct_rolls))
    assert not (await f.tend(user, Random(1), T0, none)).found


def test_byproducts_are_a_fair_share_of_what_each_crop_earns_an_hour():
    """Guard: tending is worth about 10-50% of the crop's own watered income an hour, so farming stays in line with the other skills (see scripts.balance)."""
    assert len(RULES.byproduct_rolls) == len(RULES.field_seeds)
    for seed_id, rolls, materials in zip(RULES.field_seeds, RULES.byproduct_rolls, RULES.zone_materials, strict=True):
        one_roll = sum(REG.item(i).sell_price * (d.min + d.max) / 2 / d.rate for i in materials if (d := REG.item(i).drop))  # this zone's table
        seed = REG.item(seed_id)
        crop = REG.item(seed.seed.grows_into)
        per_hour = crop.sell_price * (crop.crop.min_harvest + crop.crop.max_harvest) / 2 / seed.seed.cycles  # watered: one cycle an hour
        share = rolls * one_roll / per_hour
        assert 0.1 <= share <= 0.5, (seed_id, round(share, 2))
    assert RULES.byproduct_rolls[-1] > RULES.byproduct_rolls[0]  # bigger crops, bigger byproducts


async def test_the_farm_page_has_a_tend_button_that_wakes_up_when_something_grew(db):
    nav, inter = await hub("farm")
    assert find_button_named(nav, "Tend").disabled
    user = await User.get(1)
    await with_can(user)
    await growing(user, cycle=2)
    nav, inter = await hub("farm")
    assert not find_button_named(nav, "Tend").disabled
    await click(nav, inter, "Tend")
    assert "You tended" in all_text(nav)  # the list page (or the plain note when nothing dropped)
    if nav.screen.id == "result":
        await click(nav, inter, "Back to the farm")
    assert find_button_named(nav, "Tend").disabled


def find_button_named(nav, label):
    from tests.test_hub import find_button

    return find_button(nav, label)
