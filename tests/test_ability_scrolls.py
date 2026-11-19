"""Ability scrolls: an enchant that is a visible ability (Echo Strike is the first), and a scroll that only one mine type can drop."""

from collections import Counter
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.screens import mine as mine_screen
from cococap.screens.mine import echo_note
from cococap.services import mining as m
from cococap.services.mining import MiningError
from cococap.services import foraging as forage
from cococap.services import enchanting, equipment
from cococap.services import fishing as f
from cococap.services import scrolls
from cococap.services.equipment import equip
from cococap.services.fishing import FishingError
from tests.test_hub import buttons, click, hub
from cococap.screens.forage import ember_line, timber_note
from cococap.services.equipment import equip
from cococap.user import User

REG = get_registry()
RULES = REG.mining
D = RULES.descent
WYRM = RULES.mine_type("wyrm_tunnels")
ECHO = REG.item("scroll_echo_strike")
COPPER, GOLD = ("material_copper_ore", 1), ("material_gold_ore", 1)


class Rig(Random):
    """A generator whose random() always returns `value`."""

    def __init__(self, value):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


def calm_run(seed=1, **kw):
    """A run with no collapse, no vents, no caches and no rich lodes, so only the echo can change the dig."""
    rules = RULES.model_copy(update={"descent": D.model_copy(update={"rich_chance": 0.0, "vent_chance": 0.0, "cache_chance": 0.0})})
    run = m.MineRun(rules, REG, Random(seed), cursors=[2], **kw)
    run.rng = Random(seed)
    return run


def force_row(run, cells, holes=()):
    run.row(run.depth)
    run._rows[run.depth] = list(cells)
    run._kinds[run.depth] = ["ore"] * len(cells)
    run._holes[run.depth] = set(holes)


# ---- the data ----------------------------------------------------------------------------------------------------------
def test_echo_strike_is_a_pickaxe_enchant_with_a_scroll_from_wyrm_tunnels_only():
    enchant = REG.enchant("echo_strike")
    assert enchant.emoji and enchant.applies_to == ["pickaxe"] and enchant.max_level == 3
    assert ECHO.scroll.enchant == "echo_strike" and ECHO.category == "scroll" and ECHO.emoji
    assert scrolls.scroll_skills(ECHO.id, REG) == ["mining"]
    sources = [t.id for t in RULES.mine_types if t.scroll and t.scroll.item == ECHO.id]
    assert sources == ["wyrm_tunnels"]
    assert all(t.scroll is None for t in RULES.mine_types if t.id not in ("wyrm_tunnels", "scholars_cavern"))


# ---- Echo Strike on a dig -------------------------------------------------------------------------------------------------
def test_echo_strike_can_crack_the_tile_beside_the_dug_one_and_says_so():
    run = calm_run(echo_strike=1.0)  # every dig
    force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
    result = run.dig()
    assert len(result.echo) == 1 and result.echo[0] in (1, 3)
    assert run.lodes == 2  # the dug tile and its echo
    assert "Echo Strike" in echo_note(result)
    assert echo_note(m.DigResult(Counter())) == ""


def test_without_the_enchant_a_dig_never_echoes():
    for seed in range(40):
        run = calm_run(seed)  # echo_strike defaults to 0
        force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
        result = run.dig()
        assert result.echo == () and run.lodes == 1


def test_echo_strike_chance_is_the_enchant_level_times_its_step():
    step = REG.enchant("echo_strike").effects[0].amount
    hits = 0
    for seed in range(400):
        run = calm_run(seed, echo_strike=step * 3)  # level 3
        force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
        hits += bool(run.dig().echo)
    assert 0.1 < hits / 400 < 0.3  # about 18%


def test_echo_strike_never_cracks_a_wyrmhole_or_a_tile_already_dug():
    for seed in range(40):
        run = calm_run(seed, echo_strike=1.0)
        force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER], holes=(1, 3))  # wyrmholes on both sides
        result = run.dig()
        assert result.echo == () and run.lodes == 1


def test_an_echoed_tile_adds_no_pressure():
    plain, echoed = calm_run(seed=5), calm_run(seed=5, echo_strike=1.0)
    for run in (plain, echoed):
        force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
    plain.dig()
    result = echoed.dig()
    assert result.echo
    assert echoed.danger == plain.danger  # the echo's loot came, its rock pressure did not


# ---- the Wyrm Tunnels scroll ----------------------------------------------------------------------------------------------
async def test_an_equipped_pickaxe_with_echo_strike_arms_the_run(db):
    user = await User.get(1)
    pick = await user.give_instance("tool_pickaxe_rookie", enchants={"echo_strike": 2})
    await equip(user, "mining", pick.id)
    run = await m.start_run(user, Random(1), mine_type="standard")
    assert run.echo_strike == REG.enchant("echo_strike").effects[0].amount * 2


async def banked(db, mine_type_id, roll):
    user = await User.get(1)
    run = m.MineRun(RULES, REG, Random(1), cursors=[2], mine_type=RULES.mine_type(mine_type_id))
    run.rng = Rig(roll)
    run.leave()
    return await m.settle_run(user, run)


async def test_wyrm_tunnels_can_drop_the_echo_scroll_when_a_run_is_banked(db):
    summary = await banked(db, "wyrm_tunnels", 0.0)  # a roll that always hits the odds
    assert summary.haul[ECHO.id] == 1
    assert await (await User.get(1)).item_quantity(ECHO.id) == 1


async def test_wyrm_tunnels_never_drops_the_scroll_on_a_miss(db):
    summary = await banked(db, "wyrm_tunnels", 0.999)
    assert ECHO.id not in summary.haul


async def test_other_mine_types_never_drop_the_echo_scroll(db):
    for t in RULES.mine_types:
        if t.id != "wyrm_tunnels":
            summary = await banked(db, t.id, 0.0)
            assert ECHO.id not in summary.haul, t.id


# ---- Second Wind and Prospector's Ping (pickaxe abilities, one scroll source each) -----------------------------------------
SECOND = REG.item("scroll_second_wind")
PING = REG.item("scroll_prospectors_ping")
TOP = RULES.descent.warnings[-1].name


def rig_collapse(run):
    """Make the next collapse roll always hit: high pressure (a real max risk) and a roll of 0."""
    run.danger = 100
    run.rng = Rig(0.0)


def test_second_wind_and_ping_enchants_and_scrolls_exist():
    for enchant, item in (("second_wind", SECOND), ("prospectors_ping", PING)):
        assert REG.enchant(enchant).applies_to == ["pickaxe"] and REG.enchant(enchant).max_level == 1
        assert item.scroll.enchant == enchant and item.category == "scroll" and item.emoji
        assert scrolls.scroll_skills(item.id, REG) == ["mining"]


def test_second_wind_holds_the_collapse_once_and_brace_saves_it_for_free():
    run = calm_run(second_wind=True)
    force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
    rig_collapse(run)
    result = run.dig()
    assert result.second_wind and not result.collapsed and run.outcome is None
    braces = run.braces
    danger = run.danger
    run.brace()
    assert run.braces == braces and run.danger == max(0.0, danger - RULES.descent.brace_amount)
    assert not run.second_wind_held and run.second_wind_used
    run.rng = Rig(0.0)  # collapse rolls again, but the mine is already used up: it collapses
    result = run.dig()
    assert result.collapsed


def test_second_wind_only_lets_the_collapse_happen_if_the_player_digs_instead():
    run = calm_run(second_wind=True)
    force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
    rig_collapse(run)
    assert run.dig().second_wind
    result = run.dig()  # any other action (here a dig) lets the rock give way
    assert result.collapsed and run.outcome == "collapse"


def test_without_the_enchant_a_collapse_is_a_plain_collapse():
    run = calm_run()
    force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
    rig_collapse(run)
    result = run.dig()
    assert result.collapsed and not result.second_wind


def test_ping_reveals_the_three_tiles_under_the_cursor_once_per_mine():
    run = calm_run(prospectors_ping=True)
    tiles = run.ping()
    col = run.cursors[0]
    assert tiles == [(run.depth + i, col) for i in range(3)]
    assert run.pinged == set(tiles)
    with pytest.raises(MiningError):
        run.ping()


def test_ping_needs_the_enchant():
    run = calm_run()
    with pytest.raises(MiningError):
        run.ping()


def test_pinged_tiles_show_their_contents_on_the_shaft():
    run = calm_run(prospectors_ping=True)
    run.ping()
    shown = mine_screen.ahead_row(run, run.depth)
    assert shown  # the row renders with the revealed tile in it
    assert (run.depth, run.cursors[0]) in run.pinged


async def test_second_wind_and_ping_enchants_arm_the_run(db):
    user = await User.get(1)
    pick = await user.give_instance("tool_pickaxe_rookie", enchants={"second_wind": 1, "prospectors_ping": 1})
    await equip(user, "mining", pick.id)
    run = await m.start_run(user, Random(1), mine_type="standard")
    assert run.second_wind_armed and run.ping_armed


async def test_second_wind_scroll_drops_only_from_runs_that_reached_the_top_label(db):
    user = await User.get(1)
    run = m.MineRun(RULES, REG, Random(1), cursors=[2])
    run.rng = Rig(0.0)
    run.reached_top = True
    run.leave()
    summary = await m.settle_run(user, run)
    assert summary.haul[SECOND.id] == 1
    low = m.MineRun(RULES, REG, Random(1), cursors=[2])
    low.rng = Rig(0.0)
    low.leave()
    summary = await m.settle_run(await User.get(1), low)
    assert SECOND.id not in summary.haul


async def test_ping_scroll_drops_only_from_scholars_cavern(db):
    summary = await banked(db, "scholars_cavern", 0.0)
    assert summary.haul[PING.id] == 1
    for t in RULES.mine_types:
        if t.id != "scholars_cavern":
            summary = await banked(db, t.id, 0.0)
            assert PING.id not in summary.haul, t.id


# ---- Timber! and Ember Bite (axe enchants; Redwood and Emberwood each drop one; Double Strike moved to Burl grain) ------------
FRULES = REG.foraging


def test_timber_and_ember_bite_are_axe_enchants_and_each_scroll_has_one_tree_source():
    for enchant, scroll, species in (("timber", "scroll_timber", "redwood"), ("ember_bite", "scroll_ember_bite", "emberwood")):
        assert REG.enchant(enchant).applies_to == ["axe"] and REG.item(scroll).scroll.enchant == enchant
        assert scrolls.scroll_skills(scroll, REG) == ["foraging"]
        assert [sp.id for sp in FRULES.species if sp.scroll and sp.scroll.item == scroll] == [species]


def test_double_strike_drops_only_from_burl_grain_and_foraging_has_no_general_pool():
    assert {g.id for g in FRULES.chopping.grains if g.scroll and g.scroll.item == "scroll_double_strike"} == {"burl"}
    assert all(sp.scroll is None or sp.scroll.item != "scroll_double_strike" for sp in FRULES.species)
    assert REG.scrolls.foraging is None and scrolls.roll("foraging", Random(1), REG) is None


def test_each_tree_source_drops_its_own_scroll_and_no_other_species_or_grain_does():
    rng = Random(7)
    for sp in FRULES.species:
        tree = forage.Tree(1, 10, 0, species=sp.id)
        got = {item for _ in range(20_000) for item in forage.roll_tree_scrolls(tree, rng, REG)}
        assert got <= ({sp.scroll.item} if sp.scroll else set()), sp.id
    for grain in FRULES.chopping.grains:
        tree = forage.Tree(1, 10, 0, grain=grain.id)
        got = {item for _ in range(20_000) for item in forage.roll_tree_scrolls(tree, rng, REG)}
        assert got <= ({grain.scroll.item} if grain.scroll else set()), grain.id


def test_tree_scrolls_drop_at_their_odds():
    tree = forage.Tree(1, 10, 0, species="redwood")
    rng = Random(3)
    hits = sum(len(forage.roll_tree_scrolls(tree, rng, REG)) for _ in range(30_000))
    odds = next(sp.scroll.odds for sp in FRULES.species if sp.id == "redwood")
    assert hits == pytest.approx(30_000 / odds, rel=0.25)


def test_ember_bite_sets_the_trunk_smouldering_and_the_next_chops_hit_harder_then_it_stops():
    tree = forage.Tree(1, 100, 100)
    assert forage.ember_tick(tree, 0.0, Rig(0.0), FRULES) is False and tree.smouldering == 0  # no enchant: never catches
    assert forage.ember_tick(tree, 0.04, Rig(0.99), FRULES) is False and tree.smouldering == 0  # a missed roll
    assert forage.ember_tick(tree, 0.04, Rig(0.0), FRULES) is True and tree.smouldering == FRULES.chopping.ember_chops
    powers = []
    for _ in range(4):
        powers.append(forage.ember_power(tree, 10, FRULES))
        forage.ember_tick(tree, 0.0, Rig(0.99), FRULES)
    boosted = round(10 * FRULES.chopping.ember_mult)
    assert powers == [boosted] * FRULES.chopping.ember_chops + [10] and tree.smouldering == 0


def test_timber_topples_a_tree_into_the_next_half_chopped():
    tree = forage.roll_tree(1, Random(2), FRULES, species="pine")
    forage.topple(tree, FRULES)
    assert tree.hp == tree.max_hp - round(tree.max_hp * FRULES.chopping.timber_share) and not tree.felled


def test_the_timber_and_ember_notes_show_only_when_they_happen():
    assert timber_note(forage.Reward(Counter(), 0, 0, timber=True)) and timber_note(forage.Reward(Counter(), 0, 0)) == ""
    assert ember_line(forage.Tree(1, 10, 0, smouldering=2)) == "\n🔥 Smouldering: 2 chops left"
    assert ember_line(forage.Tree(1, 10, 0, smouldering=1)).endswith("1 chop left")
    assert ember_line(forage.Tree(1, 10, 0)) == ""


async def test_timber_only_happens_with_the_enchant_on_the_axe(db):
    lucky = Rig(0.0)  # every chance roll passes
    user = await User.get(1)
    axe = await user.give_instance("tool_axe_starter", enchants={"timber": 3})
    await equip(user, "foraging", axe.id)
    reward = await forage.fell_private(user, forage.Tree(1, 10, 0, species="pine"), lucky, REG)
    assert reward.timber is True
    plain = await User.get(2)
    bare = await plain.give_instance("tool_axe_starter")
    await equip(plain, "foraging", bare.id)
    assert (await forage.fell_private(plain, forage.Tree(1, 10, 0, species="pine"), Rig(0.0), REG)).timber is False


# ---- fishing: Net Cast, Steady Line and Double Hook each come from ONE source ----------------------------------------------
NET = REG.items["scroll_net_cast"]
STEADY = REG.items["scroll_steady_line"]
DOUBLE = REG.items["scroll_double_hook"]
FISH_STATS = equipment.EffectiveStats(power=3, requirement=0, stats={"power": 3.0})


class Always(Random):
    """A generator whose random() is 0 (every 1-in-N roll hits) and whose randint() is the low end."""

    def randint(self, a, b):
        return a

    def random(self):
        return 0.0


class Never(Random):
    """A generator whose random() is just under 1 (no 1-in-N roll hits)."""

    def randint(self, a, b):
        return b

    def random(self):
        return 0.999999


async def net_rod(user_id=1):
    user = await User.get(user_id)
    rod = await user.give_instance("tool_rod_starter")
    await equip(user, "fishing", rod.id)
    await user.add_item("scroll_net_cast", 1)
    await enchanting.apply_scroll(user, "scroll_net_cast", rod.id, REG)
    return user


def test_net_cast_is_a_rod_enchant_and_only_old_whiskers_drops_it():
    enchant = REG.enchant("net_cast")
    assert enchant.applies_to == ["rod"] and enchant.max_level == 1
    assert NET.scroll.enchant == "net_cast" and scrolls.scroll_skills(NET.id, REG) == ["fishing"]
    assert [b.name for b in REG.fishing.boss.bosses if b.scroll and b.scroll.item == NET.id] == ["Old Whiskers"]
    assert not any(w.scroll and w.scroll.item == NET.id for w in REG.fishing.waters)
    assert not any(r.item == NET.id for r in (*REG.fishing.treasure.loot, *REG.fishing.boss.loot))


async def test_net_cast_needs_the_enchant(db):
    user = await User.get(1)
    rod = await user.give_instance("tool_rod_starter")
    await equip(user, "fishing", rod.id)
    with pytest.raises(FishingError):
        await f.net_cast(user, REG.fishing.waters[0], REG)


async def test_net_cast_hauls_three_of_the_commonest_fish_at_once(db):
    user = await net_rod()
    water = REG.fishing.waters[1]  # the river
    fish_id = min(water.fish, key=water.fish.get)
    got, count, xp = await f.net_cast(user, water, REG)
    assert got == fish_id and count == 3 == REG.fishing.net.fish
    assert await user.item_quantity(fish_id) == 3 and xp == round(water.xp * 3)


async def test_net_cast_has_a_cooldown_that_a_second_net_must_wait_out(db):
    user = await net_rod()
    water = REG.fishing.waters[0]
    cool = REG.fishing.net.cooldown_seconds
    fish_id = min(water.fish, key=water.fish.get)
    await f.net_cast(user, water, REG, now=1000.0)
    with pytest.raises(FishingError, match="drying"):
        await f.net_cast(user, water, REG, now=1000.0 + cool - 1)
    assert await user.item_quantity(fish_id) == 3  # the refused net caught nothing
    assert await f.net_ready_in(user, 1000.0 + cool - 1, REG) == pytest.approx(1)
    await f.net_cast(user, water, REG, now=1000.0 + cool)  # ready again once the cooldown has passed
    assert await user.item_quantity(fish_id) == 6


async def test_the_net_button_shows_its_cooldown_and_reopening_the_page_does_not_reset_it(db):
    user = await net_rod()
    nav, inter = await hub("fish")
    await click(nav, inter, "Net")
    assert await user.item_quantity(min(REG.fishing.waters[0].fish, key=REG.fishing.waters[0].fish.get)) == 3
    nav, inter = await hub("fish")  # reopening the page is not a new trip
    labels = [b.label for b in buttons(nav)]
    assert any(label and label.startswith("Net ready in") for label in labels), labels
    assert not any(label == "Net" for label in labels)


async def test_each_boss_drops_only_its_own_scroll(db):
    user = await User.get(1)
    for boss in REG.fishing.boss.bosses:
        cast = f.cast_line(FISH_STATS, Always(1), 0, REG)
        f.make_boss(cast, boss.name, REG.fishing, Always(1))
        cast.hook(cast.bite_at + 1)
        for arrow in list(cast.truth):
            cast.press(arrow, cast.bite_at + 2)
        won = await f.defeat_boss(user, cast, Always(2), REG)
        got = {i for i in won.items if i.startswith("scroll_")}
        assert got == ({boss.scroll.item} if boss.scroll else set()), boss.name
        cast = f.cast_line(FISH_STATS, Never(1), 0, REG)
        f.make_boss(cast, boss.name, REG.fishing, Never(1))
        cast.hook(cast.bite_at + 1)
        for arrow in list(cast.truth):
            cast.press(arrow, cast.bite_at + 2)
        lost = await f.defeat_boss(user, cast, Never(2), REG)
        assert not any(i.startswith("scroll_") for i in lost.items), boss.name


def test_double_hook_and_steady_line_have_one_source_each():
    assert [b.name for b in REG.fishing.boss.bosses if b.scroll and b.scroll.item == DOUBLE.id] == ["Grandfather Carp"]
    assert [w.id for w in REG.fishing.waters if w.scroll and w.scroll.item == STEADY.id] == ["cadrega_canals"]
    assert not any(r.item in (DOUBLE.id, STEADY.id) for r in (*REG.fishing.treasure.loot, *REG.fishing.boss.loot))
    assert scrolls.scroll_skills(DOUBLE.id, REG) == ["fishing"] and scrolls.scroll_skills(STEADY.id, REG) == ["fishing"]


async def test_a_water_drops_its_scroll_only_in_that_water(db):
    user = await User.get(1)
    for water in REG.fishing.waters:
        cast = f.cast_line(FISH_STATS, Always(1), 0, REG, water=water, plain=True)
        cast.hook(cast.bite_at + 1)
        for arrow in list(cast.truth):
            cast.press(arrow, cast.bite_at + 2)
        await f.land(user, cast, REG, now=cast.bite_at + 3, rng=Always(2))  # every 1-in-N roll hits
    assert await user.item_quantity(STEADY.id) == 1  # only the cadrega_canals catch dropped it
