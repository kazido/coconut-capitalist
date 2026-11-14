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
from tests.test_hub import all_text, choose, click, hub, select_named

REG = get_registry()
RULES = REG.farming
HOUR = 3600
T0 = 1_800_000_000 // HOUR * HOUR  # a clean hour boundary


async def with_can(user, template="tin_can"):
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


FRIDAY, THURSDAY, SATURDAY, SUNDAY = at(2026, 11, 13), at(2026, 11, 12), at(2026, 11, 14), at(2026, 11, 15)


async def farmer(**items):
    user = await User.get(1)
    for item, quantity in items.items():
        await user.add_item(item, quantity)
    return user


# ---- the rain ----------------------------------------------------------------------------------------------
def seeded_farm(seed_id="coconut_seed", since=0, plot=1):
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
    slow = seeded_farm("hot_pepper_seed", since=T0 // HOUR)
    f.apply_rain(slow, 1, T0 + 19 * HOUR, SURE)
    assert f.plot_of(slow, 1).cycle == 19 and not f.plot_of(slow, 1).can_harvest
    f.apply_rain(slow, 1, T0 + 20 * HOUR, SURE)
    assert f.plot_of(slow, 1).can_harvest


def test_looking_twice_in_the_same_hour_changes_nothing():
    farm = seeded_farm("hot_pepper_seed", since=T0 // HOUR)
    f.apply_rain(farm, 1, T0 + 7 * HOUR, REG)
    snapshot = farm.model_dump()
    f.apply_rain(farm, 1, T0 + 7 * HOUR + 1800, REG)
    assert farm.model_dump() == snapshot


def test_catching_up_at_once_equals_living_through_every_hour():
    """The core promise: offline time counts exactly like being there, and reopening can't re-roll anything."""
    for uid in range(1, 25):
        once = seeded_farm("coconut_seed", since=T0 // HOUR)
        stepped = seeded_farm("coconut_seed", since=T0 // HOUR)
        f.apply_rain(once, uid, T0 + 150 * HOUR, REG)
        for h in range(1, 151):
            f.apply_rain(stepped, uid, T0 + h * HOUR, REG)
        assert once.model_dump() == stepped.model_dump(), uid


def test_rain_is_deterministic_per_player_and_differs_between_players():
    def cycles(uid):
        farm = seeded_farm("coconut_seed", since=T0 // HOUR)
        f.apply_rain(farm, uid, T0 + 60 * HOUR, REG)
        return f.plot_of(farm, 1).cycle

    assert cycles(1) == cycles(1)
    assert len({cycles(uid) for uid in range(1, 30)}) > 3  # not everyone gets the same weather


def test_growth_matches_the_chance_in_the_long_run():
    total = 0
    for uid in range(1, 200):
        farm = seeded_farm("ambrosia_seed", since=T0 // HOUR)  # 777 cycles: never finishes in this window
        f.apply_rain(farm, uid, T0 + 100 * HOUR, REG)
        total += f.plot_of(farm, 1).cycle
    assert total / (199 * 100) == pytest.approx(RULES.grow_chance, abs=0.03)


def test_a_blessing_can_only_fall_in_a_rain_where_something_grew():
    reg = registry_with(grow_chance=1.0, blessing_chance=1.0)
    farm = seeded_farm("ambrosia_seed", since=T0 // HOUR)
    report = f.apply_rain(farm, 1, T0 + 10 * HOUR, reg)
    assert report.blessings == 10 and farm.rain_god_blessings == 10
    empty = Farming()
    assert f.apply_rain(empty, 1, T0 + 10 * HOUR, reg).blessings == 0  # nothing planted: no blessings


def test_two_plots_growing_in_the_same_rain_bring_one_blessing_chance_not_two():
    reg = registry_with(grow_chance=1.0, blessing_chance=1.0)
    farm = seeded_farm("ambrosia_seed", since=T0 // HOUR, plot=1)
    other = f.plot_of(farm, 2)
    other.crop_id, other.since = "ambrosia_seed", T0 // HOUR
    assert f.apply_rain(farm, 1, T0 + 4 * HOUR, reg).blessings == 4


def test_a_ripe_plot_stops_growing_and_an_empty_one_is_ignored():
    farm = seeded_farm("apple_seed", since=T0 // HOUR)
    f.apply_rain(farm, 1, T0 + 50 * HOUR, SURE)
    assert f.plot_of(farm, 1).cycle == REG.item("apple_seed").seed.cycles
    assert f.plot_of(farm, 2).crop_id is None and f.plot_of(farm, 2).cycle == 0


# ---- plots and planting -----------------------------------------------------------------------------------------
async def test_plot_one_is_free_and_the_rest_need_land_deeds(db):
    user = await farmer(land_deed=1)
    farming = await user.skill("farming")
    assert f.is_unlocked(farming, 1, RULES) and not f.is_unlocked(farming, 2, RULES)
    await f.buy_plot(user, 2)
    assert f.is_unlocked(await user.skill("farming"), 2, RULES) and await user.item_quantity("land_deed") == 0
    with pytest.raises(f.FarmingError, match="already own"):
        await f.buy_plot(user, 2)
    with pytest.raises(f.FarmingError, match="Land Deed"):
        await f.buy_plot(user, 3)
    for bad in (0, 1, 10):
        with pytest.raises(f.FarmingError, match="can't be bought"):
            await f.buy_plot(user, bad)


async def test_planting_uses_a_seed_and_only_goes_on_an_empty_plot_you_own(db):
    user = await farmer(apple_seed=2)
    await f.plant(user, 1, "apple_seed", now=T0)
    assert await user.item_quantity("apple_seed") == 1
    plot = f.plot_of(await user.skill("farming"), 1)
    assert plot.crop_id == "apple_seed" and plot.cycle == 0 and plot.since == T0 // HOUR
    with pytest.raises(f.FarmingError, match="already growing"):
        await f.plant(user, 1, "apple_seed", now=T0)
    assert await user.item_quantity("apple_seed") == 1  # the failed attempt cost nothing
    with pytest.raises(f.FarmingError, match="don't own"):
        await f.plant(user, 2, "apple_seed", now=T0)
    assert await user.item_quantity("apple_seed") == 1


async def test_you_cannot_plant_what_is_not_a_seed_or_what_you_do_not_have(db):
    user = await farmer(copper_ore=5)
    with pytest.raises(f.FarmingError, match="isn't a seed"):
        await f.plant(user, 1, "copper_ore", now=T0)
    with pytest.raises(f.FarmingError, match="don't have any"):
        await f.plant(user, 1, "apple_seed", now=T0)
    assert await user.item_quantity("copper_ore") == 5


async def test_a_seed_planted_now_only_feels_the_rain_that_falls_afterwards(db):
    user = await farmer(apple_seed=1)
    await f.plant(user, 1, "apple_seed", now=T0 + 30)  # mid-hour
    farming, report = await f.sync(user, T0 + 40, SURE)
    assert report.rains == 0 and not f.plot_of(farming, 1).can_harvest  # this hour's rain already fell
    farming, report = await f.sync(user, T0 + HOUR + 1, SURE)
    assert f.plot_of(farming, 1).can_harvest


# ---- xp follows the waiting ------
async def test_a_longer_crop_pays_more_xp_in_proportion_to_its_growth_time(db):
    xp = {}
    for seed in ("apple_seed", "coconut_seed"):
        user = await farmer()
        await ripe_farm(user, seed)
        xp[seed] = (await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=SURE)).xp
        await user.update_skill("farming", lambda m: setattr(m, "xp", 0))
        await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "crop_id", None))
    assert xp["apple_seed"] == REG.item("apple_seed").seed.cycles * RULES.xp_per_cycle
    assert xp["coconut_seed"] == REG.item("coconut_seed").seed.cycles * RULES.xp_per_cycle > 50 * xp["apple_seed"]


# ---- harvesting ------------------------------------------------------------------------------------------------
async def ripe_farm(user, seed="apple_seed"):
    await user.add_item(seed, 1)
    await f.plant(user, 1, seed, now=T0, registry=SURE)
    await f.sync(user, T0 + 1000 * HOUR, SURE)


async def test_harvesting_gives_crops_xp_and_empties_the_plot_exactly_once(db):
    user = await farmer()
    await ripe_farm(user)
    crop = REG.item("apple")
    result = await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=SURE)
    assert result.crop_id == "apple" and crop.crop.min_harvest <= result.amount <= crop.crop.max_harvest
    assert await user.item_quantity("apple") == result.amount
    skill = await user.skill("farming")
    assert skill.xp == REG.item("apple_seed").seed.cycles * RULES.xp_per_cycle == result.xp and skill.stats.crops_grown == result.amount
    assert f.plot_of(skill, 1).crop_id is None
    with pytest.raises(f.FarmingError, match="Nothing is ready"):
        await f.harvest(user, 1, Random(1), now=T0 + 1000 * HOUR, registry=SURE)
    assert await user.item_quantity("apple") == result.amount  # no second payout


async def test_two_harvest_clicks_at_once_pay_once(db):
    user = await farmer()
    await ripe_farm(user)
    results = await asyncio.gather(
        *(f.harvest(user, 1, Random(i), now=T0 + 1000 * HOUR, registry=SURE) for i in range(2)), return_exceptions=True
    )
    paid = [r for r in results if isinstance(r, f.Harvest)]
    assert len(paid) == 1 and await user.item_quantity("apple") == paid[0].amount


async def test_an_unripe_plot_cannot_be_harvested(db):
    user = await farmer(coconut_seed=1)
    await f.plant(user, 1, "coconut_seed", now=T0)
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
    user = await farmer(apple_seed=3, land_deed=2)
    await f.buy_plot(user, 2)
    await f.buy_plot(user, 3)
    for n in (1, 2, 3):
        await f.plant(user, n, "apple_seed", now=T0, registry=SURE)
    results = await f.harvest_all(user, Random(1), now=T0 + 10 * HOUR, registry=SURE)
    assert [r.plot for r in results] == [1, 2, 3]
    assert await user.item_quantity("apple") == sum(r.amount for r in results)
    assert await f.harvest_all(user, Random(1), now=T0 + 10 * HOUR, registry=SURE) == []


# ---- the Farmer's Market -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("when, is_open", [(THURSDAY, False), (FRIDAY, True), (SATURDAY, True), (SUNDAY, False)])
def test_the_market_is_open_friday_and_saturday(when, is_open):
    assert f.market_window(when, REG)[0] is is_open


def test_the_market_says_when_it_next_changes():
    closes = f.market_window(FRIDAY, REG)[1]
    assert closes == at(2026, 11, 15, 0)  # Sunday 00:00 UTC (Friday and Saturday are one opening)
    opens = f.market_window(SUNDAY, REG)[1]
    assert opens == at(2026, 11, 20, 0)  # next Friday
    assert f.market_window(THURSDAY, REG)[1] == at(2026, 11, 13, 0)


async def test_the_market_needs_level_five_and_an_open_day(db):
    user = await farmer(apple=10)
    with pytest.raises(f.FarmingError, match="level 5"):
        await f.sell_crops(user, FRIDAY)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    with pytest.raises(f.FarmingError, match="closed"):
        await f.sell_crops(user, THURSDAY)
    assert await user.item_quantity("apple") == 10  # nothing was taken


async def test_selling_at_the_market_pays_the_bonus_and_only_takes_crops(db):
    user = await farmer(apple=10, lemon=2, copper_ore=7, apple_seed=3)
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    before = (await User.get(1)).purse
    earned, sold = await f.sell_crops(user, FRIDAY)
    expected = int(REG.item("apple").sell_price * 10 * 1.5) + int(REG.item("lemon").sell_price * 2 * 1.5)
    assert earned == expected and sold == Counter(apple=10, lemon=2)
    await user.refresh()
    assert user.purse == before + earned
    assert await user.item_quantity("copper_ore") == 7 and await user.item_quantity("apple_seed") == 3  # untouched
    with pytest.raises(f.FarmingError, match="no crops"):
        await f.sell_crops(user, FRIDAY)


async def test_market_prices_beat_the_shop(db):
    assert f.market_price("apple", 1, REG) > REG.item("apple").sell_price


async def test_blessings_turn_into_land_deeds_at_the_market(db):
    user = await farmer()
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.update_skill("farming", lambda m: setattr(m, "rain_god_blessings", 5))
    with pytest.raises(f.FarmingError, match="closed"):
        await f.deposit_blessings(user, Random(1), THURSDAY)
    lucky = registry_with(market={"deed_chance": 1.0})
    used, deeds = await f.deposit_blessings(user, Random(1), FRIDAY, lucky)
    assert (used, deeds) == (5, 5) and await user.item_quantity("land_deed") == 5
    assert (await user.skill("farming")).rain_god_blessings == 0
    with pytest.raises(f.FarmingError, match="no rain god"):
        await f.deposit_blessings(user, Random(1), FRIDAY, lucky)


async def test_blessings_only_sometimes_become_deeds(db):
    user = await farmer()
    await user.add_xp("farming", User.level_to_xp(5) + 1)
    await user.update_skill("farming", lambda m: setattr(m, "rain_god_blessings", 400))
    used, deeds = await f.deposit_blessings(user, Random(3), FRIDAY)
    assert used == 400 and 15 < deeds < 70  # about 1 in 10


def test_land_deeds_and_the_farming_rules_are_real_data():
    assert REG.item("land_deed").category == "key_item" and RULES.market.days == [4, 5] and RULES.market.min_level == 5
    assert RULES.free_plots == 1 and RULES.anomaly_odds == 25 and RULES.blessing_chance == 0.1


# ---- getting started: a gift, cheap first seeds, and watering --------------------------------------------------------------------
async def test_every_farmer_gets_free_starter_seeds_once(db):
    user = await User.get(1)
    gift = await f.starter_gift(user, REG)
    assert gift == RULES.starter_seeds and await user.item_quantity("apple_seed") == RULES.starter_seeds["apple_seed"]
    assert await f.starter_gift(user, REG) == {}  # once only
    assert await user.item_quantity("apple_seed") == RULES.starter_seeds["apple_seed"]
    assert (await user.skill("farming")).starter_given


def test_the_first_seeds_are_cheap_enough_for_a_brand_new_player():
    start = 1_000  # what a new player has
    assert REG.item("apple_seed").price * 2 <= start  # a couple of apple seeds is well within reach
    assert REG.item("apple_seed").price < REG.item("lemon_seed").price < REG.item("hot_pepper_seed").price


async def test_watering_grows_plots_you_have_not_watered_this_hour_and_only_once_an_hour(db):
    user = await User.get(1)
    await with_can(user)
    await user.add_item("apple_seed", 1)
    await f.plant(user, 1, "apple_seed", now=T0, registry=REG)
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
        await user.add_item("coconut_seed", 1)
        await f.plant(user, 1, "coconut_seed", now=T0, registry=REG)
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
        await user.add_item("apple_seed", 1)
        await f.plant(user, 1, "apple_seed", now=T0, registry=REG)
        report = await f.water(user, T0, REG)
        plot = (await user.skill("farming")).farm.plot_1
        assert plot.can_harvest == bool(report.grew) and (report.matured == (1,)) == plot.can_harvest
    assert REG.item("apple_seed").seed.cycles == 1


async def test_watering_skips_empty_and_ripe_plots(db):
    user = await User.get(1)
    await with_can(user)
    assert (await f.water(user, T0, REG)).watered == 0
    await user.add_item("apple_seed", 1)
    await f.plant(user, 1, "apple_seed", now=T0, registry=REG)
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
    await user.add_item("lemon_seed", 2)
    nav, inter = await hub("farm")
    menu = select_named(nav, "Seed to plant")
    lemon = next(o for o in menu.options if o.value == "lemon_seed")
    assert f"{REG.item('lemon_seed').seed.cycles} cycles" in lemon.description and "about" in lemon.description and "to" in lemon.description
    await choose(nav, inter, menu, "lemon_seed")
    await click(nav, inter, "1 Plant")
    assert "Ready in about" in all_text(nav)
    assert "ready in about" in all_text(nav)  # and the plot's own line keeps counting down


# ---- the watering can ---------------------------------------------------------------------------------------------------------------------
async def plant_many(user, count):
    """Own `count` plots, all planted with apples (a one-cycle crop that is never ripe before it is watered here)."""
    await user.update_skill("farming", lambda m: [setattr(getattr(m.farm, f"plot_{n}"), "unlocked", True) for n in range(1, 10)])
    await user.add_item("coconut_seed", count)
    for number in range(1, count + 1):
        await f.plant(user, number, "coconut_seed", now=T0, registry=REG)


async def test_watering_needs_a_can(db):
    user = await User.get(1)
    await user.add_item("apple_seed", 1)
    await f.plant(user, 1, "apple_seed", now=T0, registry=REG)
    with pytest.raises(f.FarmingError, match="watering can"):
        await f.water(user, T0, REG)


def test_a_watering_always_grows_a_cycle():
    assert RULES.water_chance == 1.0
    assert f.hourly_chance(RULES, watered=True) == 1.0


async def test_a_can_only_waters_as_many_plots_an_hour_as_its_power(db):
    user = await User.get(1)
    can = await with_can(user)
    await plant_many(user, 6)
    power = REG.item("tin_can").tool.power
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
    await with_can(user, "iron_can")
    await plant_many(user, 6)
    report = await f.water(user, T0, REG)
    assert report.watered == REG.item("iron_can").tool.power == 5 and report.thirsty == 1


async def test_plots_watered_before_a_new_one_is_planted_still_use_up_the_can(db):
    user = await User.get(1)
    await with_can(user)
    await plant_many(user, 3)
    assert (await f.water(user, T0, REG)).watered == 3
    await user.add_item("coconut_seed", 1)
    await f.plant(user, 4, "coconut_seed", now=T0, registry=REG)
    late = await f.water(user, T0 + 30, REG)
    assert late.watered == 0 and late.thirsty == 1  # the can was already used on three plots this hour


def test_the_can_chain_is_a_chain_of_waters_that_ends_at_the_whole_farm():
    chain = []
    tool = REG.item("tin_can")
    while tool:
        chain.append(tool)
        tool = REG.item(tool.tool.upgrade.to) if tool.tool.upgrade else None
    assert [t.tool.power for t in chain] == sorted({t.tool.power for t in chain}) and chain[0].tool.power == 3 and chain[-1].tool.power == f.PLOTS
    assert all(t.tool.kind == "can" and t.skill == "farming" for t in chain)
    assert REG.item("tin_can").price > 0 and all(t.price == 0 for t in chain[1:])  # only the first is sold


async def test_a_better_can_brings_bigger_harvests_and_more_drops(db):
    plain, rich = await User.get(1), await User.get(2)
    await with_can(plain)
    await with_can(rich, "moonwell_can")
    amounts, drops = {}, {}
    for user in (plain, rich):
        total, found = 0, 0
        for i in range(80):
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
            await user.add_item("lemon_seed", 1)
            await f.plant(user, 1, "lemon_seed", now=T0, registry=SURE)
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
    for seed in ("apple_seed", "watermelon_seed"):
        total = Counter()
        for i in range(60):
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "unlocked", True))
            await user.add_item(seed, 1)
            await f.plant(user, 1, seed, now=T0, registry=SURE)
            await user.update_skill("farming", lambda m: setattr(m.farm.plot_1, "can_harvest", True))
            total += (await f.harvest(user, 1, Random(i), T0, SURE)).extras
        found[seed] = total
    assert sum(found["watermelon_seed"].values()) > 8 * sum(found["apple_seed"].values())
    assert {"compost", "plant_fiber"} <= set(found["watermelon_seed"])  # the common ones come first


def test_the_farming_materials_are_used_by_upgrades_across_the_game():
    made = {"compost", "dewdrop", "beeswax", "living_vine", "golden_pollen"}
    assert all(REG.item(m).skill == "farming" and REG.item(m).drop for m in made)
    used = {m for t in REG.items.values() if t.tool and t.tool.upgrade for m in t.tool.upgrade.items}
    assert made <= used  # every one of them is something you spend
    outside = {t.tool.kind for t in REG.items.values() if t.tool and t.tool.kind != "can" and t.tool.upgrade and made & set(t.tool.upgrade.items)}
    assert {"axe", "pickaxe", "rod", "sword"} <= outside  # ...in other skills' tools too, not only the can
    rates = [REG.item(m).drop.rate for m in ("compost", "dewdrop", "beeswax", "living_vine", "golden_pollen")]
    assert rates == sorted(rates) and len(set(rates)) == 5  # each rarer than the last


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
