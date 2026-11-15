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
    assert 22 <= seconds <= 36, seconds  # a catch every ~25-30 seconds: about what mining and foraging pay per active minute


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
    assert sum(t != f.REEL for t in first.pattern) == RULES.reel.base_length + first.fish.rarity  # (plus Reel breaks)


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
    assert caught.xp == RULES.xp_per_catch and caught.fish.id == "salmon"
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
    assert await catch() == round(base * (1 + REG.economy.party_xp_bonus_by_size[0]))


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


async def reel_in(nav, inter, cast):
    """Press every step the reel asks for (arrows, and Reel for a 🌀), seeing through any ❓."""
    for step in list(cast.truth or cast.pattern):
        await click(nav, inter, {f.LEFT: "Left", f.RIGHT: "Right", f.REEL: "Reel"}[step])


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
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
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
    await reel_in(nav, inter, cast)
    assert nav.screen.id == "result" and "You caught a" in all_text(nav) and nav.screen.origin.cast is None
    assert "Cod" in all_text(nav) and "Common" in all_text(nav) and "cm" in all_text(nav)  # a page of its own, with what she got
    assert find_button(nav, "Cast again") and find_button(nav, "Continue")
    await click(nav, inter, "Continue")
    assert nav.screen.id == "fish" and nav.screen.cast is None and nav.screen.refresh_every is None
    assert await user.item_quantity("cod") == 1 and (await user.skill("fishing")).xp > 0
    await click(nav, inter, "Sell fish")
    await user.refresh()
    assert await user.item_quantity("cod") == 0 and "You sold" in all_text(nav)


async def test_a_wrong_arrow_on_the_screen_loses_the_fish_and_a_stale_click_is_harmless(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    wrong = "Right" if nav.screen.cast.next_arrow == f.LEFT else "Left"
    stale = find_button(nav, wrong)
    await click(nav, inter, wrong)
    assert nav.screen.id == "result" and nav.screen.origin.cast is None and "slipped off" in all_text(nav)
    await stale.callback(inter)  # a click that was already on its way: the result stays on screen
    assert nav.screen.id == "result" and nav.screen.origin.cast is None and await user.item_quantity("cod") == 0


async def test_a_fish_that_bites_while_you_are_away_gets_away(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.expires_at + 5
    await nav.screen.nav.refresh(inter)
    assert nav.screen.id == "result" and "too slow" in all_text(nav).lower()
    await click(nav, inter, "Continue")
    assert nav.screen.cast is None and not find_button(nav, "Cast").disabled


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
    assert got.finished and gained >= weekly.count * RULES.xp_per_catch + weekly.xp


async def test_the_quests_page_and_the_catch_message(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("pufferfish"))
    clock[0] = DAY0 + 100
    user, nav, inter = await open_fishing()
    assert find_button(nav, "Quests").disabled and "unlock at fishing level" in all_text(nav)
    await level_up(user)
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    cast = nav.screen.cast
    await click(nav, inter, "Pull up the line")
    await reel_in(nav, inter, cast)
    assert "You caught a" in all_text(nav)
    await click(nav, inter, "Continue")
    assert not find_button(nav, "Quests").disabled
    await click(nav, inter, "Quests")
    assert nav.screen.id == "fishquests" and "Daily" in all_text(nav) and "Weekly" in all_text(nav)
    await click(nav, inter, "Back to fishing")
    assert nav.screen.id == "fish"


async def test_a_bite_you_ignore_gets_away_once_the_window_and_the_quiet_grace_are_over(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
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
    assert nav.screen.id == "result" and nav.screen.origin.cast is None and "too slow" in all_text(nav).lower()


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
    assert {i for i in got if REG.item(i).category != "pet_food"} == {"coral_shard"} and 600 < got["coral_shard"] < 1400  # about 1 in 6
    assert {i for i in got if REG.item(i).category == "pet_food"} <= {"fish_flakes", "dried_squid", "sea_feast"}  # (and pet food)


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


# ---- the pickaxe: the first upgrade is plain ore, later ones add a little from other skills ----------------------------------
def test_the_first_pickaxe_upgrade_needs_only_ore_and_the_next_adds_a_little_from_other_skills():
    first = REG.item("rookiepickaxe").tool.upgrade.items
    assert {REG.item(i).skill for i in first} == {"mining"}
    second = REG.item("reinforced_pickaxe").tool.upgrade.items
    skills = {REG.item(i).skill for i in second}
    assert skills == {"mining"}  # (the first two steps of a long chain use only the tool's own skill)
    third = REG.item("masterwork_pickaxe").tool.upgrade.items
    assert "mining" in {REG.item(i).skill for i in third} and len({REG.item(i).skill for i in third}) > 1
    for item_id in (*first, *second, *third):  # every material really drops somewhere
        assert REG.item(item_id).drop is not None, item_id


async def test_you_can_upgrade_a_pickaxe_with_nothing_but_ore_at_first(db):
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

        def random(self):
            return 0.0

    assert farming.harvest_extras(Lucky(1), REG, cycles=REG.farming.drop_cycles_per_roll)["plant_fiber"] == 1
    assert sum(farming.harvest_extras(Random(2), REG, cycles=REG.farming.drop_cycles_per_roll)["plant_fiber"] for _ in range(1000)) > 500


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


class LuckyButNoBoss(Lucky):
    """Lucky with hallucinations and chests, but no boss turns up."""

    def randint(self, a, b):
        return b if b == RULES.boss.odds else a


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
    monkeypatch.setattr(fish_screen, "new_rng", lambda: LuckyButNoBoss(1))
    clock[0] = T0
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    cast = nav.screen.cast
    await reel_in(nav, inter, cast)
    code = (await user.skill("fishing")).treasure.code
    assert nav.screen.id == "result"
    assert code and "   ".join(code) in all_text(nav) and "Remember them" in all_text(nav)  # the numbers flash on the result page
    assert nav.screen.refresh_every  # keeps redrawing so the numbers can fade by themselves
    assert "Pufferfish" in all_text(nav) and "Super Rare" in all_text(nav)  # the catch says how rare it was (the pond's rarest fish)
    clock[0] += T.flash_seconds + 1
    await nav.screen.nav.refresh(inter)
    assert "   ".join(code) not in all_text(nav) and "slip away" in all_text(nav) and nav.screen.origin.flash is None
    assert nav.screen.refresh_every is None
    await click(nav, inter, "Continue")
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
    assert nav.screen.id == "result" and "lock clicks open" in all_text(nav) and nav.screen.origin.cast is None
    assert (await user.skill("fishing")).stats.treasures_found == 1


async def test_a_catch_names_its_rarity(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("salmon"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    await reel_in(nav, inter, nav.screen.cast)
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
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    # the bot is slow: it only gets round to the click long after the window shut, but Discord stamped it in time
    clock[0] = cast.bite_at + RULES.bite.window + RULES.bite.grace + 30
    clicked(inter, cast.bite_at + 2)
    await nav.screen.nav.refresh(inter)  # the redraw notices the fish got away
    assert nav.screen.id == "result" and nav.screen.origin.cast is None and nav.screen.origin.missed is cast
    await nav.screen.nav.refresh(inter)
    await nav.screen.nav.show(inter, "fish", push=False)
    # (a fresh screen has no memory of it, as it should: salvage only covers the screen the click was made on)
    assert nav.screen.missed is None


async def test_a_click_made_in_time_but_delivered_late_saves_the_fish_on_the_same_screen(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    pull_up = None
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    pull_up = find_button(nav, "Pull up the line")  # the button she clicked
    clock[0] = cast.bite_at + RULES.bite.window + RULES.bite.grace + 5  # ...but the click only reaches us now
    await nav.screen.nav.refresh(inter)
    assert nav.screen.id == "result" and "too slow" in all_text(nav).lower()
    clicked(inter, cast.bite_at + 3)  # Discord's stamp: she clicked three seconds after the bite
    await pull_up.callback(inter)
    assert nav.screen.id == "fish" and nav.screen.cast is cast and cast.hooked and "just in time" in all_text(nav) and "is on the line" in all_text(nav)
    await reel_in(nav, inter, cast)
    assert await user.item_quantity("cod") == 1


async def test_a_click_that_really_was_too_late_stays_too_late(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
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
    assert nav.screen.id == "result" and nav.screen.origin.cast is None and await user.item_quantity("cod") == 0


async def test_a_double_pressed_arrow_on_the_screen_does_not_cost_the_fish(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
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
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("salmon"))
    user, nav, inter = await open_fishing()
    await user.set_name("Ahna")
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    size = nav.screen.cast.size
    await reel_in(nav, inter, nav.screen.cast)
    text_now = all_text(nav)
    assert f"{size:g} cm" in text_now and "NEW SERVER RECORD" in text_now
    nav2, inter2 = await hub("fishrecords")
    page = all_text(nav2)
    assert "Salmon" in page and f"{size:g} cm" in page and "Ahna" in page and "👑" in page and "fish nobody has caught yet" in page  # unseen fish stay hidden, in one line


async def test_the_records_page_is_reachable_from_the_book_and_the_community(db):
    user = await User.get(1)
    await user.add_xp("fishing", User.level_to_xp(RULES.book.min_level) + 1)
    for screen in ("fishbook", "fishcommunity"):
        nav, inter = await hub(screen)
        await click(nav, inter, "Records")
        assert nav.screen.id == "fishrecords"
        await click(nav, inter, "Back to fishing")
        assert nav.screen.id == "fish"


# ---- bosses ---------------------------------------------------------------------------------------------------------
BOSS = RULES.boss


def test_a_boss_is_rarer_than_a_fish_and_takes_a_long_reel():
    assert BOSS.odds >= 40 and BOSS.length == 15
    assert BOSS.bits_min < BOSS.bits_max and BOSS.loot[0].chance == 1.0
    assert BOSS.length > max(len(f.reel_pattern(i.rarity, RULES, Random(1))) for i in f.fish_pool(REG))  # longer than any fish


def test_now_and_then_a_cast_is_a_boss_with_a_fifteen_arrow_reel_and_a_name():
    boss = f.cast_line(rod(), Lucky(1), T0, REG)
    assert boss.boss in {b.name for b in BOSS.bosses} and sum(t != f.REEL for t in boss.pattern) == BOSS.length and not boss.chest
    assert not f.cast_line(rod(), Unlucky(1), T0, REG).boss
    hits = sum(bool(f.cast_line(rod(), Random(i), T0, REG).boss) for i in range(6000))
    assert 0.5 * 6000 / BOSS.odds < hits < 1.6 * 6000 / BOSS.odds


def test_a_chest_beats_a_boss_when_both_come_up_and_a_boss_bites_like_any_fish():
    armed = f.cast_line(rod(), Lucky(1), T0, REG, armed=True)
    assert armed.chest and not armed.boss
    boss = f.cast_line(rod(), Lucky(1), T0, REG)
    assert boss.status(boss.bite_at + 1) == "bite"  # nothing gives it away
    boss.hook(boss.bite_at + 1)
    assert boss.status(boss.bite_at + 1) == "reeling"


async def test_a_boss_pays_a_pile_and_no_fish_and_only_once(db):
    user = await player()
    boss = f.cast_line(rod(), Lucky(1), T0, REG)
    boss.hook(boss.bite_at + 1)
    with pytest.raises(f.FishingError, match="isn't beaten"):
        await f.defeat_boss(user, boss, Lucky(2), REG)
    for arrow in list(boss.truth):
        boss.press(arrow, boss.bite_at + 2)
    with pytest.raises(f.FishingError, match="boss, not a fish"):
        await f.land(user, boss, REG, now=T0)  # a boss is not a fish
    before = user.purse
    won = await f.defeat_boss(user, boss, Lucky(2), REG)
    await user.refresh()
    assert won.name == boss.boss and won.bits == BOSS.bits_min and user.purse == before + won.bits
    assert won.items["coral_shard"] == BOSS.loot[0].min and won.items["sturgeon"] == 1  # a lucky boss pays everything
    assert await user.item_quantity("sturgeon") == 1
    assert await user.item_quantity(boss.fish.id) == won.items[boss.fish.id]  # no fish of its own: only what the loot gave
    skill = await user.skill("fishing")
    assert skill.stats.bosses_beaten == 1 and skill.stats.fish_caught == 0 and skill.xp >= BOSS.xp
    assert skill.stats.bosses == {boss.boss: 1} and skill.stats.caught == {}  # the Bestiary counts the boss by name, and no fish
    with pytest.raises(f.FishingError, match="already"):
        await f.defeat_boss(user, boss, Lucky(2), REG)


async def test_a_real_fish_is_not_a_boss(db):
    user = await player()
    with pytest.raises(f.FishingError, match="isn't a boss"):
        await f.defeat_boss(user, cast_of(), Lucky(1), REG)


async def test_beating_a_boss_on_the_screen_pays_and_losing_it_costs_only_the_boss(db, clock, monkeypatch):
    monkeypatch.setattr(fish_screen, "new_rng", lambda: Lucky(5))  # Lucky: this cast is a boss
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    assert cast.boss
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    assert "A bite!" in all_text(nav) and cast.boss not in all_text(nav)  # no spoilers
    await click(nav, inter, "Pull up the line")
    assert cast.boss in all_text(nav) and "15 arrows" in all_text(nav)
    await reel_in(nav, inter, cast)
    assert f"You beat {cast.boss}" in all_text(nav) and "Loot" in all_text(nav)
    assert nav.screen.id == "result" and nav.screen.origin.cast is None and (await user.skill("fishing")).stats.bosses_beaten == 1


async def test_slipping_on_a_boss_loses_it(db, clock, monkeypatch):
    monkeypatch.setattr(fish_screen, "new_rng", lambda: Lucky(5))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    wrong = "Right" if cast.next_arrow == f.LEFT else "Left"
    await click(nav, inter, wrong)
    assert "slipped off the hook" in all_text(nav) and (await user.skill("fishing")).stats.bosses_beaten == 0


# ---- waters -----------------------------------------------------------------------------------------------------------
WATERS = RULES.waters


def test_waters_open_in_order_and_every_fish_has_a_home():
    assert [w.min_level for w in WATERS] == sorted(w.min_level for w in WATERS) and WATERS[0].min_level == 1
    assert [w.wait_multiplier for w in WATERS] == sorted(w.wait_multiplier for w in WATERS)
    in_some_water = {fish_id for w in WATERS for fish_id in w.fish}
    assert in_some_water == {i.id for i in f.fish_pool(REG)}  # nothing is uncatchable, nothing is homeless


def test_the_first_water_is_open_to_everyone_and_levels_open_the_next():
    assert [w.id for w in f.unlocked_waters(1, RULES)] == ["pond"]
    assert [w.id for w in f.unlocked_waters(WATERS[2].min_level, RULES)] == ["pond", "river", "reef"]
    assert len(f.unlocked_waters(999, RULES)) == len(WATERS)
    assert f.require_water(1, "pond", RULES).id == "pond"
    with pytest.raises(f.FishingError, match="opens at fishing level"):
        f.require_water(1, "deep_sea", RULES)
    with pytest.raises(f.FishingError, match="no such water"):
        f.require_water(99, "moon", RULES)


def test_each_water_only_gives_its_own_fish_and_rarest_first():
    for water in WATERS:
        seen = {f.roll_fish(Random(i), REG, water).id for i in range(4000)}
        assert seen <= set(water.fish) and len(seen) >= 3, water.id
    deep = f.water_by_id(REG, "deep_sea")
    assert "cod" not in {f.roll_fish(Random(i), REG, deep).id for i in range(2000)}


def test_deeper_water_pays_more_per_cast_and_takes_longer_to_bite():
    def worth(water, n=30_000):
        rng = Random(3)
        return sum(f.roll_fish(rng, REG, water).sell_price for _ in range(n)) / n

    averages = [worth(w) for w in WATERS]
    assert averages == sorted(averages) and averages[-1] > 3 * averages[0], averages
    assert 2_000 < averages[0] < 5_000  # the starting water is a gentle start
    def mean_wait(water):
        return sum(f.cast_line(rod(), Random(i), 0, REG, water=water).bite_at for i in range(600)) / 600

    assert mean_wait(WATERS[-1]) / mean_wait(WATERS[0]) == pytest.approx(WATERS[-1].wait_multiplier, rel=0.06)


def test_quests_and_community_goals_only_ask_for_fish_from_the_first_waters():
    pool = {i.id for i in f.quest_pool(REG)}
    first = {fish_id for w in WATERS if w.min_level <= RULES.quests.min_level for fish_id in w.fish}
    assert pool == first and "marlin" not in pool and "tuna" not in pool
    for slot in (*RULES.quests.daily, *RULES.quests.weekly, *[s for s in RULES.community.monthly if s.kind == "fish"]):
        assert any(REG.item(i).rarity == slot.rarity for i in pool), slot
    from cococap.services import fishing_community as c

    for period in range(400, 460):
        assert all(q[0].id in pool for kind in ("daily", "weekly") for q in f._chosen(kind, 1, period, REG))
        assert next(g for g in c.goals(period, REG) if g.slot.kind == "fish").fish.id in pool


async def test_the_page_defaults_to_your_best_water_lets_you_pick_and_hints_at_the_next(db, clock, monkeypatch):
    seen = []

    def spy(rng, reg=None, water=None, rare_luck=0.0):
        seen.append(water.id)
        return REG.item("cod")

    monkeypatch.setattr(f, "roll_fish", spy)
    user, nav, inter = await open_fishing()
    assert "Quiet Pond" in all_text(nav) and "Winding River opens at fishing level 3" in all_text(nav)
    assert not [s for s in nav.walk_children() if isinstance(s, __import__("discord").ui.Select)]  # nothing to choose yet
    await user.add_xp("fishing", User.level_to_xp(WATERS[1].min_level) + 1)
    nav, inter = await hub("fish")
    assert "Winding River" in all_text(nav)  # a new water is where you head next
    await click(nav, inter, "Cast")
    assert seen == ["river"]
    await click(nav, inter, "Cancel cast")
    from tests.test_hub import choose, select_named

    await choose(nav, inter, select_named(nav, "Where to fish"), "pond")
    assert "Quiet Pond" in all_text(nav)
    await click(nav, inter, "Cast")
    assert seen == ["river", "pond"]


async def test_a_locked_water_cannot_be_cast_into_even_with_a_stale_menu(db):
    user, nav, inter = await open_fishing()
    nav.screen.water = "deep_sea"  # (e.g. picked, then the level somehow dropped)
    with pytest.raises(f.FishingError, match="opens at fishing level 15"):
        await click(nav, inter, "Cast")
    assert nav.screen.cast is None


async def test_the_records_page_is_one_click_from_the_fishing_page_and_shows_server_records_for_every_fish(db):
    from cococap.services import community

    await community.update(f.RECORDS_KEY, {}, lambda r: r.update({"tuna": {"size": 188.5, "uid": 7, "name": "Ahna"}}))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Records")  # at level 1, straight from the main page
    assert nav.screen.id == "fishrecords"
    page = all_text(nav)
    assert "Tuna" in page and "188.5 cm (Ahna)" in page and "you: not caught yet" in page  # someone's record, not hers yet
    assert "fish nobody has caught yet" in page and "???" not in page  # fish nobody has caught stay a mystery (one line, not one each)
    await click(nav, inter, "Back to fishing")
    assert nav.screen.id == "fish"


# ---- a reel with more to it: breaks and mystery arrows --------------------------------------------------------------------
RL = RULES.reel


def fish_of(rarity, tell=None):
    return next(i for i in f.fish_pool(REG) if i.rarity == rarity and (tell is None or (i.reel and i.reel.tell == tell)))


def test_easy_fish_are_plain_arrows_and_tougher_ones_make_you_stop_and_reel():
    shown, actual = f.build_reel(fish_of(1), RULES, Random(1))
    assert f.REEL not in shown and f.MYSTERY not in shown and len(shown) == RL.base_length + 1
    for rarity in range(RL.break_from_rarity, 8):
        shown, actual = f.build_reel(fish_of(rarity), RULES, Random(2))
        arrows = RL.base_length + rarity
        assert shown.count(f.REEL) == arrows // RL.arrows_per_break >= 1 and len(shown) == arrows + shown.count(f.REEL)
        assert shown[0] != f.REEL and shown[-1] != f.REEL  # you start and finish on an arrow
        assert not any(a == b == f.REEL for a, b in zip(shown, shown[1:], strict=False))  # never two Reels in a row


def test_only_the_toughest_fish_hide_arrows_and_more_of_them_the_rarer_they_are():
    assert RL.mystery_from_rarity == 4
    for rarity in range(1, 4):
        assert f.MYSTERY not in f.build_reel(fish_of(rarity), RULES, Random(3))[0]
    for rarity in range(4, 8):
        shown, actual = f.build_reel(fish_of(rarity), RULES, Random(3))
        fish = fish_of(rarity)
        most = rarity - RL.mystery_from_rarity + 1
        assert shown.count(f.MYSTERY) == (min(most, RL.max_random_mysteries) if fish.reel.tell == "random" else most)
        assert shown.index(f.MYSTERY) > 0 and next(a for a, t in zip(shown, actual, strict=True) if a == f.MYSTERY) is not None
        assert all(t in (f.LEFT, f.RIGHT, f.REEL) for t in actual)  # what is really wanted is never a ❓
        assert [s for s in shown if s != f.MYSTERY] == [t for s, t in zip(shown, actual, strict=True) if s != f.MYSTERY]


def test_reels_really_vary_from_cast_to_cast():
    shapes = {tuple(f.build_reel(fish_of(5), RULES, Random(i))[0]) for i in range(60)}
    assert len(shapes) > 50
    layouts = {tuple(s == f.REEL for s in f.build_reel(fish_of(6), RULES, Random(i))[0]) for i in range(60)}
    assert len(layouts) > 10  # the breaks land in different places too


def test_every_super_rare_or_better_fish_has_a_tell_and_both_kinds_exist():
    tells = {i.id: i.reel.tell for i in f.fish_pool(REG) if i.rarity >= RL.mystery_from_rarity}
    assert all(i.reel is not None for i in f.fish_pool(REG) if i.rarity >= RL.mystery_from_rarity)
    assert {"left", "right", "same", "opposite", "random"} == set(tells.values())
    assert all(i.reel is None for i in f.fish_pool(REG) if i.rarity < RL.mystery_from_rarity)


@pytest.mark.parametrize("tell", ["left", "right", "same", "opposite"])
def test_a_learnable_tell_always_does_the_same_thing(tell):
    fish = next(i for i in f.fish_pool(REG) if i.reel and i.reel.tell == tell)
    for seed in range(80):
        shown, actual = f.build_reel(fish, RULES, Random(seed))
        arrows = [a for a in actual if a != f.REEL]
        shown_arrows = [a for a in shown if a != f.REEL]
        for i, s in enumerate(shown_arrows):
            if s != f.MYSTERY:
                continue
            before = arrows[i - 1]
            expected = {"left": f.LEFT, "right": f.RIGHT, "same": before, "opposite": f.RIGHT if before == f.LEFT else f.LEFT}[tell]
            assert arrows[i] == expected


def test_a_random_tell_really_is_a_coin_flip_you_cannot_learn():
    fish = next(i for i in f.fish_pool(REG) if i.reel and i.reel.tell == "random")
    results = {}
    for seed in range(400):
        shown, actual = f.build_reel(fish, RULES, Random(seed))
        arrows = [a for a in actual if a != f.REEL]
        for i, s in enumerate([a for a in shown if a != f.REEL]):
            if s == f.MYSTERY:
                results.setdefault(arrows[i - 1], []).append(arrows[i])
    for before, truths in results.items():
        assert 0.35 < truths.count(f.LEFT) / len(truths) < 0.65, before  # either arrow, whatever came before


def test_a_player_can_work_out_every_learnable_tell_from_a_few_catches():
    """The field notes are enough: after a handful of ❓s exactly one rule fits what was seen."""
    rules = {"left": lambda b: f.LEFT, "right": lambda b: f.RIGHT, "same": lambda b: b,
             "opposite": lambda b: f.RIGHT if b == f.LEFT else f.LEFT}
    for tell in ("left", "right", "same", "opposite"):
        fish = next(i for i in f.fish_pool(REG) if i.reel and i.reel.tell == tell)
        notes = []
        for seed in range(6):  # six casts
            cast = f.cast_line(rod(), Random(seed), 0, REG)
            shown, actual = f.build_reel(fish, RULES, Random(seed))
            arrows = [a for a in actual if a != f.REEL]
            for i, s in enumerate([a for a in shown if a != f.REEL]):
                if s == f.MYSTERY:
                    notes.append(f"{arrows[i - 1]}>{arrows[i]}")
            assert cast
        fits = [name for name, rule in rules.items() if all(rule(n[0]) == n[2] for n in notes)]
        assert fits == [tell], (tell, notes, fits)


def test_a_boss_has_breaks_but_no_hidden_arrows():
    boss = f.cast_line(rod(), Lucky(1), T0, REG)
    assert boss.boss and f.MYSTERY not in boss.pattern and boss.pattern.count(f.REEL) == BOSS.length // RL.arrows_per_break


# ---- pressing the new steps -------------------------------------------------------------------------------------------------
def tricky_cast(pattern, truth, slips=0):
    cast = cast_of(pattern=pattern, slips=slips)
    cast.truth = truth
    return cast


def test_a_reel_step_wants_the_reel_button_and_an_arrow_step_does_not_accept_it():
    cast = tricky_cast([f.LEFT, f.REEL, f.RIGHT], [f.LEFT, f.REEL, f.RIGHT])
    assert cast.press(f.LEFT, T0 + 11) == "ok"
    assert cast.press(f.LEFT, T0 + 20) == "escaped"  # an arrow where a Reel was wanted
    fresh = tricky_cast([f.LEFT, f.REEL, f.RIGHT], [f.LEFT, f.REEL, f.RIGHT])
    fresh.press(f.LEFT, T0 + 11)
    assert fresh.press(f.REEL, T0 + 12) == "ok" and fresh.press(f.RIGHT, T0 + 13) == "landed"
    wrong = tricky_cast([f.LEFT, f.RIGHT], [f.LEFT, f.RIGHT])
    wrong.press(f.LEFT, T0 + 11)
    assert wrong.press(f.REEL, T0 + 20) == "escaped"  # Reel where an arrow was wanted


def test_a_mystery_arrow_is_secretly_an_arrow_and_pressing_it_teaches_you_what_it_was():
    cast = tricky_cast([f.LEFT, f.MYSTERY, f.RIGHT], [f.LEFT, f.RIGHT, f.RIGHT])
    assert cast.next_arrow == f.LEFT
    cast.press(f.LEFT, T0 + 11)
    assert cast.next_arrow == f.RIGHT and cast.pattern[1] == f.MYSTERY  # shown as ❓, wanted as ►
    assert cast.press(f.RIGHT, T0 + 12) == "ok" and cast.reveals == [(f.LEFT, f.RIGHT)]
    assert cast.press(f.RIGHT, T0 + 13) == "landed"


def test_a_wrong_guess_at_a_mystery_still_shows_you_the_answer_but_only_once():
    cast = tricky_cast([f.LEFT, f.MYSTERY, f.RIGHT], [f.LEFT, f.RIGHT, f.RIGHT], slips=2)
    cast.press(f.LEFT, T0 + 11)
    assert cast.press(f.LEFT, T0 + 20) == "slip" and cast.reveals == [(f.LEFT, f.RIGHT)]  # wrong, but now you know
    assert cast.press(f.LEFT, T0 + 30) == "slip" and len(cast.reveals) == 1  # guessing again learns nothing new
    assert cast.press(f.RIGHT, T0 + 31) == "ok"


def test_a_double_press_on_a_mystery_does_not_count_as_learning_twice():
    cast = tricky_cast([f.RIGHT, f.MYSTERY, f.LEFT], [f.RIGHT, f.RIGHT, f.LEFT])
    cast.echo_window = 2.0
    cast.press(f.RIGHT, T0 + 11)
    assert cast.press(f.RIGHT, T0 + 11.5) == "ok" and len(cast.reveals) == 1  # this one is the real answer to the ❓
    assert cast.press(f.RIGHT, T0 + 11.8) == "echo" and len(cast.reveals) == 1


async def test_landing_a_fish_writes_what_its_mystery_was_in_the_field_notes(db):
    user = await player()
    cast = tricky_cast([f.LEFT, f.MYSTERY, f.RIGHT], [f.LEFT, f.RIGHT, f.RIGHT])
    cast.fish = REG.item("pufferfish")
    for step in cast.truth:
        cast.press(step, T0 + 11)
    got = await f.land(user, cast, REG, now=T0)
    assert got.reveals == ((f.LEFT, f.RIGHT),)
    assert (await user.skill("fishing")).notes == {"pufferfish": [f"{f.LEFT}>{f.RIGHT}"]}


async def test_a_fish_that_got_away_still_teaches_you_and_the_notes_stay_short(db):
    user = await player()
    cast = tricky_cast([f.LEFT, f.MYSTERY], [f.LEFT, f.LEFT])
    cast.fish = REG.item("moray_eel")
    cast.press(f.LEFT, T0 + 11)
    assert cast.press(f.RIGHT, T0 + 12) == "escaped"
    await f.note_tells(user, cast)
    assert (await user.skill("fishing")).notes == {"moray_eel": [f"{f.LEFT}>{f.LEFT}"]}
    for i in range(30):
        again = tricky_cast([f.LEFT, f.MYSTERY], [f.LEFT, f.RIGHT])
        again.fish = REG.item("moray_eel")
        again.press(f.LEFT, T0 + 11)
        again.press(f.RIGHT, T0 + 12)
        await f.note_tells(user, again)
    assert len((await user.skill("fishing")).notes["moray_eel"]) == f.NOTES_KEPT


def test_field_notes_read_clearly():
    assert f.read_notes([f"{f.LEFT}>{f.RIGHT}", f"{f.LEFT}>{f.RIGHT}", f"{f.RIGHT}>{f.RIGHT}"]) == "after ◄ → ► ×2, after ► → ►"


async def test_the_screen_has_a_reel_button_shows_breaks_and_mysteries_and_the_result_says_what_the_mystery_was(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("moray_eel"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    assert f.MYSTERY in cast.pattern and f.REEL in cast.pattern
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    page = all_text(nav)
    assert find_button(nav, "Reel") and f.MYSTERY in page and f.REEL in page and "press **Reel**" in page.replace("**Reel**", "**Reel**")
    await reel_in(nav, inter, cast)
    assert nav.screen.id == "result" and "The ❓ was" in all_text(nav) and "field notes" in all_text(nav)
    assert (await user.skill("fishing")).notes["moray_eel"]
    nav2, inter2 = await hub("fish")
    await click(nav2, inter2, "Field notes")  # a button on the fishing page itself
    assert nav2.screen.id == "fishnotes" and "Moray Eel: after" in all_text(nav2)


async def test_losing_at_a_mystery_still_shows_it_on_the_result_page(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("moray_eel"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    while cast.progress < len(cast.pattern) and cast.pattern[cast.progress] != f.MYSTERY and not cast.escaped:
        await click(nav, inter, {f.LEFT: "Left", f.RIGHT: "Right", f.REEL: "Reel"}[cast.wanted(cast.progress)])
    wrong = "Right" if cast.wanted(cast.progress) == f.LEFT else "Left"
    await click(nav, inter, wrong)
    assert nav.screen.id == "result" and "slipped off" in all_text(nav) and "The ❓ was" in all_text(nav)
    assert (await user.skill("fishing")).notes["moray_eel"]


def test_a_coin_flip_fish_never_hides_more_arrows_than_you_can_stand():
    for fish in f.fish_pool(REG):
        if fish.reel and fish.reel.tell == "random":
            shown, _ = f.build_reel(fish, RULES, Random(1))
            assert shown.count(f.MYSTERY) <= RL.max_random_mysteries


async def test_a_chests_xp_grows_with_your_level_but_never_drops_below_the_floor(db):
    async def open_one(user_id, level):
        user = await player(user_id)
        if level > 1:
            await user.add_xp("fishing", User.level_to_xp(level) + 1)
        chest = await armed_chest(user)
        before = (await user.skill("fishing")).xp
        got = await f.open_chest(user, chest, "4815", Lucky(3), chest.bite_at + 2, REG)
        return got.xp, (await user.skill("fishing")).xp - before, before

    low, low_gain, _ = await open_one(1, 1)
    mid, mid_gain, mid_before = await open_one(2, 10)
    high, high_gain, high_before = await open_one(3, 30)
    assert low == low_gain >= T.xp  # a new angler still gets the floor
    assert mid == mid_gain and high == high_gain and low < mid < high
    _, needed = User.xp_for_next_level(high_before)
    assert high == round(needed * T.xp_level_fraction)  # a quarter of the level you are on
    assert high > 5 * T.xp  # and it is worth something at level 30
    assert mid_before < high_before


# ---- surprises in the reel: Reel steps that turn up, a window of steps, and the fish you can see ---------------------------
def reel_cast(pattern, decoys=None, truth=None, modifiers=(), progress=0, boss=""):
    cast = cast_of(pattern=pattern, hooked=True)
    cast.truth = truth or list(pattern)
    cast.decoys = decoys or []
    cast.modifiers, cast.progress, cast.boss = list(modifiers), progress, boss
    return cast


def test_a_reel_step_looks_like_an_ordinary_arrow_until_you_reach_it():
    cast = reel_cast([f.LEFT, f.REEL, f.RIGHT, f.REEL], decoys=["", f.RIGHT, "", f.LEFT])
    assert [cast.display(i) for i in range(4)] == [f.LEFT, f.RIGHT, f.RIGHT, f.LEFT]  # no sign of a Reel anywhere yet
    cast.press(f.LEFT, T0 + 11)
    assert cast.display(1) == f.REEL  # it turns into the Reel symbol the moment you get to it
    assert cast.display(3) == f.LEFT  # the later one is still hidden
    cast.press(f.REEL, T0 + 12)
    cast.press(f.RIGHT, T0 + 13)
    assert cast.display(3) == f.REEL
    assert cast.display(1) == f.REEL  # and what you have done stays as it was


def test_every_reel_in_a_real_cast_has_a_decoy_arrow_and_pressing_the_decoy_is_wrong():
    cast = f.cast_line(rod(), Random(11), 0, REG, water=f.water_by_id(REG, "deep_sea"))
    reels = [i for i, step in enumerate(cast.pattern) if step == f.REEL]
    assert reels and all(cast.decoys[i] in (f.LEFT, f.RIGHT) for i in reels)
    assert all(cast.display(i) != f.REEL for i in reels if i > cast.progress)
    cast.hook(cast.bite_at + 1)
    for index, step in enumerate(cast.truth):
        if step == f.REEL:  # arrive at a reel: it has turned, and an arrow is now the wrong thing to press
            assert cast.display(index) == f.REEL
            assert cast.press(f.LEFT, cast.bite_at + 20) in ("escaped", "slip")  # (well after the last press, so it isn't an echo)
            return
        cast.press(step, cast.bite_at + 2)


def test_you_only_see_the_next_few_steps_and_how_many_more_there_are():
    cast = reel_cast([f.LEFT, f.RIGHT] * 6)
    line = fish_screen.pattern_line(cast, RULES)
    assert line.count(f.LEFT) + line.count(f.RIGHT) == RL.window and "… +7" in line and line.startswith(f"**{f.LEFT}**")
    cast.progress = 9
    line = fish_screen.pattern_line(cast, RULES)
    assert "✅" * 9 in line and "✅×" not in line and "… +" not in line and line.count(f.LEFT) + line.count(f.RIGHT) == 3  # the end is in sight


def test_a_fog_shows_only_two_steps_and_a_reverse_boss_is_read_from_the_right():
    foggy = reel_cast([f.LEFT, f.RIGHT] * 6, modifiers=["fog"])
    line = fish_screen.pattern_line(foggy, RULES)
    assert line.count(f.LEFT) + line.count(f.RIGHT) == RL.fog_window
    backwards = reel_cast([f.LEFT, f.RIGHT, f.RIGHT, f.LEFT, f.RIGHT, f.LEFT, f.LEFT], modifiers=["reverse"])
    line = fish_screen.pattern_line(backwards, RULES)
    assert line.rstrip().endswith(f"**{f.LEFT}**") and line.startswith("… +2")  # the NEXT step sits at the right end
    assert [c for c in line if c in (f.LEFT, f.RIGHT)] == [f.RIGHT, f.LEFT, f.RIGHT, f.RIGHT, f.LEFT]  # (5 steps, last one to press on the right)


async def test_the_page_names_the_fish_on_the_line_so_you_can_use_what_you_have_learned(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("moray_eel"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    assert "Moray Eel" not in all_text(nav)  # still a mystery at the bite
    await click(nav, inter, "Pull up the line")
    page = all_text(nav)
    assert "Moray Eel" in page and "Super Rare" in page and "field notes" in page


# ---- bosses with a twist ----------------------------------------------------------------------------------------------------------
def boss_with(modifier):
    entry = next(b for b in BOSS.bosses if modifier in b.modifiers)
    fixed = Lucky(1)
    fixed.choice = lambda seq: entry if seq is BOSS.bosses or (list(seq) == list(BOSS.bosses)) else seq[0]
    return f.cast_line(rod(), fixed, T0, REG), entry


def test_every_boss_has_a_twist_and_every_twist_is_explained_and_used():
    assert all(b.modifiers for b in BOSS.bosses) and len({b.name for b in BOSS.bosses}) == len(BOSS.bosses)
    used = {m for b in BOSS.bosses for m in b.modifiers}
    assert used == {"mirror", "reverse", "shuffle", "fog", "wild"} == set(BOSS.modifier_text)
    assert len({tuple(b.modifiers) for b in BOSS.bosses}) == len(BOSS.bosses)  # no two bosses fight the same


def test_a_mirror_boss_wants_the_opposite_of_every_arrow_but_not_of_reels():
    cast, entry = boss_with("mirror")
    assert "mirror" in cast.modifiers and cast.boss == entry.name
    for shown, wanted in zip(cast.pattern, cast.truth, strict=True):
        if shown == f.REEL:
            assert wanted == f.REEL
        else:
            assert wanted == (f.RIGHT if shown == f.LEFT else f.LEFT)
    cast.hook(cast.bite_at + 1)
    first = cast.pattern[0]
    assert cast.press(first, cast.bite_at + 2) == "escaped"  # pressing what it SHOWS is the mistake
    fresh, _ = boss_with("mirror")
    fresh.hook(fresh.bite_at + 1)
    assert fresh.press(f.RIGHT if fresh.pattern[0] == f.LEFT else f.LEFT, fresh.bite_at + 2) == "ok"


def test_a_wild_boss_hides_coin_flip_arrows_and_the_others_do_not():
    wild, _ = boss_with("wild")
    assert wild.pattern.count(f.MYSTERY) == BOSS.wild_mysteries
    plain, _ = boss_with("fog")
    assert f.MYSTERY not in plain.pattern and "wild" not in plain.modifiers


async def test_a_boss_page_lists_its_twists_and_a_mirror_boss_can_be_beaten_by_pressing_the_opposite(db, clock, monkeypatch):
    mirror = next(b for b in BOSS.bosses if b.modifiers == ["mirror"])

    class Rigged(Lucky):
        def choice(self, seq):
            return mirror if list(seq) == list(BOSS.bosses) else super().choice(seq)

    monkeypatch.setattr(fish_screen, "new_rng", lambda: Rigged(5))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    assert mirror.name in all_text(nav) and "Mirror" in all_text(nav) and "OPPOSITE" in all_text(nav)
    await reel_in(nav, inter, cast)
    assert nav.screen.id == "result" and f"You beat {mirror.name}" in all_text(nav)


async def test_a_shuffle_boss_moves_the_buttons_around_and_a_normal_fish_never_does(db, clock, monkeypatch):
    shuffle = next(b for b in BOSS.bosses if b.modifiers == ["shuffle"])

    class Rigged(Lucky):
        real = Random(3)

        def choice(self, seq):
            return shuffle if list(seq) == list(BOSS.bosses) else super().choice(seq)

        def shuffle(self, items):  # (the boss comes from the lucky dice; the shuffling itself needs real randomness)
            self.real.shuffle(items)

    monkeypatch.setattr(fish_screen, "new_rng", lambda: Rigged(5))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    orders = set()
    for _ in range(40):
        await nav.screen.nav.refresh(inter)
        orders.add(tuple(b.label for b in buttons(nav) if b.label in ("Left", "Right", "Reel")))
    assert len(orders) > 1 and all(set(o) == {"Left", "Right", "Reel"} for o in orders)
    plain = fish_screen.reel_buttons(reel_cast([f.LEFT]), Random(1), lambda a: None, __import__("discord").ButtonStyle.primary)
    assert [b.label for b in plain] == ["Left", "Right", "Reel"]


# ---- the field notes page -----------------------------------------------------------------------------------------------------------------
def test_the_notes_add_up_to_a_rule_once_you_have_seen_enough():
    assert f.notes_verdict(["◄>►", "►>►"]) is None  # too few to say
    assert "always ►" in f.notes_verdict(["◄>►", "►>►", "◄>►"])
    assert "always ◄" in f.notes_verdict(["◄>◄", "►>◄", "◄>◄"])
    assert "same arrow" in f.notes_verdict(["◄>◄", "►>►", "◄>◄"])
    assert "opposite" in f.notes_verdict(["◄>►", "►>◄", "◄>►"])
    assert "luck" in f.notes_verdict(["◄>►", "◄>◄", "►>►", "►>◄"])  # no rule explains it
    assert "not sure" in f.notes_verdict(["◄>►", "◄>►", "◄>►"])  # "always ►" and "the opposite" both fit


async def test_the_field_notes_page_is_a_button_on_the_fishing_page_even_with_nothing_in_it_yet(db):
    nav, inter = await hub("fish")
    await click(nav, inter, "Field notes")
    assert nav.screen.id == "fishnotes"
    page = all_text(nav)
    assert "Field notes" in page and "not caught yet" in page and "pure luck" in page  # it explains itself and shows what is still unknown
    await click(nav, inter, "Back to fishing")
    assert nav.screen.id == "fish"
    nav2, inter2 = await hub("fishrecords")
    await click(nav2, inter2, "Field notes")
    assert nav2.screen.id == "fishnotes"


async def test_the_page_shows_what_a_caught_fish_has_taught_you_and_what_it_adds_up_to(db):
    user = await User.get(1)
    fish = next(i for i in f.fish_pool(REG) if i.rarity >= RL.mystery_from_rarity and i.reel and i.reel.tell == "opposite")
    await user.update_skill("fishing", lambda s: (s.records.update({fish.id: 30.0}), s.notes.update({fish.id: ["◄>►", "►>◄"]})))
    nav, _ = await hub("fishnotes")
    assert fish.name in all_text(nav) and "after ◄ → ►" in all_text(nav) and "1 more" in all_text(nav)
    await user.update_skill("fishing", lambda s: s.notes[fish.id].append("◄>►"))
    nav, _ = await hub("fishnotes")
    assert "opposite of the arrow before it" in all_text(nav)


# ---- a better rod is a noticeably faster rod ----------------------------------------------------------------------------------------------------
def test_each_rod_upgrade_cuts_the_wait_by_something_you_can_feel():
    starter, reinforced, master = (f.typical_wait(REG.item(r).tool.power, RULES) for r in ("starter_rod", "reinforced_rod", "masterwork_rod"))
    assert reinforced < 0.7 * starter and master < 0.65 * reinforced  # each step is a third or more off the wait
    assert master < 0.4 * starter
    assert f.typical_wait(100, RULES) >= RULES.bite.wait_min * RULES.bite.min_wait_factor  # (it still never hits zero)
    assert f.typical_wait(3, RULES, bite_speed=0.2) < f.typical_wait(3, RULES)  # a Lure on top


async def test_the_fishing_page_tells_you_how_long_your_rod_takes_to_bite(db):
    user = await User.get(1)
    inst = await user.give_instance("reinforced_rod")
    await equip(user, "fishing", inst.id)
    nav, _ = await hub("fish")
    expected = f.typical_wait(REG.item("reinforced_rod").tool.power, RULES)
    assert f"bites in ~**{expected:.0f}s**" in all_text(nav)


# ---- xp is for the catch, not the fish or the rod ------------------------------------------------------------------------
async def test_every_landed_fish_pays_the_same_xp_whatever_its_rarity(db):
    paid = {}
    for fish_id in ("cod", "salmon", "pike"):  # rarities 1, 3, 4
        user = await player()
        cast = cast_of(fish_id, slips=0)
        for arrow in cast.pattern:
            cast.press(arrow, T0 + 11)
        paid[fish_id] = (await f.land(user, cast, REG)).xp
    assert len(set(paid.values())) == 1 and paid["cod"] == RULES.xp_per_catch


async def test_the_water_sets_the_xp_and_a_better_rod_does_not_change_it(db):
    deep = f.water_by_id(REG, "deep_sea")
    pond = f.water_by_id(REG, "pond")
    assert deep.xp > pond.xp
    results = {}
    for power in (3, 120):
        stats = EffectiveStats(power=power, requirement=0)
        cast = f.cast_line(stats, Random(1), T0, REG, water=deep)
        assert cast.xp == deep.xp
        results[power] = cast.xp
    assert results[3] == results[120]


def test_a_fishing_boss_pays_a_haul_of_the_fish_tools_are_upgraded_with():
    loot = {row.item: row for row in REG.fishing.boss.loot}
    for fish in ("salmon", "trout"):
        assert loot[fish].chance == 1.0 and loot[fish].max >= 6  # a sure haul, like the mining vault
    upgrade_fish = {i for t in REG.items.values() if t.tool and t.tool.upgrade for i in t.tool.upgrade.items if REG.item(i).category == "fish"}
    assert {"salmon", "trout", "pufferfish", "tuna"} <= upgrade_fish and {"salmon", "trout", "pufferfish", "tuna"} <= set(loot)


# ---- a clean reel pays, and a cast tells you how long to wait ---------------------------------------------------------------------------
async def land_with(user, slips_left, fish_id="cod", extra=0):
    cast = cast_of(fish_id, slips=slips_left)
    cast.extra_fish = extra
    for arrow in cast.pattern:
        cast.press(arrow, T0 + 11)
    return await f.land(user, cast, REG)


async def test_every_slack_you_did_not_need_pays_a_bonus(db):
    user = await player(1)
    start = (await User.get(1)).purse
    none = await land_with(user, 0)
    assert none.slack_bits == 0 and none.slack_left == 0
    two = await land_with(user, 2)
    assert two.slack_left == 2 and two.slack_bits == round(REG.item("cod").sell_price * RULES.reel.slack_bonus * 2)
    four = await land_with(user, 4)
    assert four.slack_bits == 2 * two.slack_bits  # it adds up: the more slack to spare, the cleaner the reel
    await user.refresh()
    assert user.purse == start + two.slack_bits + four.slack_bits


async def test_a_slack_bonus_counts_the_extra_fish_a_good_rod_hauls_in(db):
    user = await player(1)
    plain = await land_with(user, 1)
    hauled = await land_with(user, 1, extra=2)
    assert hauled.slack_bits == 3 * plain.slack_bits


async def test_slack_you_used_is_not_paid_for(db):
    user = await player(1)
    cast = cast_of("cod", slips=2)
    steps = list(cast.pattern)
    assert cast.press(f.RIGHT if steps[0] == f.LEFT else f.LEFT, T0 + 11) == "slip" and cast.slips_left == 1
    for step in steps:
        cast.press(step, T0 + 12)
    caught = await f.land(user, cast, REG)
    assert caught.slack_left == 1 and caught.slack_bits == round(REG.item("cod").sell_price * RULES.reel.slack_bonus)


async def test_a_boss_reel_with_slack_left_pays_a_bonus_on_its_bits(db):
    user = await player(1)
    for left, expect_bonus in ((0, False), (3, True)):
        boss = cast_of("cod", slips=left)
        boss.boss, boss.modifiers = "Old Whiskers", []
        for arrow in boss.pattern:
            boss.press(arrow, T0 + 11)
        won = await f.defeat_boss(user, boss, Random(1), REG)
        assert (won.slack_bits > 0) == expect_bonus and won.slack_left == left
        if expect_bonus:
            assert won.slack_bits == round(won.bits * RULES.reel.slack_bonus * 3)


async def test_the_catch_page_says_it_was_a_clean_reel_and_the_reel_page_says_slack_pays(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
    user, nav, inter = await open_fishing(power_item="reinforced_rod")  # power 8: forgives a wrong arrow
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    assert "each one unused pays a bonus" in all_text(nav)
    await reel_in(nav, inter, cast)
    assert "Clean reel" in all_text(nav) and "slack unused" in all_text(nav)


async def test_casting_tells_you_how_long_the_bite_should_take_and_a_better_rod_shortens_it(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))
    waits = {}
    for uid, item in ((1, "starter_rod"), (2, "masterwork_rod")):
        user, nav, inter = await open_fishing(uid, item)
        await click(nav, inter, "Cast")
        line = next(l for l in all_text(nav).split("\n") if "A bite in about" in l)
        waits[item] = (int(line.split("**")[1].rstrip("s")), "starter rod" in line)
    assert waits["starter_rod"][1] is False  # (a starter rod's own line does not compare itself with itself)
    assert waits["masterwork_rod"][0] < waits["starter_rod"][0] and waits["masterwork_rod"][1] is True
    starter_wait = round(f.typical_wait(REG.item("starter_rod").tool.power, RULES) * f.water_by_id(REG, nav.screen.water).wait_multiplier)
    assert waits["starter_rod"][0] == starter_wait


# ---- rod abilities: the Angler's Auto-Reel and the Treasure Hunter's Bycatch -----------------------------------------------------------
def test_auto_reel_presses_the_first_plain_arrows_when_you_pull_up_the_line():
    cast = cast_of("cod", pattern=[f.LEFT, f.RIGHT, f.LEFT, f.RIGHT, f.LEFT], hooked=False)
    cast.auto_steps = 2
    cast.hook(T0 + 11)
    assert cast.hooked and cast.progress == 2 and cast.next_arrow == f.LEFT  # the first two are done for you


def test_auto_reel_stops_at_a_reel_break_a_mystery_and_the_last_step_and_never_lands_the_fish_by_itself():
    cast = cast_of("cod", pattern=[f.LEFT, f.REEL, f.LEFT], hooked=False)
    cast.auto_steps = 3
    cast.hook(T0 + 11)
    assert cast.progress == 1  # a Reel break is yours to press
    short = cast_of("cod", pattern=[f.LEFT, f.RIGHT], hooked=False)
    short.auto_steps = 9
    short.hook(T0 + 11)
    assert short.progress == 1 and short.status(T0 + 12) == "reeling"  # always leaves you the last press
    mystery = cast_of("cod", pattern=[f.LEFT, f.MYSTERY, f.LEFT, f.RIGHT], hooked=False)
    mystery.truth = [f.LEFT, f.RIGHT, f.LEFT, f.RIGHT]
    mystery.auto_steps = 3
    mystery.hook(T0 + 11)
    assert mystery.progress == 1


def test_without_auto_reel_you_start_at_the_first_arrow():
    cast = cast_of("cod", hooked=False)
    cast.hook(T0 + 11)
    assert cast.progress == 0


def test_a_cast_carries_the_rods_abilities():
    from cococap.models.instance import ItemInstance
    from cococap.services.equipment import effective_stats

    for template, field, value in (("tidecaller_rod", "auto_steps", 1), ("abyssal_rod", "auto_steps", 2), ("lantern_rod", "bycatch", 0.10)):
        stats = effective_stats(ItemInstance(id=1, owner_id=1, template_id=template, enchants={}, rolled={}), REG)
        cast = f.cast_line(stats, Random(1), T0, REG)
        assert getattr(cast, field) == pytest.approx(value), template


async def test_bycatch_brings_a_second_different_fish_and_counts_it(db):
    user = await player(1)
    cast = cast_of("cod", slips=0)
    cast.bycatch, cast.water = 1.0, next(w for w in RULES.waters if w.id == "river")
    for arrow in cast.pattern:
        cast.press(arrow, T0 + 11)
    caught = await f.land(user, cast, REG, rng=Random(3))
    assert caught.bycatch is not None and caught.bycatch.id != "cod"
    assert await user.item_quantity(caught.bycatch.id) == 1 and (await user.skill("fishing")).stats.caught[caught.bycatch.id] == 1
    none = cast_of("cod")
    none.bycatch = 0.0
    for arrow in none.pattern:
        none.press(arrow, T0 + 11)
    assert (await f.land(user, none, REG, rng=Random(3))).bycatch is None


async def test_the_catch_page_mentions_the_bycatch(db, clock, monkeypatch):
    fish = iter([REG.item("cod"), REG.item("bass")])  # the cast brings a cod; the bycatch roll brings a bass
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: next(fish))
    user, nav, inter = await open_fishing(power_item="lantern_rod")
    await click(nav, inter, "Cast")
    cast = nav.screen.cast
    cast.bycatch = 1.0
    clock[0] = cast.bite_at + 1
    await nav.screen.nav.refresh(inter)
    await click(nav, inter, "Pull up the line")
    await reel_in(nav, inter, cast)
    assert "Bycatch" in all_text(nav) and await user.item_quantity("bass") == 1


def test_the_rod_roads_data_each_road_has_its_own_ability_and_fish():
    angler = ["tidecaller_rod", "moonlit_rod", "leviathan_rod", "abyssal_rod", "poseidon_rod"]
    treasure = ["lantern_rod", "siren_rod", "trident_rod", "kraken_rod", "trophy_rod"]
    steps = [REG.item(a).tool.stats["auto_reel"] for a in angler]
    chances = [REG.item(t).tool.stats["bycatch"] for t in treasure]
    assert steps == sorted(steps) and chances == sorted(chances) and steps[-1] > steps[0]
    for a, t in zip(angler, treasure, strict=True):
        assert REG.item(a).tool.ability == "auto_reel" and REG.item(t).tool.ability == "bycatch"


async def test_bycatch_is_never_a_second_helping_of_the_same_fish(db, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None, water=None, rare_luck=0.0: REG.item("cod"))  # the water only ever gives cod
    user = await player(1)
    cast = cast_of("cod")
    cast.bycatch, cast.water = 1.0, next(w for w in RULES.waters if w.id == "pond")
    for arrow in cast.pattern:
        cast.press(arrow, T0 + 11)
    caught = await f.land(user, cast, REG, rng=Random(3))
    assert caught.bycatch is None and await user.item_quantity("cod") == 1  # (it gives up rather than hand you the same fish again)
