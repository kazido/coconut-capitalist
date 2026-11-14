import datetime
from collections import Counter
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.screens import fish as fish_screen
from cococap.services import fishing as f
from cococap.services import mining
from cococap.services import shop
from cococap.services.equipment import EffectiveStats, equip
from cococap.services.party import Party
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, buttons, click, find_button, hub

REG = get_registry()
RULES = REG.fishing
T0 = 1_000_000.0


def rod(power=3):
    return EffectiveStats(power=power, requirement=0, stats={"power": float(power)})


async def player(user_id=1, rod_name="starter_rod"):
    user = await User.get(user_id)
    if rod_name:
        inst = await user.give_instance(rod_name)
        await equip(user, "fishing", inst.id)
    return user


def cast_of(fish_id="cod", pattern=None, slips=0, wait=10.0, hooked=True):
    """A cast whose fish has bitten and (by default) been pulled up, so tests can go straight to reeling."""
    pattern = pattern or [f.LEFT, f.RIGHT, f.LEFT]
    return f.Cast(REG.item(fish_id), T0 + wait, T0 + wait + RULES.bite.window, list(pattern), slips, hooked=hooked)


# ---- the fish ---------------------------------------------------------------------------------------------------
def test_the_pool_is_rarest_first_ends_with_a_sure_catch_and_leaves_the_pet_item_out():
    pool = f.fish_pool(REG)
    rates = [i.drop.rate for i in pool]
    assert rates == sorted(rates, reverse=True) and rates[-1] == 1
    assert "spirit_of_the_sea" not in {i.id for i in pool}
    assert all(i.sell_price > 0 and i.skill == "fishing" for i in pool)


def test_every_cast_catches_something_and_rarer_fish_are_rarer():
    rng, seen = Random(1), Counter()
    for _ in range(20_000):
        seen[f.roll_fish(rng, REG).id] += 1
    assert sum(seen.values()) == 20_000
    by_rarity = Counter()
    for fish_id, n in seen.items():
        by_rarity[REG.item(fish_id).rarity] += n
    assert by_rarity[1] > by_rarity[2] > by_rarity[3] > by_rarity[4] > by_rarity[5]
    assert seen["cod"] > 0 and seen["bass"] > 0


def test_a_cast_pays_about_what_it_should_at_starter_gear():
    """A guard against the payout drifting: the average catch's value, and so bits per minute, at a Starter Rod."""
    rng = Random(2)
    n = 40_000
    worth = sum(f.roll_fish(rng, REG).sell_price for _ in range(n)) / n
    assert 4_000 <= worth <= 6_500, worth
    power = REG.item("starter_rod").tool.power
    seconds = sum(f.wait_seconds(power, RULES, rng) for _ in range(2000)) / 2000 + 1.5 * (RULES.reel.base_length + 2)
    assert 10 <= seconds <= 25, seconds  # a catch every ~15-20 seconds: roughly what foraging earns per second


# ---- the rod ----------------------------------------------------------------------------------------------------
def test_a_stronger_rod_bites_sooner_but_never_instantly():
    mean = lambda p: sum(f.wait_seconds(p, RULES, Random(i)) for i in range(400)) / 400
    assert mean(1) > mean(3) > mean(8) > mean(18)
    assert all(f.wait_seconds(10_000, RULES, Random(i)) >= RULES.bite.wait_min * RULES.bite.min_wait_factor for i in range(50))
    assert all(RULES.bite.wait_min <= f.wait_seconds(1, RULES, Random(i)) <= RULES.bite.wait_max for i in range(50))


def test_rod_power_forgives_wrong_arrows():
    assert f.slips_allowed(3, RULES) == 0
    assert f.slips_allowed(RULES.reel.power_per_slip, RULES) == 1
    assert f.slips_allowed(18, RULES) == 2


def test_rarer_fish_take_longer_to_reel_in():
    lengths = [len(f.reel_pattern(r, RULES, Random(1))) for r in range(1, 8)]
    assert lengths == sorted(lengths) and lengths[0] == RULES.reel.base_length + 1 and len(set(lengths)) == 7
    assert set(f.reel_pattern(7, RULES, Random(1))) <= {f.LEFT, f.RIGHT}


# ---- a cast -----------------------------------------------------------------------------------------------------
def test_a_line_waits_then_bites_then_the_fish_gets_away_if_you_dawdle():
    cast = cast_of(hooked=False)
    assert cast.status(T0) == "waiting"
    assert cast.status(T0 + 10) == "bite"
    assert cast.status(T0 + 10 + RULES.bite.window) == "bite"
    assert cast.status(T0 + 10 + RULES.bite.window + 1) == "escaped"
    with pytest.raises(f.FishingError):
        cast.hook(T0 + 99)


def test_a_bite_only_lasts_six_seconds():
    assert RULES.bite.window == 6


def test_you_must_pull_up_the_line_before_you_can_reel():
    cast = cast_of(hooked=False)
    with pytest.raises(f.FishingError, match="biting"):
        cast.hook(T0 + 1)  # nothing yet
    with pytest.raises(f.FishingError, match="Pull up"):
        cast.press(f.LEFT, T0 + 11)  # it's biting, but the game doesn't start by itself
    assert cast.progress == 0 and not cast.hooked
    cast.hook(T0 + 11)
    assert cast.hooked and cast.status(T0 + 11) == "reeling"
    assert cast.press(f.LEFT, T0 + 11) == "ok"


def test_pulling_up_late_is_too_late():
    cast = cast_of(hooked=False)
    with pytest.raises(f.FishingError, match="got away"):
        cast.hook(T0 + 10 + RULES.bite.window + 0.1)
    assert cast.escaped


def test_pressing_the_right_arrows_in_order_lands_the_fish():
    cast = cast_of()
    assert [cast.press(a, T0 + 11) for a in (f.LEFT, f.RIGHT, f.LEFT)] == ["ok", "ok", "landed"]
    assert cast.status(T0 + 11) == "landed"
    with pytest.raises(f.FishingError, match="already landed"):
        cast.press(f.LEFT, T0 + 11)


def test_a_wrong_arrow_loses_the_fish_unless_the_rod_forgives_it():
    strict = cast_of()
    assert strict.press(f.RIGHT, T0 + 11) == "escaped" and strict.escaped
    kind = cast_of(slips=1)
    assert kind.press(f.RIGHT, T0 + 11) == "slip" and kind.progress == 0 and not kind.escaped
    assert kind.press(f.RIGHT, T0 + 11) == "escaped"  # the second slip is one too many


def test_once_you_are_reeling_the_clock_no_longer_loses_the_fish():
    cast = cast_of(hooked=False)
    cast.hook(T0 + 11)
    cast.press(f.LEFT, T0 + 11)
    assert cast.status(T0 + 10_000) == "reeling"  # only pulling up the line has a deadline


def test_casting_fixes_everything_up_front():
    first = f.cast_line(rod(3), Random(7), T0, REG)
    again = f.cast_line(rod(3), Random(7), T0, REG)
    assert (first.fish.id, first.bite_at, first.pattern) == (again.fish.id, again.bite_at, again.pattern)
    assert first.bite_at > T0 and first.expires_at == first.bite_at + RULES.bite.window
    assert len(first.pattern) == RULES.reel.base_length + first.fish.rarity


# ---- paying out -------------------------------------------------------------------------------------------------
async def test_you_need_a_rod(db):
    user = await player(rod_name=None)
    with pytest.raises(f.FishingError, match="rod"):
        await f.rod_stats(user)


async def test_landing_a_fish_pays_once(db):
    user = await player()
    cast = cast_of("salmon", slips=0)
    for arrow in cast.pattern:
        cast.press(arrow, T0 + 11)
    caught = await f.land(user, cast, REG)
    assert caught.xp == 3 * RULES.xp_per_rarity and caught.fish.id == "salmon"
    assert await user.item_quantity("salmon") == 1
    skill = await user.skill("fishing")
    assert skill.xp == caught.xp and skill.stats.fish_caught == 1
    with pytest.raises(f.FishingError, match="already"):
        await f.land(user, cast, REG)
    assert await user.item_quantity("salmon") == 1


async def test_an_unfinished_or_escaped_fish_pays_nothing(db):
    user = await player()
    with pytest.raises(f.FishingError):
        await f.land(user, cast_of(), REG)
    gone = cast_of()
    gone.press(f.RIGHT, T0 + 11)
    with pytest.raises(f.FishingError):
        await f.land(user, gone, REG)
    assert await user.item_quantity("cod") == 0 and (await user.skill("fishing")).xp == 0


async def test_fishing_xp_is_boosted_in_a_party(db):
    user = await player(1)

    async def catch():
        cast = cast_of()
        for arrow in cast.pattern:
            cast.press(arrow, T0 + 11)
        return (await f.land(user, cast, REG)).xp

    base = await catch()
    party = await Party.create(1)
    await party.add_member(2)
    assert await catch() == round(base * (1 + REG.economy.party_xp_bonus))


async def test_selling_the_catch_empties_the_bag_and_pays(db):
    user = await player()
    await user.add_item("cod", 3)
    await user.add_item("salmon", 1)
    await user.add_item("apple", 5)  # not a fish: stays
    haul = await f.stock(user, REG)
    assert haul.count == 4 and haul.worth == 3 * REG.item("cod").sell_price + REG.item("salmon").sell_price
    before = user.purse
    earned = await f.sell_all(user, REG)
    await user.refresh()
    assert earned == haul.worth and user.purse == before + earned
    assert await user.item_quantity("cod") == 0 and await user.item_quantity("apple") == 5
    assert await f.sell_all(user, REG) == 0


# ---- starting out: tools cost money, and your first one equips itself -------------------------------------------
async def test_buying_your_first_tool_equips_it_and_you_cannot_buy_a_second(db):
    user = await User.get(1)
    await set_columns(user, purse=50_000_000)
    for item_id, skill in (("starter_rod", "fishing"), ("starter_axe", "foraging"), ("rookiepickaxe", "mining")):
        bought = await shop.buy(user, item_id, 1, REG)
        assert (await user.equipped_instance(skill)).id == bought.instances[0].id
    with pytest.raises(shop.ShopError, match="already have"):
        await shop.buy(user, "starter_rod", 1, REG)  # one tool per kind: upgrade it instead


async def test_a_brand_new_player_can_afford_a_starter_tool_with_their_first_work_wage(db):
    user = await User.get(1)
    wage = REG.rank(user.rank).wage
    for item_id in ("starter_rod", "starter_axe", "rookiepickaxe"):
        assert REG.item(item_id).buyable
        assert user.purse + wage >= REG.item(item_id).price, item_id


@pytest.mark.bare_hands
async def test_you_cannot_mine_without_a_pickaxe(db):
    user = await User.get(1)
    with pytest.raises(mining.MiningError, match="pickaxe"):
        await mining.start_run(user, Random(1))
    inst = await user.give_instance("rookiepickaxe")
    await equip(user, "mining", inst.id)
    assert (await mining.start_run(user, Random(1))).depth == 0


@pytest.mark.bare_hands
async def test_the_mining_page_asks_for_a_pickaxe_and_locks_the_door(db):
    nav, _ = await hub("mining")
    assert "need a pickaxe" in all_text(nav)
    assert find_button(nav, "Enter the mines").disabled


# ---- the screen -------------------------------------------------------------------------------------------------
class NoLuck(Random):
    """Ordinary dice, except no 1-in-N chance ever hits: no hallucinations, chests or surprise drops to flake a test."""

    def randint(self, a, b):
        return b


@pytest.fixture(autouse=True)
def steady_dice(monkeypatch):
    monkeypatch.setattr(fish_screen, "new_rng", lambda: NoLuck(1))  # (tests that want luck set their own)


@pytest.fixture
def clock(monkeypatch):
    now = [T0]
    monkeypatch.setattr(fish_screen, "now", lambda: now[0])
    return now


async def open_fishing(user_id=1, power_item="starter_rod"):
    user = await player(user_id, power_item)
    nav, inter = await hub("fish", user_id=user_id)
    return user, nav, inter


async def test_without_a_rod_the_fishing_page_says_how_to_get_one(db):
    nav, _ = await hub("fish")
    assert "need a rod" in all_text(nav) and find_button(nav, "Cast").disabled


async def test_casting_waits_then_a_bite_then_reeling_lands_the_fish(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    assert nav.screen.refresh_every is None  # nothing in the water: no self-refresh
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    assert "in the water" in all_text(nav) and nav.screen.refresh_every
    assert [b.label for b in buttons(nav) if b.label in ("Left", "Right")] == []
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    assert "A bite!" in all_text(nav)
    assert [b.label for b in buttons(nav) if b.label in ("Left", "Right")] == []  # reeling hasn't started
    await click(nav, inter, "Pull up the line")
    assert "is on the line" in all_text(nav)
    for arrow in list(cast.pattern):
        await click(nav, inter, "Left" if arrow == f.LEFT else "Right")
    assert nav.screen.cast is None and nav.screen.refresh_every is None
    assert "You caught a" in all_text(nav)
    assert await user.item_quantity("cod") == 1 and (await user.skill("fishing")).xp > 0
    await click(nav, inter, "Sell fish")
    await user.refresh()
    assert await user.item_quantity("cod") == 0 and "You sold" in all_text(nav)


async def test_a_wrong_arrow_on_the_screen_loses_the_fish_and_a_stale_click_is_harmless(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    wrong = "Right" if nav.screen.cast.next_arrow == f.LEFT else "Left"
    stale = find_button(nav, wrong)
    await click(nav, inter, wrong)
    assert nav.screen.cast is None and "slipped off" in all_text(nav)
    await stale.callback(inter)  # a click that was already on its way
    assert nav.screen.cast is None and await user.item_quantity("cod") == 0


async def test_a_fish_that_bites_while_you_are_away_gets_away(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.expires_at + 5
    await nav.screen.nav.refresh(inter)
    assert nav.screen.cast is None and "too slow" in all_text(nav)
    assert not find_button(nav, "Cast").disabled


async def test_pulling_up_the_line_costs_nothing(db, clock):
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    await click(nav, inter, "Cancel cast")
    assert nav.screen.cast is None and "reel the line back in" in all_text(nav)
    assert await user.get_bits() == user.purse


async def test_a_better_rod_shows_how_many_slips_it_forgives(db):
    user = await player(1, "masterwork_rod")
    nav, _ = await hub("fish")
    assert "forgives" in all_text(nav)


# ---- quests -----------------------------------------------------------------------------------------------------
DAY0 = 19_996 * f.DAY  # the start of a UTC day that is a Monday
Q = RULES.quests


async def level_up(user, level=Q.min_level):
    await user.add_xp("fishing", User.level_to_xp(level) + 1)
    assert User.xp_to_level((await user.skill("fishing")).xp) == level


async def catch(user, fish_id, now):
    cast = cast_of(fish_id)
    for arrow in cast.pattern:
        cast.press(arrow, T0 + 11)
    return await f.land(user, cast, REG, now=now)


def test_weeks_run_monday_to_sunday():
    assert f.week_of(DAY0) == f.week_of(DAY0 + 6.9 * f.DAY) != f.week_of(DAY0 + 7 * f.DAY)
    assert f.week_of(DAY0 - 1) != f.week_of(DAY0)


async def test_quests_are_locked_below_the_level(db):
    user = await player()
    assert await f.quests(user, DAY0, REG) == []
    await level_up(user, Q.min_level - 1)
    assert await f.quests(user, DAY0, REG) == []


async def test_you_get_a_quest_per_slot_each_asking_for_a_specific_fish_and_they_stay_put_all_period(db):
    user = await player()
    await level_up(user)
    first = await f.quests(user, DAY0, REG)
    assert [q.kind for q in first] == ["daily"] * len(Q.daily) + ["weekly"] * len(Q.weekly)
    for quest, slot in zip(first, [*Q.daily, *Q.weekly], strict=False):
        assert quest.fish.rarity == slot.rarity and slot.min_count <= quest.count <= slot.max_count
        assert quest.fish.id in {i.id for i in f.fish_pool(REG)}
    mult = {"daily": Q.daily_bits_multiplier, "weekly": Q.weekly_bits_multiplier}
    assert all(q.bits == round(q.fish.sell_price * q.count * mult[q.kind]) for q in first)
    assert all(q.xp == q.fish.rarity * q.count * Q.xp_per_rarity for q in first)
    assert "Catch" in first[0].text and first[0].fish.name in first[0].text
    assert [(q.fish.id, q.count) for q in await f.quests(user, DAY0 + 3600, REG)] == [(q.fish.id, q.count) for q in first]
    days = {tuple(q.fish.id for q in await f.quests(user, DAY0 + d * f.DAY, REG) if q.kind == "daily") for d in range(8)}
    assert len(days) > 1  # a different set on different days
    others = {tuple(q.fish.id for q in await f.quests(await level_up_player(uid), DAY0, REG)) for uid in range(10, 16)}
    assert len(others) > 1  # and different players get different fish


async def level_up_player(user_id):
    user = await player(user_id)
    await level_up(user)
    return user


async def test_the_two_common_slots_ask_for_different_fish_where_they_can(db):
    user = await player()
    await level_up(user)
    for day in range(30):
        commons = [q.fish.id for q in await f.quests(user, DAY0 + day * f.DAY, REG) if q.kind == "daily" and q.fish.rarity == 1]
        assert len(commons) == len(set(commons))


async def test_only_the_asked_for_fish_counts_and_finishing_pays_once(db):
    user = await player()
    await level_up(user)
    daily = next(q for q in await f.quests(user, DAY0, REG) if q.kind == "daily" and q.fish.rarity == 1)
    other = next(i.id for i in f.fish_pool(REG) if i.rarity == 1 and i.id != daily.fish.id)
    got = await catch(user, other, DAY0 + 5)
    assert not got.finished
    assert next(q for q in await f.quests(user, DAY0 + 6, REG) if q.index == daily.index and q.kind == "daily").progress == 0
    before, paid = user.purse, 0
    for _ in range(daily.count + 2):
        paid += (await catch(user, daily.fish.id, DAY0 + 10)).quest_bits
    await user.refresh()
    assert paid == daily.bits and user.purse == before + paid  # paid once, however many more you catch
    after = next(q for q in await f.quests(user, DAY0 + 20, REG) if q.index == daily.index and q.kind == "daily")
    assert after.done and (await user.skill("fishing")).stats.quests_completed >= 1


async def test_a_new_day_starts_fresh_but_the_week_carries_on_and_a_new_week_resets(db):
    user = await player()
    await level_up(user)
    weekly = next(q for q in await f.quests(user, DAY0, REG) if q.kind == "weekly")
    daily = next(q for q in await f.quests(user, DAY0, REG) if q.kind == "daily")
    await catch(user, weekly.fish.id, DAY0)
    await catch(user, daily.fish.id, DAY0)
    today, tomorrow = await f.quests(user, DAY0, REG), await f.quests(user, DAY0 + f.DAY, REG)
    assert any(q.progress or q.done for q in today if q.kind == "daily")
    assert not any(q.progress or q.done for q in tomorrow if q.kind == "daily")
    assert [(q.fish.id, q.progress) for q in tomorrow if q.kind == "weekly"] == [(q.fish.id, q.progress) for q in today if q.kind == "weekly"]
    assert not any(q.progress or q.done for q in await f.quests(user, DAY0 + 7 * f.DAY, REG))


async def test_the_catch_that_unlocks_quests_does_not_count_toward_them(db):
    user = await player()
    await level_up(user, Q.min_level - 1)
    just_under = User.level_to_xp(Q.min_level) - (await user.skill("fishing")).xp - 1
    await user.add_xp("fishing", just_under)  # one xp short of the level
    quest_fish = [i for i in f.fish_pool(REG) if i.rarity == 1][0]
    await catch(user, quest_fish.id, DAY0)  # this catch takes them over the line
    assert User.xp_to_level((await user.skill("fishing")).xp) == Q.min_level
    assert all(q.progress == 0 for q in await f.quests(user, DAY0, REG))


async def test_quest_xp_is_added_on_top_of_the_catch(db):
    user = await player()
    await level_up(user)
    weekly = next(q for q in await f.quests(user, DAY0, REG) if q.kind == "weekly")
    before = (await user.skill("fishing")).xp
    got = None
    for _ in range(weekly.count):
        got = await catch(user, weekly.fish.id, DAY0)
    gained = (await user.skill("fishing")).xp - before
    assert got.finished and gained >= weekly.count * weekly.fish.rarity * RULES.xp_per_rarity + weekly.xp


async def test_the_quests_page_and_the_catch_message(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("pufferfish"))
    clock[0] = DAY0 + 100
    user, nav, inter = await open_fishing()
    assert find_button(nav, "Quests").disabled and "unlock at fishing level" in all_text(nav)
    await level_up(user)
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    cast = nav.screen.cast
    await click(nav, inter, "Pull up the line")
    for arrow in list(cast.pattern):
        await click(nav, inter, "Left" if arrow == f.LEFT else "Right")
    assert "You caught a" in all_text(nav)
    assert not find_button(nav, "Quests").disabled
    await click(nav, inter, "Quests")
    assert nav.screen.id == "fishquests" and "Daily" in all_text(nav) and "Weekly" in all_text(nav)
    await click(nav, inter, "Back to fishing")
    assert nav.screen.id == "fish"


async def test_a_bite_you_ignore_gets_away_once_the_window_and_the_quiet_grace_are_over(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + RULES.bite.window - 1
    await nav.screen.nav.refresh(inter)
    assert "A bite!" in all_text(nav)
    clock[0] = nav.screen.cast.bite_at + RULES.bite.window + RULES.bite.grace - 0.5  # past the six seconds, in the grace
    await nav.screen.nav.refresh(inter)
    assert "A bite!" in all_text(nav) and nav.screen.cast is not None  # still hers: the connection may be slow
    clock[0] = nav.screen.cast.bite_at + RULES.bite.window + RULES.bite.grace + 1
    await nav.screen.nav.refresh(inter)
    assert nav.screen.cast is None and "too slow" in all_text(nav)


# ---- more fish ---------------------------------------------------------------------------------------------------
def test_every_rarity_has_fish_and_the_rare_ones_exist():
    by_rarity = Counter(i.rarity for i in f.fish_pool(REG))
    assert set(by_rarity) == set(range(1, 8))
    assert by_rarity[7] >= 2 and by_rarity[6] >= 2 and by_rarity[5] >= 3
    assert all(i.category == "fish" for i in f.fish_pool(REG))


def test_rare_fish_really_can_be_caught_and_are_worth_the_wait():
    rng, seen = Random(5), Counter()
    for _ in range(200_000):
        seen[f.roll_fish(rng, REG).rarity] += 1
    assert all(seen[r] > 0 for r in range(1, 8))
    worth = {i.rarity: i.sell_price for i in f.fish_pool(REG)}
    assert worth[7] > worth[6] > worth[5] > worth[4] > worth[3] > worth[2]


# ---- things that come up with a catch -----------------------------------------------------------------------------
def test_coral_comes_up_now_and_then_but_only_with_a_catch():
    rng = Random(1)
    got = Counter()
    for _ in range(6000):
        got += f.catch_extras(rng, REG)
    assert set(got) == {"coral_shard"} and 600 < got["coral_shard"] < 1400  # about 1 in 6


async def test_landing_a_fish_can_bring_coral_with_it(db):
    class Lucky(Random):
        def randint(self, a, b):
            return 1  # every drop table hits

    user = await player()
    cast = cast_of()
    for arrow in cast.pattern:
        cast.press(arrow, T0 + 11)
    got = await f.land(user, cast, REG, now=T0, rng=Lucky(1))
    assert got.extras["coral_shard"] == 1 and await user.item_quantity("coral_shard") == 1


# ---- the pickaxe: upgradable with a bit from every skill -----------------------------------------------------------
def test_the_first_pickaxe_upgrade_wants_something_from_every_skill():
    needs = REG.item("rookiepickaxe").tool.upgrade.items
    skills = {REG.item(i).skill for i in needs}
    assert skills == {"mining", "foraging", "farming", "fishing"}
    for item_id in needs:  # every material really drops somewhere
        assert REG.item(item_id).drop is not None, item_id


async def test_you_can_upgrade_a_pickaxe_with_materials_from_all_four_skills(db):
    from cococap.services import upgrades

    user = await User.get(1)
    await set_columns(user, purse=10**6)
    pick = await user.give_instance("rookiepickaxe")
    await equip(user, "mining", pick.id)
    cost = REG.item("rookiepickaxe").tool.upgrade
    for item_id, quantity in cost.items.items():
        await user.add_item(item_id, quantity)
    done = await upgrades.upgrade(user, pick.id, REG)
    assert done.target.id == "reinforced_pickaxe"
    assert (await user.instance(pick.id)).template_id == "reinforced_pickaxe"


async def test_a_harvest_can_bring_plant_fiber(db):
    from cococap.services import farming

    class Lucky(Random):
        def randint(self, a, b):
            return 1

    assert farming.harvest_extras(Lucky(1), REG)["plant_fiber"] == 1
    assert sum(farming.harvest_extras(Random(2), REG)["plant_fiber"] for _ in range(1000)) > 500


# ---- the collection book ----------------------------------------------------------------------------------------------
B = RULES.book


async def book_player(user_id=1, fish=None):
    user = await player(user_id)
    await user.add_xp("fishing", User.level_to_xp(B.min_level) + 1)
    for fish_id, quantity in (fish or {}).items():
        await user.add_item(fish_id, quantity)
    return user


def test_the_book_holds_common_to_super_rare_fish_only():
    book = f.book_fish(REG)
    assert {i.rarity for i in book} == set(range(1, B.max_rarity + 1)) and len(book) >= 8
    assert [i.rarity for i in book] == sorted(i.rarity for i in book)
    assert all(i.rarity <= B.max_rarity for i in book)


def test_each_book_level_needs_more_but_common_fish_grow_fastest():
    need = lambda level, rarity: f.book_need(level, rarity, RULES)
    assert [need(1, r) for r in range(1, 5)] == [B.need_base] * 4  # level 1: one of each
    assert [need(2, r) for r in range(1, 5)] == [5, 3, 1, 1]  # level 2: 5 common, 3 uncommon, 1 rare, 1 super rare
    for rarity in range(1, 5):
        assert [need(level, rarity) for level in range(1, 11)] == sorted(need(level, rarity) for level in range(1, 11))
    for level in range(2, 11):
        assert need(level, 1) > need(level, 2) > need(level, 3) >= need(level, 4)
    assert need(10, 1) > need(5, 1) > need(2, 1)


async def test_the_book_is_locked_until_the_level(db):
    user = await player()
    with pytest.raises(f.FishingError, match="opens at fishing level"):
        await f.turn_in(user, "cod", REG)


async def test_turning_in_fish_pays_a_bonus_and_fills_the_page(db):
    user = await book_player(fish={"cod": 3})
    before_xp, before_bits = (await user.skill("fishing")).xp, user.purse
    done = await f.turn_in(user, "cod", REG)
    assert done.quantity == B.need_base  # only as many as the page needs (level 1: one)
    assert done.bits == round(REG.item("cod").sell_price * B.bits_per_sell * done.quantity)
    assert await user.item_quantity("cod") == 3 - done.quantity  # the rest stay in the bag
    await user.refresh()
    assert user.purse == before_bits + done.bits and (await user.skill("fishing")).xp == before_xp + done.xp
    page = next(e for e in (await f.book(user, REG)).entries if e.fish.id == "cod")
    assert page.done
    with pytest.raises(f.FishingError, match="already has"):
        await f.turn_in(user, "cod", REG)


async def test_you_cannot_turn_in_fish_you_do_not_have_or_that_the_book_does_not_hold(db):
    user = await book_player()
    with pytest.raises(f.FishingError, match="don't have any"):
        await f.turn_in(user, "cod", REG)
    await user.add_item("marlin", 1)  # legendary: not in the personal book
    with pytest.raises(f.FishingError, match="no page"):
        await f.turn_in(user, "marlin", REG)
    assert await user.item_quantity("marlin") == 1


async def test_two_clicks_at_once_cannot_turn_in_more_than_the_page_needs(db):
    import asyncio

    user = await book_player(fish={"cod": 5})
    results = await asyncio.gather(f.turn_in(user, "cod", REG), f.turn_in(user, "cod", REG), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 1
    page = next(e for e in (await f.book(user, REG)).entries if e.fish.id == "cod")
    assert page.given == page.need
    assert await user.item_quantity("cod") == 5 - page.need  # nothing was eaten for nothing


async def test_a_full_book_can_be_finished_and_starts_over_a_level_up(db):
    user = await book_player(fish={i.id: 5 for i in f.book_fish(REG)})
    with pytest.raises(f.FishingError, match="isn't full"):
        await f.complete_book(user, REG)
    for item in f.book_fish(REG):
        await f.turn_in(user, item.id, REG)
    assert (await f.book(user, REG)).complete
    before = user.purse
    done = await f.complete_book(user, REG)
    await user.refresh()
    assert done.new_level == 2 and done.bits == B.completion_bits and user.purse >= before + done.bits
    again = await f.book(user, REG)
    assert again.level == 2 and not again.complete and all(e.given == 0 and e.need == f.book_need(2, e.fish.rarity, RULES) for e in again.entries)
    with pytest.raises(f.FishingError, match="isn't full"):
        await f.complete_book(user, REG)  # no double payout


async def test_the_book_stops_at_its_top_level(db):
    user = await book_player()
    await user.update_skill("fishing", lambda s: setattr(s.book, "level", B.max_level))
    await user.update_skill("fishing", lambda s: s.book.given.update(
        {i.id: f.book_need(B.max_level, i.rarity, RULES) for i in f.book_fish(REG)}))
    with pytest.raises(f.FishingError, match="highest level"):
        await f.complete_book(user, REG)


async def test_the_book_screen_turns_fish_in_and_finishes_the_book(db):
    user = await book_player(fish={i.id: 2 for i in f.book_fish(REG)})
    nav, inter = await hub("fishbook")
    text_now = all_text(nav)
    assert "Book level 1" in text_now and "0/1" in text_now
    from tests.test_hub import choose, select_named

    for item in f.book_fish(REG):
        menu = select_named(nav, "Turn in")
        await choose(nav, inter, menu, item.id)
    assert "✅" in all_text(nav) and not find_button(nav, "Finish the book").disabled
    await click(nav, inter, "Finish the book")
    assert "Book complete" in all_text(nav) and "Book level 2" in all_text(nav)
    assert find_button(nav, "Finish the book").disabled


async def test_the_fishing_page_shows_the_book_button_once_unlocked(db):
    user = await player()
    nav, _ = await hub("fish")
    assert find_button(nav, "Book").disabled
    await user.add_xp("fishing", User.level_to_xp(B.min_level) + 1)
    nav, inter = await hub("fish")
    assert not find_button(nav, "Book").disabled
    await click(nav, inter, "Book")
    assert nav.screen.id == "fishbook"


async def test_a_stale_second_click_gets_its_fish_back_when_the_page_filled_in_the_meantime(db, monkeypatch):
    user = await book_player(fish={"cod": 5})
    stale = await f.book(user, REG)  # what the second click saw before the first one landed
    await f.turn_in(user, "cod", REG)

    async def old_view(*_args, **_kwargs):
        return stale

    monkeypatch.setattr(f, "book", old_view)
    before = await user.item_quantity("cod")
    with pytest.raises(f.FishingError, match="already has"):
        await f.turn_in(user, "cod", REG)
    assert await user.item_quantity("cod") == before  # nothing was eaten
    page = next(e for e in stale.entries if e.fish.id == "cod")
    monkeypatch.undo()
    assert next(e for e in (await f.book(user, REG)).entries if e.fish.id == "cod").given == page.need


# ---- treasure ------------------------------------------------------------------------------------------------------
T = RULES.treasure


class Lucky(Random):
    """Every 1-in-N roll hits, every chance succeeds."""

    def randint(self, a, b):
        return a  # the 1 in 1-in-N rolls, and the smallest sum of bits

    def random(self):
        return 0.0

    def choice(self, seq):
        return seq[min(7, len(seq) - 1)]  # every digit is a 7: the numbers are 7777


class Unlucky(Random):
    def randint(self, a, b):
        return b

    def random(self):
        return 0.999


def test_hallucinations_are_a_little_rarer_than_the_wiki_and_chests_match_them():
    assert T.hallucination_odds > 25  # the wiki says 1 in 25
    assert T.chest_odds == T.hallucination_odds
    assert T.code_length == 4 and T.attempts >= 1
    assert T.loot[-1].item == "spirit_of_the_sea" and T.loot[-1].chance == 0.001  # 1 in 1,000, as in the wiki


def test_a_chest_can_only_turn_up_while_a_hallucination_lasts():
    assert not f.cast_line(rod(), Lucky(1), T0, REG).chest
    assert f.cast_line(rod(), Lucky(1), T0, REG, armed=True).chest
    assert not f.cast_line(rod(), Unlucky(1), T0, REG, armed=True).chest
    chest = f.cast_line(rod(), Lucky(1), T0, REG, armed=True)
    assert chest.attempts_left == T.attempts


def test_a_chest_is_hooked_like_a_fish_but_then_wants_numbers_not_arrows():
    chest = f.cast_line(rod(), Lucky(1), T0, REG, armed=True)
    assert chest.status(chest.bite_at + 1) == "bite"  # looks exactly like any bite
    chest.hook(chest.bite_at + 1)
    assert chest.status(chest.bite_at + 1) == "chest"
    with pytest.raises(f.FishingError, match="chest"):
        chest.press(f.LEFT, chest.bite_at + 1)


async def test_a_catch_can_trigger_a_hallucination_and_only_one_at_a_time(db):
    user = await player()
    cast = cast_of()
    for arrow in cast.pattern:
        cast.press(arrow, T0 + 11)
    got = await f.land(user, cast, REG, now=T0, rng=Lucky(1))
    assert got.hallucination and len(got.hallucination) == T.code_length and got.hallucination.isdigit()
    state = (await user.skill("fishing")).treasure
    assert state.code == got.hallucination and state.armed_until == T0 + T.armed_minutes * 60
    assert await f.chests_possible(user, T0 + 60) and not await f.chests_possible(user, T0 + T.armed_minutes * 60 + 1)
    again = cast_of()
    for arrow in again.pattern:
        again.press(arrow, T0 + 11)
    second = await f.land(user, again, REG, now=T0 + 30, rng=Lucky(2))
    assert second.hallucination is None and (await user.skill("fishing")).treasure.code == got.hallucination
    quiet = cast_of()
    for arrow in quiet.pattern:
        quiet.press(arrow, T0 + 11)
    other = await player(2)
    assert (await f.land(other, quiet, REG, now=T0, rng=Unlucky(1))).hallucination is None


async def armed_chest(user, code="4815"):
    await user.update_skill("fishing", lambda s: setattr(s, "treasure", __import__("cococap.models.skills.fishing", fromlist=["x"]).TreasureState(code=code, armed_until=T0 + 600)))
    chest = f.cast_line(rod(), Lucky(1), T0, REG, armed=True)
    chest.hook(chest.bite_at + 1)
    return chest


async def test_the_right_numbers_open_the_chest_once_and_pay(db):
    user = await player()
    chest = await armed_chest(user)
    before = user.purse
    opened = await f.open_chest(user, chest, "4 8 1 5", Lucky(3), chest.bite_at + 2, REG)
    await user.refresh()
    assert opened.opened and T.bits_min <= opened.bits <= T.bits_max and user.purse == before + opened.bits
    assert opened.items["coral_shard"] >= 2 and opened.items["spirit_of_the_sea"] == 1  # a lucky chest has everything
    assert await user.item_quantity("spirit_of_the_sea") == 1
    skill = await user.skill("fishing")
    assert skill.stats.treasures_found == 1 and skill.treasure.code == "" and skill.xp >= T.xp
    with pytest.raises(f.FishingError, match="no chest"):
        await f.open_chest(user, chest, "4815", Lucky(3), chest.bite_at + 3, REG)
    assert await user.item_quantity("spirit_of_the_sea") == 1  # not paid twice


async def test_wrong_numbers_cost_a_try_and_too_many_sink_the_chest(db):
    user = await player()
    chest = await armed_chest(user)
    for tries_left in range(T.attempts - 1, 0, -1):
        tried = await f.open_chest(user, chest, "0000", Lucky(3), chest.bite_at + 2, REG)
        assert not tried.opened and not tried.sunk and tried.attempts_left == tries_left
    last = await f.open_chest(user, chest, "1111", Lucky(3), chest.bite_at + 2, REG)
    assert last.sunk and not last.opened and chest.escaped
    assert (await user.skill("fishing")).treasure.code == ""  # the hallucination is spent
    assert await user.get_bits() == user.purse and await user.item_quantity("coral_shard") == 0
    with pytest.raises(f.FishingError, match="no chest"):
        await f.open_chest(user, chest, "4815", Lucky(3), chest.bite_at + 3, REG)


async def test_the_numbers_cannot_be_guessed_after_they_are_used_up(db):
    user = await player()
    chest = await armed_chest(user)
    await user.update_skill("fishing", lambda s: setattr(s.treasure, "code", ""))  # e.g. opened by another click
    gone = await f.open_chest(user, chest, "4815", Lucky(3), chest.bite_at + 2, REG)
    assert gone.sunk and not gone.opened


async def test_the_screen_flashes_the_numbers_then_hides_them_and_the_chest_opens_with_them(db, clock, monkeypatch):
    monkeypatch.setattr(fish_screen, "new_rng", lambda: Lucky(1))
    clock[0] = T0
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    cast = nav.screen.cast
    for arrow in list(cast.pattern):
        await click(nav, inter, "Left" if arrow == f.LEFT else "Right")
    code = (await user.skill("fishing")).treasure.code
    assert code and "   ".join(code) in all_text(nav) and "Remember them" in all_text(nav)
    assert nav.screen.refresh_every  # keeps redrawing so the numbers can fade by themselves
    assert "Leviathan Pup" in all_text(nav) and "Mythical" in all_text(nav)  # the catch says how rare it was
    clock[0] += T.flash_seconds + 1
    await nav.screen.nav.refresh(inter)
    assert "   ".join(code) not in all_text(nav) and "slip away" in all_text(nav) and nav.screen.flash is None
    assert "hallucination lingers" in all_text(nav) and nav.screen.refresh_every is None
    await click(nav, inter, "Cast")  # armed: with these dice the next cast is a chest
    assert nav.screen.cast.chest
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    assert "A bite!" in all_text(nav) and "chest" not in all_text(nav).lower()
    await click(nav, inter, "Pull up the line")
    assert "treasure chest" in all_text(nav)
    await click(nav, inter, "Enter the numbers")
    modal = inter.response.send_modal.await_args.args[0]
    await modal._handler(inter, "0000")
    assert "Wrong numbers" in all_text(nav) and f"**{T.attempts - 1}** tries left" in all_text(nav)
    await click(nav, inter, "Enter the numbers")
    await inter.response.send_modal.await_args.args[0]._handler(inter, code)
    assert "lock clicks open" in all_text(nav) and nav.screen.cast is None
    assert (await user.skill("fishing")).stats.treasures_found == 1


async def test_a_catch_names_its_rarity(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("salmon"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    for arrow in list(nav.screen.cast.pattern):
        await click(nav, inter, "Left" if arrow == f.LEFT else "Right")
    assert "You caught a" in all_text(nav) and "Salmon" in all_text(nav) and "**Rare**" in all_text(nav)


async def test_the_second_book_asks_for_more_common_fish_than_rare_ones(db):
    user = await book_player(fish={i.id: 10 for i in f.book_fish(REG)})
    for item in f.book_fish(REG):
        await f.turn_in(user, item.id, REG)
    await f.complete_book(user, REG)
    second = await f.book(user, REG)
    needs = {e.fish.rarity: e.need for e in second.entries}
    assert needs == {1: 5, 2: 3, 3: 1, 4: 1}
    assert not second.complete
    common = next(e for e in second.entries if e.fish.rarity == 1)
    done = await f.turn_in(user, common.fish.id, REG)
    assert done.quantity == 5  # the page takes five, not one
    assert await user.item_quantity(common.fish.id) == 10 - 1 - 5  # one went in at level 1, five now


# ---- not losing the fish to lag ---------------------------------------------------------------------------------------
def laggy_cast(**kw):
    cast = cast_of(hooked=False, **kw)
    cast.grace, cast.echo_window = RULES.bite.grace, RULES.reel.echo_window
    return cast


def test_a_laggy_click_in_the_quiet_grace_still_lands_the_fish():
    cast = laggy_cast()
    late = T0 + 10 + RULES.bite.window + RULES.bite.grace - 0.1
    cast.hook(late)  # past the six seconds, inside the grace
    assert cast.hooked and cast.status(late) == "reeling"


def test_a_click_that_was_made_in_time_saves_a_fish_the_bot_already_wrote_off():
    cast = laggy_cast()
    assert cast.status(T0 + 10 + RULES.bite.window + RULES.bite.grace + 1) == "escaped" and cast.timed_out
    assert cast.salvage(T0 + 10 + RULES.bite.window - 1)  # the click itself was made in the window
    assert cast.hooked and not cast.escaped and cast.status(T0 + 99) == "reeling"


def test_a_click_that_really_was_late_does_not_save_it():
    cast = laggy_cast()
    cast.status(T0 + 100)
    assert not cast.salvage(T0 + 10 + RULES.bite.window + RULES.bite.grace + 0.5)
    assert not cast.salvage(T0 + 5)  # nor one from before it bit
    assert cast.escaped


def test_a_fish_lost_to_a_wrong_arrow_cannot_be_salvaged():
    cast = cast_of(hooked=True)
    cast.press(f.RIGHT, T0 + 11)  # wrong (the pattern starts with LEFT) and no slips: it escapes
    assert cast.escaped and not cast.timed_out and not cast.salvage(T0 + 11)


def test_pressing_the_arrow_you_just_pressed_again_is_ignored_when_it_is_a_repeat():
    cast = cast_of(pattern=[f.LEFT, f.RIGHT, f.LEFT])
    cast.echo_window = 2.0
    assert cast.press(f.LEFT, T0 + 11) == "ok"
    assert cast.press(f.LEFT, T0 + 11.5) == "echo"  # the panel was slow to show the first press
    assert cast.progress == 1 and not cast.escaped and cast.slips_left == 0
    assert cast.press(f.RIGHT, T0 + 12) == "ok"  # and the game carries on


def test_a_real_mistake_is_still_a_mistake():
    cast = cast_of(pattern=[f.LEFT, f.RIGHT, f.LEFT])
    cast.echo_window = 2.0
    cast.press(f.LEFT, T0 + 11)
    assert cast.press(f.LEFT, T0 + 14) == "escaped"  # the same arrow, but much later: it was a real slip
    other = cast_of(pattern=[f.LEFT, f.RIGHT, f.LEFT])
    other.echo_window = 2.0
    assert other.press(f.RIGHT, T0 + 11) == "escaped"  # nothing was pressed before: not an echo
    third = cast_of(pattern=[f.LEFT, f.LEFT, f.RIGHT])
    third.echo_window = 2.0
    third.press(f.LEFT, T0 + 11)
    third.press(f.LEFT, T0 + 11.2)  # a genuine second left, as the pattern asks
    assert third.press(f.LEFT, T0 + 11.4) == "echo" and third.progress == 2


def clicked(inter, at):
    inter.created_at = datetime.datetime.fromtimestamp(at, datetime.timezone.utc)


async def test_the_screen_uses_when_you_clicked_not_when_the_bot_noticed(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    # the bot is slow: it only gets round to the click long after the window shut, but Discord stamped it in time
    clock[0] = cast.bite_at + RULES.bite.window + RULES.bite.grace + 30
    clicked(inter, cast.bite_at + 2)
    await nav.screen.nav.refresh(inter)  # the redraw notices the fish got away
    assert nav.screen.cast is None and nav.screen.missed is cast
    await nav.screen.nav.refresh(inter)
    await nav.screen.nav.show(inter, "fish", push=False)
    # (a fresh screen has no memory of it, as it should: salvage only covers the screen the click was made on)
    assert nav.screen.missed is None


async def test_a_click_made_in_time_but_delivered_late_saves_the_fish_on_the_same_screen(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    pull_up = None
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    pull_up = find_button(nav, "Pull up the line")  # the button she clicked
    clock[0] = cast.bite_at + RULES.bite.window + RULES.bite.grace + 5  # ...but the click only reaches us now
    await nav.screen.nav.refresh(inter)
    assert nav.screen.cast is None and "too slow" in all_text(nav)
    clicked(inter, cast.bite_at + 3)  # Discord's stamp: she clicked three seconds after the bite
    await pull_up.callback(inter)
    assert nav.screen.cast is cast and cast.hooked and "just in time" in all_text(nav) and "is on the line" in all_text(nav)
    for arrow in list(cast.pattern):
        await click(nav, inter, "Left" if arrow == f.LEFT else "Right")
    assert await user.item_quantity("cod") == 1


async def test_a_click_that_really_was_too_late_stays_too_late(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    pull_up = find_button(nav, "Pull up the line")
    clock[0] = cast.bite_at + 60
    await nav.screen.nav.refresh(inter)
    clicked(inter, cast.bite_at + 30)  # clicked long after it got away
    await pull_up.callback(inter)
    assert nav.screen.cast is None and await user.item_quantity("cod") == 0


async def test_a_double_pressed_arrow_on_the_screen_does_not_cost_the_fish(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    cast = nav.screen.cast
    first = cast.pattern[0]
    await click(nav, inter, "Left" if first == f.LEFT else "Right")
    stale = find_button(nav, "Left" if first == f.LEFT else "Right")  # she presses the same button again (the panel lagged)
    if cast.pattern[1] != first:
        await stale.callback(inter)
        assert nav.screen.cast is cast and not cast.escaped and cast.progress == 1


# ---- record fish ------------------------------------------------------------------------------------------------------
def test_every_fish_has_a_size_range_and_catches_vary_within_it():
    for fish in f.fish_pool(REG):
        assert fish.size is not None and fish.size.min < fish.size.max
        sizes = [f.roll_size(fish, Random(i)) for i in range(300)]
        assert min(sizes) >= fish.size.min and max(sizes) <= fish.size.max
        assert len(set(sizes)) > 100 and sum(sizes) / 300 < fish.size.min + 0.42 * (fish.size.max - fish.size.min)  # mostly smaller, a few giants


def test_a_cast_fixes_its_size_up_front():
    first = f.cast_line(rod(3), Random(7), T0, REG)
    again = f.cast_line(rod(3), Random(7), T0, REG)
    assert first.size == again.size and first.fish.size.min <= first.size <= first.fish.size.max


async def test_your_biggest_catch_of_each_fish_is_kept_and_beating_it_pays_xp(db):
    user = await player()
    first = cast_of("cod")
    first.size = 50.0
    for arrow in first.pattern:
        first.press(arrow, T0 + 11)
    got = await f.land(user, first, REG, now=T0)
    assert got.size == 50 and got.personal_best  # the first of a fish is a best
    assert (await user.skill("fishing")).records == {"cod": 50.0}
    xp_after_first = (await user.skill("fishing")).xp
    smaller = cast_of("cod")
    smaller.size = 40.0
    for arrow in smaller.pattern:
        smaller.press(arrow, T0 + 11)
    small = await f.land(user, smaller, REG, now=T0)
    assert not small.personal_best and (await user.skill("fishing")).records["cod"] == 50.0
    bigger = cast_of("cod")
    bigger.size = 90.0
    for arrow in bigger.pattern:
        bigger.press(arrow, T0 + 11)
    assert (await f.land(user, bigger, REG, now=T0)).personal_best
    assert (await user.skill("fishing")).records["cod"] == 90.0 and (await user.skill("fishing")).xp > xp_after_first


async def test_the_biggest_fish_on_the_server_is_a_record_that_pays_and_names_the_old_holder(db):
    alice, bob = await player(1), await player(2)
    await alice.set_name("Alice")
    await bob.set_name("Bob")

    async def land_size(user, size, fish="salmon"):
        cast = cast_of(fish)
        cast.size = size
        for arrow in cast.pattern:
            cast.press(arrow, T0 + 11)
        return await f.land(user, cast, REG, now=T0)

    first = await land_size(alice, 80.0)
    assert first.server_record and first.record_holder is None
    assert first.record_bits == round(REG.item("salmon").sell_price * RULES.records.server_bits_multiplier)
    smaller = await land_size(bob, 70.0)
    assert smaller.personal_best and not smaller.server_record and smaller.record_bits == 0  # his best, not the server's
    before = bob.purse
    beaten = await land_size(bob, 95.0)
    await bob.refresh()
    assert beaten.server_record and beaten.record_holder == "Alice" and bob.purse >= before + beaten.record_bits
    assert (await f.server_records())["salmon"] == {"size": 95.0, "uid": 2, "name": "Bob"}
    tie = await land_size(alice, 95.0)
    assert not tie.server_record  # you have to beat it, not match it


async def test_a_catch_says_its_size_and_a_record_and_the_records_page_lists_them(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("salmon"))
    user, nav, inter = await open_fishing()
    await user.set_name("Ahna")
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    size = nav.screen.cast.size
    for arrow in list(nav.screen.cast.pattern):
        await click(nav, inter, "Left" if arrow == f.LEFT else "Right")
    text_now = all_text(nav)
    assert f"{size:g} cm" in text_now and "NEW SERVER RECORD" in text_now
    nav2, inter2 = await hub("fishrecords")
    page = all_text(nav2)
    assert "Salmon" in page and f"{size:g} cm" in page and "Ahna" in page and "👑" in page and "???" in page  # unseen fish stay hidden


async def test_the_records_page_is_reachable_from_the_book_and_the_community(db):
    user = await User.get(1)
    await user.add_xp("fishing", User.level_to_xp(RULES.book.min_level) + 1)
    for screen in ("fishbook", "fishcommunity"):
        nav, inter = await hub(screen)
        await click(nav, inter, "Records")
        assert nav.screen.id == "fishrecords"
        await click(nav, inter, "Back to fishing")
        assert nav.screen.id == "fish"
