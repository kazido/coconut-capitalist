"""The Mining stat page: existing numbers show for an existing player, and each new counter goes up by one per mine (never twice)."""

from collections import Counter
from pathlib import Path
from random import Random

from cococap.services import mining
from cococap.services.stats_mining import page
from cococap.user import User
from tests.test_hub import all_text, choose, hub, select_named

NEW_NAMES = (
    "mining_mines_entered", "mining_safe_exits", "mining_collapses", "mining_vault_floors", "mining_wyrmholes_found",
    "mining_lifeline_saves", "mining_vents_dug", "mining_braces_used", "mining_bombs_used", "mining_magnet_rows",
    "mining_implosion_gems", "mining_deepest_row", "mining_biggest_haul", "mining_ore_",
)


def rows(p) -> dict[str, object]:
    return {label: value for _, lines in p.groups for label, value in lines}


async def settle(user, outcome="left", depth=1, haul=None):
    run = await mining.start_run(user, Random(1))
    run.outcome, run.depth, run.lodes = outcome, depth, 4
    run.haul = Counter(haul or {})
    await mining.settle_run(user, run)
    return run


async def test_existing_numbers_show_for_an_existing_player(db):
    user = await User.get(1)
    await user.update_skill("mining", lambda m: setattr(m.stats, "lodes_mined", 40))
    got = rows(await page(user, await user.stats()))
    assert got["Lodes mined"] == 40
    assert got["Mines entered"] == 0 and got["Deepest row"] == 0  # new counters start at 0, nothing double counted


async def test_one_mine_moves_each_counter_by_exactly_one(db):
    user = await User.get(1)
    await user.update_skill("mining", lambda m: setattr(m.stats, "lodes_mined", 40))
    first = await settle(user, outcome="left", depth=2, haul={"material_copper_ore": 3})
    got = rows(await page(user, await user.stats()))
    assert got["Mines entered"] == 1 and got["Safe exits"] == 1 and got["Deepest row"] == 2
    assert got["Lodes mined"] == 40 + first.lodes  # the existing count is kept and goes up by this mine only

    await settle(user, outcome="collapse", depth=1)
    got = rows(await page(user, await user.stats()))
    assert got["Mines entered"] == 2 and got["Collapses"] == 1 and got["Safe exits"] == 1
    assert got["Deepest row"] == 2  # best row, not the latest
    assert got["Lodes mined"] == 40 + first.lodes + 4

    await mining.settle_run(user, first)  # settling a finished run again changes nothing
    assert rows(await page(user, await user.stats()))["Mines entered"] == 2


def test_every_new_counter_is_written_in_the_services():
    src = Path(mining.__file__).read_text(encoding="utf-8")
    for name in NEW_NAMES:
        assert f'"{name}' in src, name


async def test_the_mining_page_renders_in_the_stats_tab(db):
    user = await User.get(1)
    await user.update_skill("mining", lambda m: setattr(m.stats, "lodes_mined", 7))
    nav, inter = await hub("player", tab="stats")
    await choose(nav, inter, select_named(nav, "Pick a page"), "mining")
    text = all_text(nav)
    assert "Lodes mined" in text and "Mines entered" in text
