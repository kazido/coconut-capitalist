import asyncio
from collections import Counter
from random import Random

import pytest
from pydantic import ValidationError

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



# ---- the descent (pure rules) ------------------------------------------------------------------
D = RULES.descent


class Rig(Random):
    """A generator whose random() always returns `value` (for forcing collapse / no-collapse)."""

    def __init__(self, value):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


D = RULES.descent


def rules_with(**descent):
    return RULES.model_copy(update={"descent": D.model_copy(update=descent)})


def make_run(seed=1, rules=RULES, **kw):
    kw.setdefault("cursors", [2])
    return m.MineRun(rules, REG, Random(seed), **kw)


def force_row(run, cells, kinds=None, holes=(), depth=None):
    """Fix the row about to be dug: `cells` (5 items) and optional `kinds`."""
    depth = run.depth if depth is None else depth
    run.row(depth)
    run._rows[depth] = list(cells)
    run._kinds[depth] = list(kinds or ["ore"] * len(cells))
    run._holes[depth] = set(holes)


COPPER, GOLD = ("copper_ore", 1), ("gold_ore", 1)


# ---- the shaft: tiers, rows, loot -------------------------------------------------------------------
def test_depth_tiers_cover_the_whole_shaft():
    run = make_run()
    n = D.rows_per_tier
    assert [run.tier(d) for d in (0, n - 1, n, 2 * n - 1, 2 * n)] == [0, 0, 1, 1, 2]
    assert run.tier(D.floor - 1) == len(RULES.depth_tables) - 1  # the deepest table is actually reachable
    assert run.tier(10_000) == len(RULES.depth_tables) - 1


def test_plain_cells_only_hold_their_own_tiers_loot_and_rich_lodes_come_from_the_next_tier():
    for seed in range(120):
        run = make_run(seed)
        for depth in (0, 4, 8, 12):
            tier = run.tier(depth)
            for cell, sign in zip(run.row(depth), run.signs(depth), strict=True):
                if sign == "ore" and cell:
                    assert cell[0] in RULES.depth_tables[tier]
                if sign == "rich":
                    assert cell and cell[0] in RULES.depth_tables[min(tier + 1, len(RULES.depth_tables) - 1)]
                if sign in ("vent", "cache"):
                    assert cell is None


def test_rows_are_rolled_once_and_stay_fixed():
    run = make_run(3)
    assert run.row(2) == run.row(2) and run.signs(2) == run.signs(2)
    assert make_run(3).row(2) == make_run(3).row(2)  # deterministic per seed


def test_gems_only_appear_deep():
    gems = set(RULES.reactor.core_gems)
    shallow = deep = 0
    for seed in range(400):
        run = make_run(seed)
        shallow += sum(1 for c in run.row(1) if c and c[0] in gems)
        deep += sum(1 for c in run.row(D.floor - 1) if c and c[0] in gems)
    assert shallow == 0 and deep > 0


def test_a_better_pickaxe_means_bigger_piles_and_every_row_deeper_pays_more():
    base, boosted = make_run(5), make_run(5, yield_factor=3.0)
    pairs = [(x, y) for x, y, kind in zip(base.row(0), boosted.row(0), base.signs(0), strict=True) if kind == "ore" and x]
    assert pairs and all(y[1] == round(x[1] * 3) for x, y in pairs)
    assert make_run()._quantity_factor(0) == 1.0
    assert make_run()._quantity_factor(20) == pytest.approx(1 + 20 * D.depth_bonus_per_row)
    assert make_run()._quantity_factor(20) > make_run()._quantity_factor(10) > make_run()._quantity_factor(0)


# ---- pressure and the collapse risk ----------------------------------------------------------------------
def test_risk_is_zero_when_safe_then_climbs_smoothly_to_the_maximum():
    run = make_run()
    seen = []
    for pressure in range(0, 101, 5):
        run.danger = pressure
        seen.append(run.risk)
    assert seen[0] == 0 and all(r == 0 for p, r in zip(range(0, 101, 5), seen, strict=True) if p <= D.safe_pressure)
    assert seen == sorted(seen) and seen[-1] == pytest.approx(D.max_risk)
    steps = [b - a for a, b in zip(seen, seen[1:], strict=False)]
    assert max(steps) < D.max_risk / 3  # no cliffs: the old 3%/10%/25% staircase is gone
    run.danger = 50
    assert 0.03 < run.risk < 0.10  # halfway is a real, but not scary, chance


def test_the_warning_label_follows_the_risk():
    run = make_run()
    labels = []
    for pressure in (0, 40, 60, 80, 100):
        run.danger = pressure
        labels.append(run.warning.name)
    assert labels[0] == "Calm" and labels[-1] == "Critical" and len(set(labels)) >= 3


def test_every_dig_adds_creak_plus_the_hardness_of_the_cells_dug():
    copper, gold = make_run(), make_run()
    force_row(copper, [COPPER] * 5)
    force_row(gold, [GOLD] * 5)
    for run in (copper, gold):
        run.rng = Rig(0.99)
        run.dig()
    assert copper.danger == pytest.approx(D.creak + D.hardness["copper_ore"])
    assert gold.danger == pytest.approx(D.creak + D.hardness["gold_ore"])
    assert gold.danger > copper.danger  # richer ore is louder


def test_digging_an_empty_cell_is_cheap_but_not_free():
    run = make_run()
    force_row(run, [None] * 5)
    run.rng = Rig(0.99)
    run.dig()
    assert run.danger == pytest.approx(D.creak + D.empty_hardness)


def test_a_slower_growth_factor_buys_more_digs():
    def digs_before_risky(factor):
        run = make_run(1, growth_factor=factor)
        n = 0
        while run.risk < 0.05 and not run.finished:
            run.rng = Rig(0.99)
            run.dig()
            n += 1
        return n

    assert digs_before_risky(0.5) > digs_before_risky(1.0)


def test_calm_never_collapses_even_on_the_worst_luck():
    run = make_run()
    assert run.risk == 0.0
    run.rng = Rig(0.0)  # random() is below any positive risk
    result = run.dig()
    assert not result.collapsed and run.depth == 1


def test_collapse_costs_part_of_the_haul_and_ends_the_run():
    run = make_run()
    run.row(0)
    run.haul = Counter(copper_ore=10, iron_ore=1)
    run.danger = 80
    run.rng = Rig(0.0)  # unlucky
    result = run.dig()
    assert result.collapsed and run.outcome == "collapse" and run.finished
    assert run.haul == Counter(copper_ore=5)  # half kept (rounded down); the lone iron is gone
    assert result.lost == Counter(copper_ore=5, iron_ore=1)
    with pytest.raises(m.MiningError):
        run.dig()


def test_lucky_digs_at_high_pressure_still_succeed():
    run = make_run()
    run.danger = 80
    run.rng = Rig(0.99)
    assert not run.dig().collapsed and run.depth == 1


def test_brace_lowers_pressure_uses_a_brace_and_does_not_descend():
    run = make_run(braces=1)
    run.danger = 40
    run.brace()
    assert run.danger == 40 - D.brace_amount and run.braces == 0 and run.depth == 0
    with pytest.raises(m.MiningError, match="out of braces"):
        run.brace()
    run2 = make_run(braces=2)
    run2.danger = 5
    run2.brace()
    assert run2.danger == 0  # never below zero


def test_leaving_keeps_everything_and_blocks_further_actions():
    run = make_run(bombs=1)
    run.haul = Counter(copper_ore=3)
    run.leave()
    assert run.outcome == "left" and run.haul == Counter(copper_ore=3)
    for action in (run.dig, run.brace, run.leave, run.bomb):
        with pytest.raises(m.MiningError):
            action()


# ---- wyrmholes, columns, cursors ------------------------------------------------------------------------
def test_breaking_into_a_wyrmhole_ends_the_run_and_keeps_the_haul():
    run = make_run()
    force_row(run, [COPPER] * 5, holes={2})
    run.haul = Counter(copper_ore=4)
    result = run.dig()
    assert result.wyrmhole and run.outcome == "wyrmhole" and run.haul == Counter(copper_ore=4) and run.depth == 0


def test_wyrmholes_can_only_hide_below_the_minimum_depth():
    deep_holes = 0
    for seed in range(60):
        run = make_run(seed, wyrmhole_odds_value=2)  # 50% per cell, to make them common
        for depth in range(10):
            run.row(depth)
            if depth < RULES.wyrmhole.min_depth:
                assert run._holes[depth] == set(), (seed, depth)
            else:
                deep_holes += len(run._holes[depth])
    assert deep_holes > 100


def test_digging_several_columns_collects_each_and_adds_each_ones_pressure():
    run = make_run(cursors=[1, 2, 3])
    force_row(run, [None, ("copper_ore", 2), ("copper_ore", 3), None, None])
    run.rng = Rig(0.99)
    result = run.dig()
    assert result.found == Counter(copper_ore=5) and run.lodes == 3 and run.history[0].dug == (1, 2, 3)
    assert run.danger == pytest.approx(D.creak + 2 * D.hardness["copper_ore"] + D.empty_hardness)


def test_cursor_movement_wraps():
    run = make_run(cursors=[4, 0])
    run.move(1)
    assert run.cursors == [0, 1]
    run.move(-1)
    assert run.cursors == [4, 0]


# ---- special cells ------------------------------------------------------------------------------------
def test_signs_show_special_cells_and_row_zero_has_no_vents_or_caches():
    run = make_run(rules=rules_with(vent_chance=1.0, rich_chance=0.0, cache_chance=0.0))
    assert set(run.signs(0)) == {"ore"}
    assert set(run.signs(1)) <= {"vent", "hole"} and "vent" in run.signs(1)
    caches = make_run(rules=rules_with(vent_chance=0.0, rich_chance=0.0, cache_chance=1.0))
    assert set(caches.signs(1)) == {"ore"} and "cache" in caches.signs(D.cache_min_depth)


def test_digging_a_vent_cools_the_tunnel_gives_no_loot_and_never_goes_below_zero():
    run = make_run(rules=rules_with(vent_chance=1.0, rich_chance=0.0, cache_chance=0.0))
    run.depth, run.danger, run.rng = 1, 30.0, Rig(0.99)
    result = run.dig()
    assert result.vented == 1 and not result.found and not run.finished
    assert run.danger == pytest.approx(30 + D.creak + D.empty_hardness - D.vent_relief)
    run.danger = 3.0
    run.dig()
    assert run.danger == 0.0


def test_digging_a_cache_gives_a_brace():
    run = make_run(rules=rules_with(vent_chance=0.0, rich_chance=0.0, cache_chance=1.0), braces=0)
    run.depth, run.rng = D.cache_min_depth, Rig(0.99)
    result = run.dig()
    assert result.caches == 1 and run.braces == D.cache_braces and not result.found


def test_rich_lodes_are_a_mystery_with_better_loot_than_the_tier_would_give():
    plain = make_run(5, rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0))
    rich = make_run(5, rules=rules_with(rich_chance=1.0, vent_chance=0.0, cache_chance=0.0))
    assert set(rich.signs(0)) == {"rich"} and set(plain.signs(0)) == {"ore"}
    cells = rich.row(0)
    assert all(c is not None for c in cells)  # never empty
    assert all(c[0] in RULES.depth_tables[1] for c in cells)  # next tier's table
    assert sum(c[1] for c in cells) > sum(c[1] for c in plain.row(0) if c)


def test_a_charged_magnet_marks_the_richest_cell_of_the_next_row():
    run = make_run(magnet=True)
    force_row(run, [None, COPPER, GOLD, None, ("copper_ore", 1)])
    assert run.best_columns() == frozenset({2})
    force_row(run, [None, COPPER, GOLD, None, ("copper_ore", 1)], holes={2})  # never points into a wyrmhole
    assert run.best_columns() == frozenset({1, 4})
    assert make_run(magnet=False).best_columns() == frozenset()


def test_the_magnet_mark_shows_on_the_map():
    from cococap.screens.mine import MAGNET, render_shaft

    run = make_run(magnet=True)
    force_row(run, [GOLD, None, None, None, None])  # (the cursor is on column 2, so mark another)
    assert MAGNET in render_shaft(run).splitlines()[0]


# ---- bombs ---------------------------------------------------------------------------------------------
def test_a_bomb_clears_the_whole_row_for_a_flat_pressure_and_skips_wyrmholes():
    run = make_run(bombs=2, cursors=[2])
    force_row(run, [COPPER, GOLD, None, COPPER, None], kinds=["ore", "ore", "ore", "ore", "vent"], holes={3})
    run.rng = Rig(0.99)
    run.danger = 30
    result = run.bomb()
    assert result.bombed and run.depth == 1 and run.bombs == 1 and run.bombs_used == 1
    assert result.found == Counter(copper_ore=1, gold_ore=1) and run.lodes == 4  # the hole was left alone
    assert run.history[0].dug == (0, 1, 2, 4)
    assert run.danger == pytest.approx(30 + D.creak + D.bomb_pressure - D.vent_relief)


def test_a_bomb_skips_the_collapse_check_even_when_the_mine_is_about_to_go():
    run = make_run(bombs=1)
    run.danger, run.rng = 95, Rig(0.0)  # the dice would collapse a normal dig
    result = run.bomb()
    assert not result.collapsed and not run.finished


def test_bombs_need_bombs():
    with pytest.raises(m.MiningError, match="no bombs"):
        make_run(bombs=0).bomb()


# ---- the floor and the vault ---------------------------------------------------------------------------
def test_digging_the_last_row_opens_the_vault():
    run = make_run(rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0, vault_gem_chance=1.0))
    run.rng = Rig(0.99)
    for _ in range(D.floor - 1):
        run.danger = 0  # keep it calm: this test is about the floor
        assert not run.dig().vault
    run.danger = 0
    result = run.dig()
    assert run.outcome == "floor" and run.depth == D.floor
    assert all(result.vault[ore] == quantity for ore, quantity in D.vault_ore.items())
    assert sum(result.vault[g] for g in RULES.reactor.core_gems) == 1
    assert all(run.haul[i] >= q for i, q in result.vault.items())
    with pytest.raises(m.MiningError):
        run.dig()


def test_a_vault_gem_is_rare_not_guaranteed():
    assert D.vault_gem_chance <= 0.05  # gems are supposed to be rare
    rules = rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0)
    gems = 0
    for seed in range(4000):
        run = make_run(seed, rules=rules)
        run.depth = D.floor - 1
        run.rng = Random(seed)
        vault = run.dig().vault
        gems += sum(vault[g] for g in RULES.reactor.core_gems)
    assert 0 < gems < 4000 * 0.08  # roughly 3%, never "every time"
    never = make_run(rules=rules_with(vault_gem_chance=0.0, rich_chance=0.0, vent_chance=0.0, cache_chance=0.0))
    never.depth, never.rng = D.floor - 1, Rig(0.99)
    vault = never.dig().vault
    assert all(vault[ore] for ore in D.vault_ore) and not any(vault[g] for g in RULES.reactor.core_gems)


def test_the_vault_holds_all_three_ores_in_proportion_to_how_often_they_drop():
    from random import Random

    from cococap.services import loot

    assert set(D.vault_ore) == {"copper_ore", "iron_ore", "gold_ore"}
    rng = Random(1)

    def per_roll(ore):  # how much of it one roll of the ore's own drop table brings, on average
        item = REG.item(ore)
        return sum(loot.skewed_roll(rng, item.drop.min, item.drop.max) for _ in range(20000)) / 20000 / item.drop.rate

    ratios = {ore: D.vault_ore[ore] / per_roll(ore) for ore in D.vault_ore}
    assert max(ratios.values()) / min(ratios.values()) < 1.15  # the rarer the ore, the fewer of it: as many "rolls" of each
    worth = sum(REG.item(ore).sell_price * q for ore, q in D.vault_ore.items())
    assert 70_000 <= worth <= 120_000  # (the ore COUNT is what was cut, to a third; the price is the flattened one)


def test_a_bomb_on_the_last_row_also_opens_the_vault():
    run = make_run(bombs=1)
    run.depth = D.floor - 1
    run.rng = Rig(0.99)
    assert run.bomb().vault and run.outcome == "floor"


# ---- why steering matters --------------------------------------------------------------------------------
def test_steering_to_the_best_cell_beats_digging_straight_down():
    calm = rules_with(max_risk=0.0)
    value = lambda run, c: (REG.item(run.row(run.depth)[c][0]).sell_price * run.row(run.depth)[c][1]) if run.row(run.depth)[c] else 0
    steered = straight = 0
    for seed in range(150):
        a, b = (make_run(seed, rules=calm) for _ in range(2))
        for _ in range(8):
            best = max(range(5), key=lambda c: (value(a, c), -abs(c - a.cursors[0])) if a.signs(a.depth)[c] != "hole" else (-1, 0))
            a.move(best - a.cursors[0])
            a.dig()
            b.dig()
        steered += sum(REG.item(i).sell_price * q for i, q in a.haul.items())
        straight += sum(REG.item(i).sell_price * q for i, q in b.haul.items())
    assert steered > straight * 1.3


def test_vents_let_a_careful_miner_keep_the_pressure_down():
    calm = rules_with(max_risk=0.0, vent_chance=0.4, rich_chance=0.0, cache_chance=0.0)

    def average_pressure(use_vents):
        total = 0.0
        for seed in range(60):
            run = make_run(seed, rules=calm)
            for _ in range(D.floor - 1):
                signs = run.signs(run.depth)
                if use_vents and run.danger >= 25 and "vent" in signs:
                    run.move(signs.index("vent") - run.cursors[0])
                elif signs[run.cursors[0]] in ("hole", "vent"):
                    rock = next((c for c, sign in enumerate(signs) if sign == "ore"), None)
                    if rock is not None:
                        run.move(rock - run.cursors[0])
                run.dig()
                if run.finished:
                    break
            total += run.danger
        return total / 60

    assert average_pressure(True) < average_pressure(False) - 10


# ---- starting, spending bombs and banking (these persist) ----------------------------------------------------
async def test_start_run_uses_reactor_braces_columns_and_carried_bombs(db):
    user = await player()
    run = await m.start_run(user, Random(1))
    assert (run.braces, run.cursors, run.growth_factor, run.yield_factor, run.bombs) == (1, [2], 1.0, 1.0, 0)
    await user.update_skill("mining", lambda s: setattr(s.reactor, "level", 11))
    run = await m.start_run(user, Random(1))
    assert run.braces == 1 + 10 // D.braces_per_reactor_levels and len(run.cursors) == 3
    assert run.growth_factor == pytest.approx(1 - D.reactor_reduction * 10)


async def test_you_carry_at_most_the_allowed_number_of_bombs_down(db):
    user = await player(scarab_bomb=D.bombs_per_run + 4)
    run = await m.start_run(user, Random(1))
    assert run.bombs == D.bombs_per_run
    assert await user.item_quantity("scarab_bomb") == D.bombs_per_run + 4  # carried, not yet spent


async def test_using_a_bomb_spends_exactly_one_from_the_inventory(db):
    user = await player(scarab_bomb=2)
    run = await m.start_run(user, Random(1))
    run.rng = Rig(0.99)
    result = await m.use_bomb(user, run)
    assert result.bombed and run.bombs == 1 and await user.item_quantity("scarab_bomb") == 1


async def test_a_bomb_you_no_longer_own_cannot_be_used(db):
    user = await player(scarab_bomb=1)
    run = await m.start_run(user, Random(1))
    await user.remove_item("scarab_bomb", 1)  # e.g. sold or used in another run
    with pytest.raises(m.MiningError, match="don't have a bomb"):
        await m.use_bomb(user, run)
    assert run.bombs == 0 and run.depth == 0


async def test_reactor_slowdown_is_capped(db):
    user = await player()
    await user.update_skill("mining", lambda s: setattr(s.reactor, "level", 100))
    assert (await m.start_run(user, Random(1))).growth_factor == pytest.approx(1 - D.max_reduction)


async def test_a_better_pickaxe_means_bigger_piles_in_a_real_run(db):
    from cococap.services.equipment import equip

    user = await player()
    pick = await user.give_instance("rookiepickaxe", rolled={"power": 4})
    await equip(user, "mining", pick.id)
    run = await m.start_run(user, Random(1))
    assert run.yield_factor == pytest.approx(1 + D.power_yield_bonus * 4)


async def test_a_full_magnet_is_spent_when_a_run_starts(db):
    user = await player()
    await user.update_skill("mining", lambda s: setattr(s, "magnet_meter", RULES.magnet.capacity))
    assert (await m.start_run(user, Random(1))).magnet
    assert (await user.skill("mining")).magnet_meter == 0
    assert not (await m.start_run(user, Random(1))).magnet


async def test_settling_banks_loot_xp_and_stats_exactly_once(db):
    user = await player()
    run = await m.start_run(user, Random(1))
    run.rng = Rig(0.99)
    for _ in range(3):
        run.dig()
    run.leave()
    first = await m.settle_run(user, run)
    again = await m.settle_run(user, run)
    assert first == again and first.xp == RULES.xp_per_column * 3 and first.outcome == "left"
    assert await user.items() == dict(run.haul)
    skill = await user.skill("mining")
    assert skill.xp == first.xp and skill.stats.lodes_mined == 3


async def test_a_collapse_still_banks_what_survived_and_the_xp(db):
    user = await player()
    run = await m.start_run(user, Random(1))
    run.rng = Rig(0.99)
    run.dig()
    run.haul = Counter(copper_ore=10)
    run.danger = 90
    run.rng = Rig(0.0)
    run.dig()
    summary = await m.settle_run(user, run)
    assert summary.outcome == "collapse" and await user.item_quantity("copper_ore") == 5
    assert (await user.skill("mining")).xp == RULES.xp_per_column


async def test_reaching_the_floor_banks_the_vault(db):
    user = await player()
    run = await m.start_run(user, Random(1))
    run.rng = Rig(0.99)
    for _ in range(D.floor):
        run.danger = 0
        run.dig()
    summary = await m.settle_run(user, run)
    assert summary.outcome == "floor" and all([await user.item_quantity(ore) >= q for ore, q in D.vault_ore.items()])


async def test_settling_an_unfinished_run_is_refused_and_abandoning_climbs_out_safely(db):
    user = await player()
    run = await m.start_run(user, Random(1))
    run.rng = Rig(0.99)
    run.dig()
    with pytest.raises(m.MiningError):
        await m.settle_run(user, run)
    await m.abandon_run(user, run)
    await m.abandon_run(user, run)
    assert run.outcome == "left" and await user.items() == dict(run.haul)


def test_rows_you_passed_keep_their_signs_for_the_cells_you_did_not_dig():
    from cococap.screens.mine import render_shaft

    run = make_run(rules=rules_with(vent_chance=0.0, rich_chance=1.0, cache_chance=0.0))
    run.cursors, run.rng = [0], Rig(0.99)
    run.dig()
    first = render_shaft(run).splitlines()[0]
    from cococap.screens.mine import _rich

    assert first.count(_rich()) == 4  # the four rich lodes you left behind are still marked


def test_cells_show_only_how_hard_the_rock_is_plus_rich_lodes_and_wyrmholes():
    from cococap.screens.mine import FIRM, HARD, SOFT, _hole, _rich, cell_emoji

    assert len({cell_emoji(f) for f in ("soft", "firm", "hard", "rich", "hole")}) == 5  # five different looks
    assert cell_emoji("soft") == SOFT and cell_emoji("firm") == FIRM and cell_emoji("hard") == HARD
    assert cell_emoji("rich") == _rich() and cell_emoji("hole") == _hole()
    assert {cell_emoji(kind) for kind in ("ore", "vent", "cache")} == {cell_emoji("ore")}  # (what is inside is not shown, only the rock)


def test_a_cell_is_revealed_once_you_dig_it():
    from cococap.screens.mine import CACHE, VENT, dug_emoji, item_emoji

    assert dug_emoji("vent", None) == VENT and dug_emoji("cache", None) == CACHE
    assert dug_emoji("ore", COPPER) == item_emoji("copper_ore")
    assert dug_emoji("ore", None) not in (VENT, CACHE, item_emoji("copper_ore"))


def test_the_map_shows_three_rows_ahead_and_a_vent_looks_like_any_other_soft_rock():
    from cococap.screens.mine import SOFT, render_shaft

    run = make_run(rules=rules_with(rich_chance=0.0, vent_chance=1.0, cache_chance=0.0))
    shaft = render_shaft(run).splitlines()
    assert len(shaft) == 1 + D.lookahead
    assert all(line.startswith(SOFT * RULES.columns) for line in shaft[1:])  # vents everywhere, all of it just soft rock: nothing gives them away
    from cococap.screens.mine import _rich

    rich = make_run(rules=rules_with(rich_chance=1.0, vent_chance=0.0, cache_chance=0.0))
    assert render_shaft(rich).splitlines()[1].startswith(_rich() * RULES.columns)  # a rich lode still stands out


def test_every_cell_feels_soft_firm_or_hard_by_how_much_pressure_it_costs_and_rich_lodes_and_holes_stand_out():
    run = make_run(rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0))
    force_row(run, [None, COPPER, ("iron_ore", 1), GOLD, ("hardwood", 1)])
    feel = run.feel(run.depth)
    assert feel[:4] == ["soft", "soft", "firm", "hard"]  # nothing and copper: soft. iron: firm. gold: hard
    assert D.hardness["copper_ore"] < D.soft_below <= D.hardness["iron_ore"] < D.hard_from <= D.hardness["gold_ore"]
    force_row(run, [GOLD] * 5, kinds=["rich", "ore", "vent", "cache", "ore"], holes={1})
    assert run.feel(run.depth)[:2] == ["rich", "hole"]
    vent_row = run.feel(run.depth)
    assert vent_row[2] == "hard"  # (the sign is irrelevant: it is the rock that is read)


def test_the_hint_is_a_real_clue_to_the_ore_and_to_the_pressure_it_costs():
    """Over many rows: hard cells hold the better ore and cost more pressure to dig, soft cells the cheaper ore."""
    worth = {"soft": [], "firm": [], "hard": []}
    pressure = {"soft": [], "firm": [], "hard": []}
    for seed in range(60):
        run = make_run(seed, rules=rules_with(rich_chance=0.0))
        for depth in range(0, D.floor):
            for feel, cell in zip(run.feel(depth), run.row(depth), strict=True):
                if feel in worth:
                    worth[feel].append(REG.item(cell[0]).sell_price * cell[1] if cell else 0)
                    pressure[feel].append(run.hardness(cell))
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    assert mean(worth["soft"]) < mean(worth["firm"]) < mean(worth["hard"])
    assert mean(pressure["soft"]) < mean(pressure["firm"]) < mean(pressure["hard"])


def test_rows_you_left_behind_still_show_the_rock_you_did_not_dig():
    from cococap.screens.mine import SOFT, render_shaft

    run = make_run(rules=rules_with(vent_chance=0.0, rich_chance=0.0, cache_chance=0.0))
    run.cursors, run.rng = [0], Rig(0.99)
    force_row(run, [None, None, None, None, None])
    run.dig()
    assert render_shaft(run).splitlines()[0].count(SOFT) == RULES.columns - 1  # the four you left are soft rock; the one you dug shows what it held


def test_the_shown_risk_is_the_real_chance_of_collapse_for_that_dig():
    for pressure in (40, 60, 80):
        collapses = 0
        trials = 20000
        for seed in range(trials):
            run = make_run(seed)
            run.danger = pressure
            shown = run.risk
            collapses += run.dig().collapsed
        assert abs(collapses / trials - shown) < 0.012, (pressure, shown, collapses / trials)


def test_the_risk_label_never_says_zero_unless_it_is_zero():
    from cococap.screens.mine import risk_text

    assert risk_text(0.0) == "0%" and risk_text(0.001) == "<1%" and risk_text(0.0049) == "<1%"
    assert risk_text(0.03) == "3%" and risk_text(0.256) == "26%"
    run = make_run()
    for pressure in range(0, 101):
        run.danger = pressure
        assert (risk_text(run.risk) == "0%") == (run.risk == 0.0)


def test_zero_risk_really_cannot_collapse():
    for seed in range(3000):
        run = make_run(seed)
        run.danger = D.safe_pressure  # the highest pressure that is still exactly zero risk
        assert run.risk == 0.0 and not run.dig().collapsed


def test_the_last_dig_is_remembered_for_the_log():
    run = make_run()
    run.danger = 50
    run.rng = Rig(0.99)
    run.dig()
    assert run.last_pressure == 50 and run.last_risk == pytest.approx(D.max_risk * (30 / 80) ** D.risk_exponent)


def test_going_deeper_is_a_real_choice_not_always_the_right_one():
    """With starting gear, leaving once the risk is 'Unstable' earns more than never leaving (and than leaving at once)."""
    def average_value(theta):
        total = 0
        for seed in range(1500):
            run = make_run(seed)
            while not run.finished:
                if run.risk >= theta:
                    if run.braces and run.danger > 10:
                        run.brace()
                        continue
                    run.leave()
                    break
                sign = run.signs(run.depth)
                if sign[run.cursors[0]] == "hole":
                    run.move(next(c for c, k in enumerate(sign) if k != "hole") - run.cursors[0])
                run.dig()
            total += sum(REG.item(i).sell_price * q for i, q in run.haul.items() if i in ("copper_ore", "iron_ore", "gold_ore"))
        return total / 1500

    cautious, balanced, reckless = average_value(0.02), average_value(0.08), average_value(1.0)
    assert balanced > cautious * 1.2 and balanced > reckless * 1.2


def test_one_vault_is_a_part_of_the_next_pickaxe_not_the_whole_of_it():
    """The reward for reaching the bottom should not pay for a pickaxe upgrade on its own: the ores it holds are a fraction of what Masterwork asks."""
    ask = REG.item("reinforced_pickaxe").tool.upgrade.items
    for ore, quantity in D.vault_ore.items():
        assert quantity <= ask[ore], ore  # never more than the whole ask of any ore...
    shares = [D.vault_ore[ore] / ask[ore] for ore in ask]
    assert min(shares) <= 0.35 and max(shares) < 1  # ...and well under half of at least one of them: it takes several trips


# ---- checkpoints: landmark rows ---------------------------------------------------------------------------------------------------
def calm_run(**kw):
    run = make_run(rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0, **kw))
    run.rng = Rig(0.99)  # no collapse, nothing lucky
    return run


def dig_to(run, rows):
    for _ in range(rows):
        run.danger = 0
        run.dig()


def test_the_milestone_rows_are_in_the_data_and_below_the_vault():
    rows = [ms.row for ms in D.milestones]
    assert rows == [10, 20] and all(r < D.floor for r in rows)


def test_finishing_a_landmark_row_makes_a_checkpoint_of_what_you_hold():
    run = calm_run()
    dig_to(run, 9)
    run.haul = Counter(copper_ore=40)
    run.danger = 0
    assert run.safe == Counter()
    result = run.dig()  # finishes row 10
    assert result.milestone is not None and result.milestone.row == 10 and run.depth == 10
    assert run.safe == Counter(run.haul) and run.safe["copper_ore"] >= 40


def test_a_collapse_after_a_checkpoint_only_costs_what_you_dug_since():
    run = calm_run()
    dig_to(run, 10)
    run.haul = Counter(copper_ore=100)
    run.safe = Counter(copper_ore=80)  # 80 are safe, 20 are at risk
    run.row(run.depth)  # (roll the row first: a rigged dice would put a wyrmhole in it)
    run.rng = Rig(0.0)
    run.danger = 100
    result = run.dig()
    assert result.collapsed and run.haul["copper_ore"] == 80 + int(20 * (1 - D.collapse_loss))
    before = calm_run()
    before.haul = Counter(copper_ore=100)
    before.row(before.depth)
    before.rng = Rig(0.0)
    before.danger = 100
    before.dig()
    assert before.haul["copper_ore"] == int(100 * (1 - D.collapse_loss))  # with no checkpoint a collapse takes its usual share of everything


def test_an_ordinary_row_is_not_a_checkpoint():
    run = calm_run()
    dig_to(run, 4)
    run.danger = 0
    result = run.dig()
    assert result.milestone is None and run.safe == Counter()


def test_milestone_rows_must_sit_in_order_above_the_floor_and_below_it():
    for bad in ([{"row": 10}, {"row": 10}], [{"row": 20}, {"row": 10}], [{"row": D.floor}], [{"row": 0}]):
        with pytest.raises(ValidationError):
            D.model_validate({**D.model_dump(), "milestones": bad})


def test_the_screen_marks_the_landmarks_and_the_vault_and_says_what_you_are_digging_toward():
    from cococap.screens import mine

    run = calm_run()
    assert "checkpoint at row 10 (10 to go)" in mine.next_landmark(run)
    run.depth = 9
    assert mine.row_mark(run, 9) == f"  {mine.MILESTONE} checkpoint" and mine.row_mark(run, 8) == ""
    assert mine.row_mark(run, D.floor - 1) == f"  {mine.VAULT} vault"
    run.depth = 25
    assert mine.next_landmark(run).startswith(mine.VAULT) and "5 to go" in mine.next_landmark(run)
    run.depth = 8  # three rows ahead are shown: rows 9, 10 and 11, and row 10 carries the flag
    shaft = mine.render_shaft(run).split("\n")
    assert any(mine.MILESTONE in line for line in shaft) and not any(mine.VAULT in line for line in shaft)
    run.depth = D.floor - 2
    assert any(mine.VAULT in line for line in mine.render_shaft(run).split("\n"))


def test_a_plain_checkpoint_gives_no_ore_and_one_with_a_vault_share_gives_that_share():
    run = calm_run()
    dig_to(run, 10)
    assert run.passed is not None and run.passed_haul == Counter()  # (it once handed out one of every ore)
    shared = calm_run(milestones=[D.milestones[0].model_copy(update={"vault_share": 0.1})])
    dig_to(shared, 10)
    assert shared.passed_haul == Counter({ore: max(1, round(q * 0.1)) for ore, q in D.vault_ore.items()})


# ---- bigger loot pools for soft, firm and hard rock -------------------------------------------------------------------------------
def rock_of(item_id):
    h = D.hardness.get(item_id, D.default_hardness)
    return "soft" if h < D.soft_below else "hard" if h >= D.hard_from else "firm"


def test_every_kind_of_rock_has_a_real_pool_of_things_to_find():
    pools = {"soft": set(), "firm": set(), "hard": set()}
    for table in RULES.depth_tables:
        for item in table:
            pools[rock_of(item)].add(item)
    assert len(pools["soft"]) >= 4 and len(pools["firm"]) >= 5 and len(pools["hard"]) >= 8, {k: sorted(v) for k, v in pools.items()}
    assert {"copper_ore", "coal", "clay", "amber"} <= pools["soft"]
    assert {"iron_ore", "tin_ore", "silver_ore", "garnet"} <= pools["firm"]
    assert {"gold_ore", "obsidian", "platinum_ore", "sapphire", "emerald"} <= pools["hard"]


def test_the_pools_open_up_as_you_go_deeper():
    sizes = [len(table) for table in RULES.depth_tables]
    assert sizes == sorted(sizes) and sizes[0] >= 4 and sizes[-1] >= 18  # the top of the mine already has more than copper
    seen = set()
    for table in RULES.depth_tables:
        assert seen <= set(table)  # nothing you could find higher up is lost lower down
        seen |= set(table)


def test_the_new_finds_all_sell_and_nothing_uses_them_yet():
    new = ("coal", "clay", "amber", "tin_ore", "silver_ore", "garnet", "obsidian", "platinum_ore", "sapphire", "emerald")
    for item_id in new:
        item = REG.item(item_id)
        assert item.skill == "mining" and item.sell_price > 0 and item.drop and item_id in D.hardness
    used = {i for t in REG.items.values() if t.tool and t.tool.upgrade for i in t.tool.upgrade.items}
    assert not set(new) & used  # (they are for selling for now; crafting will find a use later)


def test_in_each_pool_the_harder_rock_holds_the_better_stuff():
    worth = {"soft": set(), "firm": set(), "hard": set()}
    for table in RULES.depth_tables[:3]:  # (above the gems and the spirit, which would swamp the comparison)
        for item in table:
            worth[rock_of(item)].add((item, REG.item(item).sell_price))
    median = lambda pairs: sorted(p for _, p in pairs)[len(pairs) // 2]  # noqa: E731  (a median: one rare amber should not drag soft rock up)
    assert median(worth["soft"]) < median(worth["firm"]) < median(worth["hard"])
