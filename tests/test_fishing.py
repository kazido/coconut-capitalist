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


def test_each_book_level_needs_more_of_every_fish():
    needs = [f.book_need(level, RULES) for level in range(1, 6)]
    assert needs == sorted(needs) and needs[0] == B.need_base and len(set(needs)) == 5


async def test_the_book_is_locked_until_the_level(db):
    user = await player()
    with pytest.raises(f.FishingError, match="opens at fishing level"):
        await f.turn_in(user, "cod", REG)


async def test_turning_in_fish_pays_a_bonus_and_fills_the_page(db):
    user = await book_player(fish={"cod": 3})
    before_xp, before_bits = (await user.skill("fishing")).xp, user.purse
    done = await f.turn_in(user, "cod", REG)
    assert done.quantity == B.need_base  # only as many as the page needs
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
    assert again.level == 2 and not again.complete and all(e.given == 0 and e.need == f.book_need(2, RULES) for e in again.entries)
    with pytest.raises(f.FishingError, match="isn't full"):
        await f.complete_book(user, REG)  # no double payout


async def test_the_book_stops_at_its_top_level(db):
    user = await book_player()
    await user.update_skill("fishing", lambda s: setattr(s.book, "level", B.max_level))
    need = f.book_need(B.max_level, RULES)
    await user.update_skill("fishing", lambda s: s.book.given.update({i.id: need for i in f.book_fish(REG)}))
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
