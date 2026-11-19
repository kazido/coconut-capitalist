"""Ability scrolls: an enchant that is a visible ability (Echo Strike is the first), and a scroll that only one mine type can drop."""

from collections import Counter
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.screens import mine as mine_screen
from cococap.screens.mine import echo_note
from cococap.services import mining as m
from cococap.services.mining import MiningError
from cococap.services import scrolls
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
