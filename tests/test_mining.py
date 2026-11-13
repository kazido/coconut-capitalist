import asyncio
from collections import Counter
from random import Random

import pytest

from cococap.models.skills.mining import Core, Mining, Reactor
from cococap.registry import get_registry
from cococap.services import mining as m
from cococap.user import User

REG = get_registry()
RULES = REG.mining


# ---- pure rules ---------------------------------------------------------------------------------
@pytest.mark.parametrize("level, expected", [(1, 1), (5, 1), (6, 2), (11, 3), (16, 4), (21, 5), (25, 5)])
def test_columns_dug_grows_every_five_reactor_levels(level, expected):
    assert m.columns_dug(level, RULES) == expected


@pytest.mark.parametrize("gems, odds", [(0, 25000), (1, 20000), (4, 5000), (10, 1000)])
def test_wyrmhole_odds_improve_with_gems_but_have_a_floor(gems, odds):
    assert m.wyrmhole_odds(gems, RULES) == odds


def test_pending_lodes_scale_with_level_and_cap():
    reactor = lambda level, last: Mining(reactor=Reactor(level=level, last_auto_mine=last))
    assert m.pending_lodes(reactor(1, 0), RULES, now=10**9) == 0  # clock not started
    assert m.pending_lodes(reactor(1, 1000), RULES, now=1000 + 359) == 0
    assert m.pending_lodes(reactor(1, 1000), RULES, now=1000 + 360) == 1
    assert m.pending_lodes(reactor(3, 1000), RULES, now=1000 + 720) == 6  # 2 intervals x 3 levels
    cap = RULES.reactor.automine_cap_hours * 3600 // RULES.reactor.automine_seconds
    assert m.pending_lodes(reactor(2, 1000), RULES, now=10**9) == cap * 2


def test_prestige_needs_all_four_distinct_gems():
    gems = RULES.reactor.core_gems
    full = Mining(reactor=Reactor(**{f"core_{i + 1}": Core(gem_id=g) for i, g in enumerate(gems)}))
    assert m.prestige_unlocked(full, RULES) and m.gems_placed(full) == 4
    dup = Mining(reactor=Reactor(**{f"core_{i + 1}": Core(gem_id=gems[0]) for i in range(4)}))
    assert not m.prestige_unlocked(dup, RULES)
    assert not m.prestige_unlocked(Mining(), RULES)


# ---- generating a mine ----------------------------------------------------------------------------
def make(seed=1, **kw):
    return m.generate_mine(RULES, REG, Random(seed), **kw)


def test_same_seed_same_mine():
    assert make(7).nodes == make(7).nodes and make(7).wyrmholes == make(7).wyrmholes


def test_mine_shape_and_depth_rules():
    gems = set(RULES.reactor.core_gems)
    seen_gem_rows = set()
    for seed in range(300):
        mine = make(seed)
        assert len(mine.nodes) == RULES.rows and all(len(r) == RULES.columns for r in mine.nodes)
        for row, cells in enumerate(mine.nodes):
            for cell in cells:
                if cell and cell[0] in gems:
                    seen_gem_rows.add(row)
                if cell:  # nothing appears outside its row's table
                    assert cell[0] in RULES.depth_tables[row]
    assert seen_gem_rows <= {3, 4} and seen_gem_rows  # gems only in the deepest two levels


def test_wyrmholes_only_below_the_minimum_row_and_gems_make_them_likelier():
    rows = set()
    plain = boosted = 0
    for seed in range(4000):
        a = make(seed, placed_gems=0)
        b = make(seed, placed_gems=4)
        rows |= {r for r, _ in a.wyrmholes | b.wyrmholes}
        plain += bool(a.wyrmholes)
        boosted += bool(b.wyrmholes)
    assert rows <= set(range(RULES.wyrmhole.min_row, RULES.rows))
    assert boosted > plain * 2  # 1/5000 vs 1/25000 per cell


def test_cursor_count_follows_reactor_level_and_starts_in_the_middle():
    assert make(reactor_level=1).cursors == [2]
    assert len(make(reactor_level=6).cursors) == 2 and 2 in make(reactor_level=6).cursors
    assert sorted(make(reactor_level=25).cursors) == [0, 1, 2, 3, 4]


def test_magnet_highlights_the_most_valuable_column():
    mine = make(3, magnet=True)
    worth = lambda c: sum(REG.item(r[c][0]).sell_price * r[c][1] for r in mine.nodes if r[c])
    best = max(range(RULES.columns), key=worth)
    assert best in mine.magnet_columns
    assert make(3, magnet=False).magnet_columns == frozenset()


# ---- playing a mine ---------------------------------------------------------------------------------
def fixed_mine(wyrmholes=frozenset()):
    nodes = [[("copper_ore", r + 1)] * 5 for r in range(5)]
    nodes[1][2] = None
    return m.MineSession(nodes=nodes, wyrmholes=set(wyrmholes), cursors=[2])


def test_movement_wraps_around():
    mine = fixed_mine()
    mine.move(-1), mine.move(-1), mine.move(-1)
    assert mine.cursors == [4]
    mine.move(1)
    assert mine.cursors == [0]


def test_mining_rows_collects_loot_and_finishes_after_the_last_row():
    mine = fixed_mine()
    results = [mine.mine_row() for _ in range(5)]
    assert [r.found for r in results] == [Counter(copper_ore=1), Counter(), Counter(copper_ore=3),
                                          Counter(copper_ore=4), Counter(copper_ore=5)]
    assert results[-1].finished and mine.finished
    assert mine.loot == Counter(copper_ore=13) and mine.lodes == 5
    assert mine.revealed[(1, 2)] is None
    with pytest.raises(m.MiningError):
        mine.mine_row()


def test_multiple_cursors_dig_multiple_columns():
    mine = fixed_mine()
    mine.cursors = [1, 2, 3]
    assert mine.mine_row().found == Counter(copper_ore=3) and mine.lodes == 3


def test_wyrmhole_ends_the_mine_and_collects_nothing_from_that_row():
    mine = fixed_mine(wyrmholes={(2, 3)})
    mine.cursors = [2, 3]
    mine.mine_row(), mine.mine_row()
    result = mine.mine_row()
    assert result.wyrmhole and result.finished and mine.entered_wyrmhole
    assert mine.loot == Counter(copper_ore=4)  # rows 0 and 1 only: (1+1) + (none+2)
    assert mine.row == 2 and mine.finished


def test_wyrmhole_mine_has_exactly_one_implosion_gem():
    for seed in range(50):
        hole = m.generate_wyrmhole(RULES, Random(seed))
        assert len(hole.nodes) == 5
        assert [n[0] for n in hole.nodes].count("implosion_gemstone") == 1
        assert all(n[0] in RULES.wyrmhole.pool or n[0] == "implosion_gemstone" for n in hole.nodes)


def test_wyrmhole_allows_a_single_dig():
    hole = m.generate_wyrmhole(RULES, Random(1))
    hole.move(1)
    item = hole.dig()
    assert hole.finished and item == hole.nodes[3]
    with pytest.raises(m.MiningError):
        hole.dig()


# ---- scarab -----------------------------------------------------------------------------------------
def test_scarab_scroll_is_scrambled_and_checkable():
    challenge = m.make_scarab(["lantern"], RULES, Random(2))
    assert sorted(challenge.scrambled) == sorted("lantern") and challenge.scrambled != "lantern"
    assert challenge.check(" Lantern ") and not challenge.check("lantern!")


def test_scarab_frequency_and_reward():
    hits = sum(m.scarab_appears(RULES, Random(s)) for s in range(5000))
    assert 50 < hits < 160  # about 1 in 51
    reward = m.scarab_reward(REG, RULES, Random(1))
    bomb = REG.item("scarab_bomb")
    assert list(reward) == ["scarab_bomb"] and bomb.drop.min <= reward["scarab_bomb"] <= bomb.drop.max


# ---- operations that persist -------------------------------------------------------------------------
async def player(level=1, **items):
    user = await User.get(1)
    if level > 1:
        await user.add_xp("mining", User.level_to_xp(level) + 1)
    for item_id, qty in items.items():
        await user.add_item(item_id, qty)
    return user


async def test_dig_row_banks_loot_immediately_and_finish_pays_xp_only_when_complete(db):
    user = await player()
    mine = fixed_mine()
    await m.dig_row(user, mine)
    assert await user.items() == {"copper_ore": 1}
    assert await m.finish_mine(user, mine) == 0  # abandoned: no xp...
    assert (await user.skill("mining")).stats.lodes_mined == 1  # ...but the lode is counted
    for _ in range(4):
        await m.dig_row(user, mine)
    assert await m.finish_mine(user, mine) == RULES.xp_per_column * 1
    assert (await user.skill("mining")).xp == 10
    assert await user.item_quantity("copper_ore") == 13


async def test_a_full_magnet_is_spent_when_the_next_mine_starts(db):
    user = await player()
    await user.update_skill("mining", lambda s: setattr(s, "magnet_meter", RULES.magnet.capacity))
    mine = await m.start_mine(user, Random(1))
    assert mine.magnet_columns  # highlighted
    assert (await user.skill("mining")).magnet_meter == 0
    assert not (await m.start_mine(user, Random(1))).magnet_columns  # not twice


async def test_magnet_deposits(db):
    user = await player(level=5, gold_ore=3, iron_ore=2, apple=1)
    assert await m.deposit_ore(user, "gold_ore", 3) == (300, 3)
    assert await m.deposit_ore(user, "iron_ore", 2) == (320, 2)
    with pytest.raises(m.MiningError, match="only takes"):
        await m.deposit_ore(user, "apple", 1)
    with pytest.raises(m.MiningError, match="don't have"):
        await m.deposit_ore(user, "gold_ore", 1)
    await user.add_item("gold_ore", 50)
    meter, used = await m.deposit_ore(user, "gold_ore", 50)
    assert meter == RULES.magnet.capacity and used == 7  # only the ore that fits is taken
    assert await user.item_quantity("gold_ore") == 43
    with pytest.raises(m.MiningError, match="full"):
        await m.deposit_ore(user, "gold_ore", 1)


async def test_magnet_requires_level(db):
    user = await player(level=1, gold_ore=1)
    with pytest.raises(m.MiningError, match="level 5"):
        await m.deposit_ore(user, "gold_ore", 1)
    assert await user.item_quantity("gold_ore") == 1  # nothing was taken


async def test_gem_placement_rules_and_prestige(db):
    gems = RULES.reactor.core_gems
    user = await player(level=1, **{g: 1 for g in gems}, implosion_gemstone=2)
    with pytest.raises(m.MiningError, match="level 10"):
        await m.place_gem(user, gems[0])
    await user.add_xp("mining", User.level_to_xp(10) + 1)

    assert await m.place_gem(user, gems[0]) == 1  # each gem goes to its own slot
    assert (await user.skill("mining")).reactor.core_1.gem_id == gems[0]
    assert await user.item_quantity(gems[0]) == 0
    await user.add_item(gems[0], 1)
    with pytest.raises(m.MiningError, match="already in the reactor"):
        await m.place_gem(user, gems[0])
    assert await user.item_quantity(gems[0]) == 1  # not consumed by the failed attempt
    with pytest.raises(m.MiningError, match="isn't a reactor gem"):
        await m.place_gem(user, "copper_ore")
    with pytest.raises(m.MiningError, match="Fill all four"):
        await m.prestige(user)

    for gem in gems[1:]:
        await m.place_gem(user, gem)
    assert await m.prestige(user) == 2 and await user.item_quantity("implosion_gemstone") == 1
    assert await m.prestige(user) == 3 and await user.item_quantity("implosion_gemstone") == 0
    with pytest.raises(m.MiningError, match="implosion gem"):
        await m.prestige(user)


async def test_prestige_stops_at_the_maximum(db):
    gems = RULES.reactor.core_gems
    user = await player(level=10, implosion_gemstone=3)
    def setup(s):
        for i, g in enumerate(gems, start=1):
            getattr(s.reactor, f"core_{i}").gem_id = g
        s.reactor.level = RULES.reactor.max_prestige
    await user.update_skill("mining", setup)
    with pytest.raises(m.MiningError, match="maximum"):
        await m.prestige(user)
    assert await user.item_quantity("implosion_gemstone") == 3


async def test_lodes_accumulate_and_can_only_be_claimed_once(db):
    user = await player()
    status = await m.reactor_status(user, now=1000.0)  # first visit starts the clock
    assert status["pending_lodes"] == 0
    lodes, loot = await m.claim_lodes(user, Random(1), now=1000 + 360 * 10)
    assert lodes == 10 and sum(loot.values()) > 0
    assert await user.item_quantity("copper_ore") == loot["copper_ore"]
    assert (await user.skill("mining")).stats.lodes_auto_mined == 10
    assert await m.claim_lodes(user, Random(1), now=1000 + 360 * 10) == (0, Counter())


async def test_concurrent_lode_claims_pay_once(db):
    user = await player()
    await m.reactor_status(user, now=1000.0)
    handles = [await User.get(1) for _ in range(5)]
    results = await asyncio.gather(
        *(m.claim_lodes(h, Random(i), now=1000 + 3600) for i, h in enumerate(handles))
    )
    assert sorted(r[0] for r in results) == [0, 0, 0, 0, 10]


async def test_wyrmhole_reward_is_banked(db):
    user = await player()
    hole = m.generate_wyrmhole(RULES, Random(5))
    item_id, qty = await m.finish_wyrmhole(user, hole)
    assert await user.item_quantity(item_id) == qty
    assert (await user.skill("mining")).stats.lodes_mined == 1


async def test_scarab_reward_is_banked(db):
    user = await player()
    reward = await m.claim_scarab_reward(user, Random(1))
    assert await user.items() == dict(reward)
