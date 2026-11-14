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


async def test_you_get_five_different_dailies_and_a_weekly_that_stay_the_same_all_period(db):
    user = await player()
    await level_up(user)
    first = await f.quests(user, DAY0, REG)
    assert [q.kind for q in first] == ["daily"] * Q.daily_count + ["weekly"]
    assert len({q.template for q in first if q.kind == "daily"}) == Q.daily_count
    assert [q.template for q in await f.quests(user, DAY0 + 3600, REG)] == [q.template for q in first]
    days = {tuple(q.template for q in await f.quests(user, DAY0 + d * f.DAY, REG) if q.kind == "daily") for d in range(8)}
    assert len(days) > 1  # a different set on different days


async def test_finishing_a_quest_pays_once_and_a_cod_does_not_count_toward_rare_quests(db):
    user = await player()
    await level_up(user)
    quests = await f.quests(user, DAY0, REG)
    easy = [q for q in quests if q.kind == "daily" and q.template.min_rarity == 1]
    assert easy, "the test player's dailies should include an easy quest (fixed seed)"
    before, paid = user.purse, 0
    for _ in range(max(q.template.count for q in easy) + 3):
        paid += (await catch(user, "cod", DAY0 + 10)).quest_bits
    await user.refresh()
    assert paid == sum(q.template.bits for q in easy) and user.purse == before + paid
    after = await f.quests(user, DAY0 + 20, REG)
    assert all(q.done for q in after if q.template.min_rarity == 1 and q.kind == "daily")
    assert all(q.progress == 0 for q in after if q.template.min_rarity > 1)
    assert (await user.skill("fishing")).stats.quests_completed == len(easy)


async def test_a_rare_fish_counts_toward_every_quest_it_is_good_enough_for(db):
    user = await player()
    await level_up(user)
    await catch(user, "pufferfish", DAY0)  # rarity 4
    after = await f.quests(user, DAY0, REG)
    assert all(q.progress == 1 or q.done for q in after if q.template.min_rarity <= 4)
    assert all(q.progress == 0 for q in after if q.template.min_rarity > 4)


async def test_a_new_day_starts_fresh_but_the_week_carries_on_and_a_new_week_resets(db):
    user = await player()
    await level_up(user)
    for _ in range(2):
        await catch(user, "pufferfish", DAY0)
    today, tomorrow = await f.quests(user, DAY0, REG), await f.quests(user, DAY0 + f.DAY, REG)
    assert any(q.progress or q.done for q in today if q.kind == "daily")
    assert not any(q.progress or q.done for q in tomorrow if q.kind == "daily")
    assert [(q.progress, q.done) for q in tomorrow if q.kind == "weekly"] == [(q.progress, q.done) for q in today if q.kind == "weekly"]
    assert not any(q.progress or q.done for q in await f.quests(user, DAY0 + 7 * f.DAY, REG))


async def test_the_catch_that_unlocks_quests_does_not_count_toward_them(db):
    user = await player()
    await level_up(user, Q.min_level - 1)
    just_under = User.level_to_xp(Q.min_level) - (await user.skill("fishing")).xp - 1
    await user.add_xp("fishing", just_under)  # one xp short of the level
    await catch(user, "cod", DAY0)  # this catch takes them over the line
    assert User.xp_to_level((await user.skill("fishing")).xp) == Q.min_level
    assert all(q.progress == 0 for q in await f.quests(user, DAY0, REG))


async def test_quest_xp_is_added_on_top_of_the_catch(db):
    user = await player()
    await level_up(user)
    quest = next(q for q in await f.quests(user, DAY0, REG) if q.template.min_rarity == 4 and q.template.count == 1) \
        if any(q.template.min_rarity == 4 and q.template.count == 1 for q in await f.quests(user, DAY0, REG)) else None
    before = (await user.skill("fishing")).xp
    got = await catch(user, "pufferfish", DAY0)
    gained = (await user.skill("fishing")).xp - before
    assert gained == got.xp + sum(q.template.xp for q in got.finished)
    assert quest is None or quest.template.xp in {q.template.xp for q in got.finished}


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


async def test_a_bite_you_ignore_for_six_seconds_gets_away(db, clock, monkeypatch):
    monkeypatch.setattr(f, "roll_fish", lambda rng, reg=None: REG.item("cod"))
    user, nav, inter = await open_fishing()
    await click(nav, inter, "Cast")
    clock[0] = nav.screen.cast.bite_at + RULES.bite.window - 1
    await nav.screen.nav.refresh(inter)
    assert "A bite!" in all_text(nav)
    clock[0] = nav.screen.cast.bite_at + RULES.bite.window + 1
    await nav.screen.nav.refresh(inter)
    assert nav.screen.cast is None and "too slow" in all_text(nav)
