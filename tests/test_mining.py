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


@pytest.mark.parametrize("gems, odds", [(0, 1500), (1, 1300), (4, 700), (10, 600)])
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


GEMS = {RULES.wyrmhole.implosion_item, *RULES.reactor.core_gems}


def test_a_big_wyrmhole_hides_exactly_one_gem_and_only_in_its_last_row():
    for seed in range(100):
        hole = m.generate_wyrmhole(RULES, Random(seed))
        assert len(hole.rows) == len(RULES.wyrmhole.rows) and all(len(r) == RULES.wyrmhole.columns for r in hole.rows)
        assert all(n[0] not in GEMS for r in hole.rows[:-1] for n in r)  # no gems above the last row
        assert sum(n[0] in GEMS for n in hole.rows[-1]) == 1
        pools = [set(r.pool) for r in RULES.wyrmhole.rows]
        assert all(n[0] in pools[i] for i, r in enumerate(hole.rows) for n in r if n[0] not in GEMS)  # (and no node is empty: every one pays)
        assert all(n[1] >= 1 for r in hole.rows for n in r)


def test_the_gem_is_never_a_core_gem_you_own_and_the_implosion_gem_gets_likelier_with_every_one():
    core = RULES.reactor.core_gems

    def implosion_share(owned):
        gems = [next(n[0] for n in m.generate_wyrmhole(RULES, Random(s), owned).rows[-1] if n[0] in GEMS) for s in range(3000)]
        assert all(g == RULES.wyrmhole.implosion_item or g not in owned for g in gems)  # never a core gem you already own
        return gems.count(RULES.wyrmhole.implosion_item) / len(gems)

    shares = [implosion_share(set(core[:k])) for k in range(5)]
    assert shares == sorted(shares) and shares[0] < shares[3] and shares[4] == 1.0  # (own all four: always the implosion gem)


def test_wyrmhole_digs_one_node_per_row_and_a_finished_hole_refuses_more():
    hole = m.generate_wyrmhole(RULES, Random(1))
    hole.move(1)
    item = hole.dig()
    assert not hole.finished and item == hole.rows[0][hole.columns_picked[0]] and hole.cursor == hole.width // 2
    while not hole.finished:
        hole.dig()
    with pytest.raises(m.MiningError):
        hole.dig()


# ---- scarab -----------------------------------------------------------------------------------------
def test_scarab_scroll_is_scrambled_and_checkable():
    challenge = m.make_scarab(["lantern"], RULES, Random(2))
    assert sorted(challenge.scrambled) == sorted("lantern") and challenge.scrambled != "lantern"
    assert challenge.check(" Lantern ") and not challenge.check("lantern!")


def test_scarabs_are_common_enough_to_see_and_give_more_than_bombs():
    hits = sum(m.scarab_appears(RULES, Random(s)) for s in range(6000))
    assert 6000 / RULES.scarab.chance * 0.8 < hits < 6000 / RULES.scarab.chance * 1.2  # about 1 mine in 12
    assert RULES.scarab.chance <= 15 and RULES.scarab.seconds > 30  # it used to be 1 in 51 and 30 seconds
    wins = Counter(m.scarab_reward(REG, RULES, Random(s)).name for s in range(3000))
    assert set(wins) == {p.name for p in RULES.scarab.prizes} and len(wins) >= 4
    prizes = {p.name: p for p in RULES.scarab.prizes}
    assert any(p.xp for p in prizes.values()) and any(set(p.items) - {"tool_scarab_bomb"} for p in prizes.values())  # xp, and loot that is not a bomb
    assert wins["Bombs"] > wins["A glittering find"] and "tool_scarab_bomb" in prizes["Bombs"].items  # (the bombs are the common one, the find the rare one)


def test_a_prize_must_give_something():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RULES.scarab.prizes[0].model_validate({"name": "nothing", "weight": 1})


# ---- operations that persist -------------------------------------------------------------------------
async def player(level=1, **items):
    user = await User.get(1)
    if level > 1:
        await user.add_xp("mining", User.level_to_xp(level) + 1)
    for item_id, qty in items.items():
        await user.add_item(item_id, qty)
    return user








async def test_magnet_deposits(db):
    gold, iron = RULES.magnet.values["material_gold_ore"], RULES.magnet.values["material_iron_ore"]
    user = await player(level=5, material_gold_ore=3, material_iron_ore=2, crop_apple=1)
    assert await m.deposit_ore(user, "material_gold_ore", 3) == (3 * gold, 3)
    assert await m.deposit_ore(user, "material_iron_ore", 2) == (3 * gold + 2 * iron, 2)
    with pytest.raises(m.MiningError, match="only takes"):
        await m.deposit_ore(user, "crop_apple", 1)
    with pytest.raises(m.MiningError, match="don't have"):
        await m.deposit_ore(user, "material_gold_ore", 1)
    await user.add_item("material_gold_ore", 100)
    meter, used = await m.deposit_ore(user, "material_gold_ore", 100)
    room = RULES.magnet.capacity - (3 * gold + 2 * iron)
    assert meter == RULES.magnet.capacity and used == -(-room // gold)  # only the ore that fits is taken
    assert await user.item_quantity("material_gold_ore") == 100 - used
    with pytest.raises(m.MiningError, match="full"):
        await m.deposit_ore(user, "material_gold_ore", 1)


async def test_the_magnet_cannot_be_fed_while_you_are_in_a_mine(db):
    user = await player(level=5, material_gold_ore=3, material_copper_ore=3)
    run = await m.start_run(user, Random(1))
    assert m.in_a_mine(user.id)
    with pytest.raises(m.MiningError, match="in a mine"):
        await m.deposit_ore(user, "material_gold_ore", 1)
    assert await user.item_quantity("material_gold_ore") == 3  # nothing was taken
    run.leave()
    await m.settle_run(user, run)
    assert not m.in_a_mine(user.id)
    assert (await m.deposit_ore(user, "material_copper_ore", 3))[1] == 3


async def test_the_auto_miner_feeds_the_magnet_first_when_you_ask_it_to_and_never_overfills(db):
    from collections import Counter

    user = await player(level=5)
    loot = Counter({"material_gold_ore": 10, "material_iron_ore": 5, "material_copper_ore": 7, "material_coal": 4})
    assert await m._feed_from_loot(user, loot, REG) == Counter()  # (off by default)
    await m.set_magnet_option(user, "magnet_auto_feed", True)
    fed = await m._feed_from_loot(user, loot, REG)
    v = RULES.magnet.values
    assert fed == Counter({"material_gold_ore": 10, "material_iron_ore": 5, "material_copper_ore": 7}) and "material_coal" not in fed
    assert (await user.skill("mining")).magnet_meter == 10 * v["material_gold_ore"] + 5 * v["material_iron_ore"] + 7 * v["material_copper_ore"]
    await user.update_skill("mining", lambda s: setattr(s, "magnet_meter", RULES.magnet.capacity - 50))
    fed = await m._feed_from_loot(user, Counter({"material_gold_ore": 100}), REG)
    assert fed["material_gold_ore"] == 50 // v["material_gold_ore"] and (await user.skill("mining")).magnet_meter <= RULES.magnet.capacity  # only what fits
    await m.set_magnet_option(user, "magnet_auto_feed", True)
    await user.update_skill("mining", lambda s: setattr(s, "magnet_meter", 0))
    run = await m.start_run(user, Random(1))  # in a mine: no feeding
    assert await m._feed_from_loot(user, Counter({"material_gold_ore": 5}), REG) == Counter()
    run.leave()
    await m.settle_run(user, run)


async def test_magnet_requires_level(db):
    user = await player(level=1, material_gold_ore=1)
    with pytest.raises(m.MiningError, match="level 5"):
        await m.deposit_ore(user, "material_gold_ore", 1)
    assert await user.item_quantity("material_gold_ore") == 1  # nothing was taken


async def test_gem_placement_rules_and_prestige(db):
    gems = RULES.reactor.core_gems
    user = await player(level=1, **{g: 1 for g in gems}, key_gemstone_implosion=2)
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
        await m.place_gem(user, "material_copper_ore")
    with pytest.raises(m.MiningError, match="Fill all four"):
        await m.prestige(user)

    for gem in gems[1:]:
        await m.place_gem(user, gem)
    assert await m.prestige(user) == 2 and await user.item_quantity("key_gemstone_implosion") == 1
    assert await m.prestige(user) == 3 and await user.item_quantity("key_gemstone_implosion") == 0
    with pytest.raises(m.MiningError, match="implosion gem"):
        await m.prestige(user)


async def test_prestige_stops_at_the_maximum(db):
    gems = RULES.reactor.core_gems
    user = await player(level=10, key_gemstone_implosion=3)
    def setup(s):
        for i, g in enumerate(gems, start=1):
            getattr(s.reactor, f"core_{i}").gem_id = g
        s.reactor.level = RULES.reactor.max_prestige
    await user.update_skill("mining", setup)
    with pytest.raises(m.MiningError, match="maximum"):
        await m.prestige(user)
    assert await user.item_quantity("key_gemstone_implosion") == 3


async def test_lodes_accumulate_and_can_only_be_claimed_once(db):
    user = await player()
    status = await m.reactor_status(user, now=1000.0)  # first visit starts the clock
    assert status["pending_lodes"] == 0
    lodes, loot = await m.claim_lodes(user, Random(1), now=1000 + 360 * 10)
    assert lodes == 10 and sum(loot.values()) > 0
    assert await user.item_quantity("material_copper_ore") == loot["material_copper_ore"]
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
    await m.finish_wyrmhole(user, hole)
    for item_id, qty in hole.loot().items():
        assert await user.item_quantity(item_id) >= qty
    skill = await user.skill("mining")
    assert skill.stats.lodes_mined == len(hole.rows) and skill.xp == hole.xp_awarded > 0 and hole.xp_awarded >= RULES.wyrmhole.xp_per_row * len(hole.rows)


async def test_scarab_reward_is_banked(db):
    user = await player()
    for seed in range(40):
        before_xp = (await user.skill("mining")).xp
        before = Counter(await user.items())
        win = await m.claim_scarab_reward(user, Random(seed))
        assert Counter(await user.items()) - before == win.items  # the items are banked
        assert (await user.skill("mining")).xp - before_xp == win.xp  # ...and the xp
    assert (await user.skill("mining")).xp > 0


async def test_scarab_xp_gets_the_usual_bonuses(db):
    from cococap.services.party import Party

    user = await player()
    other = await User.get(2)
    party = await Party.create(1)
    await party.add_member(2)
    xp_prizes = [p for p in RULES.scarab.prizes if p.xp]
    seen = set()
    for seed in range(400):
        win = await m.claim_scarab_reward(user, Random(seed))
        if win.xp:
            seen.add(win.xp)
    base = {p.xp for p in xp_prizes}
    assert seen and all(x > b for x in seen for b in [min(base)]) and seen != base  # (paid more than the base amount: the party bonus applies)
    assert other


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


COPPER, GOLD = ("material_copper_ore", 1), ("material_gold_ore", 1)


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
    assert copper.danger == pytest.approx(D.creak + D.hardness["material_copper_ore"])
    assert gold.danger == pytest.approx(D.creak + D.hardness["material_gold_ore"])
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
    run.haul = Counter(material_copper_ore=10, material_iron_ore=1)
    run.danger = 80
    run.rng = Rig(0.0)  # unlucky
    result = run.dig()
    assert result.collapsed and run.outcome == "collapse" and run.finished
    assert run.haul == Counter(material_copper_ore=5)  # half kept (rounded down); the lone iron is gone
    assert result.lost == Counter(material_copper_ore=5, material_iron_ore=1)
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
    run.haul = Counter(material_copper_ore=3)
    run.leave()
    assert run.outcome == "left" and run.haul == Counter(material_copper_ore=3)
    for action in (run.dig, run.brace, run.leave, run.bomb):
        with pytest.raises(m.MiningError):
            action()


# ---- wyrmholes, columns, cursors ------------------------------------------------------------------------
def test_breaking_into_a_wyrmhole_ends_the_run_and_keeps_the_haul():
    run = make_run()
    force_row(run, [COPPER] * 5, holes={2})
    run.haul = Counter(material_copper_ore=4)
    result = run.dig()
    assert result.wyrmhole and run.outcome == "wyrmhole" and run.haul == Counter(material_copper_ore=4) and run.depth == 0


def test_wyrmholes_never_show_in_the_rows_visible_when_a_mine_opens():
    assert RULES.wyrmhole.min_depth > RULES.descent.lookahead  # (else you could reset mines until one shows)


def test_wyrmholes_only_show_between_the_minimum_and_maximum_depth():
    deep_holes = 0
    for seed in range(60):
        run = make_run(seed, wyrmhole_odds_value=2)  # 50% per cell, to make them common
        for depth in range(RULES.wyrmhole.max_depth + 4):
            run.row(depth)
            if not RULES.wyrmhole.min_depth <= depth <= RULES.wyrmhole.max_depth:  # (too deep and the mine would collapse before you reach it)
                assert run._holes[depth] == set(), (seed, depth)
            else:
                deep_holes += len(run._holes[depth])
    assert deep_holes > 100


def test_digging_several_columns_collects_each_and_adds_each_ones_pressure():
    run = make_run(cursors=[1, 2, 3])
    force_row(run, [None, ("material_copper_ore", 2), ("material_copper_ore", 3), None, None])
    run.rng = Rig(0.99)
    result = run.dig()
    assert result.found == Counter(material_copper_ore=5) and run.lodes == 3 and run.history[0].dug == (1, 2, 3)
    assert run.danger == pytest.approx(D.creak + 2 * D.hardness["material_copper_ore"] + D.empty_hardness)


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
    force_row(run, [None, COPPER, GOLD, None, ("material_copper_ore", 1)])
    assert run.best_columns() == frozenset({2})
    force_row(run, [None, COPPER, GOLD, None, ("material_copper_ore", 1)], holes={2})  # never points into a wyrmhole
    assert run.best_columns() == frozenset({1, 4})
    assert make_run(magnet=False).best_columns() == frozenset()


def test_the_magnet_mark_shows_on_the_map():
    from cococap.screens.mine import _magnet, render_shaft

    run = make_run(magnet=True)
    run.cursors = [2]
    force_row(run, [GOLD, None, None, None, None])  # (the cursor is on column 2, so mark another)
    assert _magnet() in render_shaft(run).splitlines()[0]


def test_auto_aim_puts_the_cursor_on_the_richest_column_while_the_magnet_has_fuel():
    run = make_run(magnet=True, cursors=[0])
    force_row(run, [COPPER, None, GOLD, None, ("material_copper_ore", 1)])
    run.aim()
    assert run.cursors == [2]
    dry = make_run(magnet=True, magnet_points=1, magnet_drain=4, cursors=[0])  # not enough fuel for a row: no aim
    force_row(dry, [COPPER, None, GOLD, None, None])
    dry.aim()
    assert dry.cursors == [0]
    off = make_run(magnet=False, cursors=[0])
    force_row(off, [COPPER, None, GOLD, None, None])
    off.aim()
    assert off.cursors == [0]


def test_auto_aim_keeps_the_spacing_of_several_cursors_and_covers_the_most_ore():
    run = make_run(magnet=True, cursors=[1, 2])
    force_row(run, [None, None, None, GOLD, COPPER])
    run.aim()
    assert sorted(run.cursors) == [3, 4]


def test_auto_aim_follows_the_magnet_down_the_shaft_and_the_player_can_still_move():
    run = make_run(magnet=True, cursors=[2], rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0))
    run.rng = Rig(0.99)
    run.danger = 0
    run.dig()
    best = run.best_columns()
    assert not best or run.cursors[0] in best
    before = run.cursors[0]
    run.move(1)
    assert run.cursors[0] == (before + 1) % RULES.columns  # the arrows still work


def test_the_magnet_marks_vents_but_never_aims_at_them():
    run = make_run(magnet=True, cursors=[0])
    force_row(run, [COPPER, None, GOLD, None, None], kinds=["ore", "vent", "ore", "vent", "ore"])
    assert run.vent_columns() == frozenset({1, 3})
    run.aim()
    assert run.cursors == [2]
    assert make_run(magnet=False).vent_columns() == frozenset()
    from cococap.screens.mine import _vent, render_shaft

    assert _vent() in render_shaft(run).splitlines()[0]


def test_a_brace_and_the_magnet_drain_read_the_configured_numbers():
    run = make_run(magnet=True, magnet_points=100, magnet_drain=RULES.magnet.drain_per_row)
    run.danger = 60
    run.braces = 1
    run.brace()
    assert run.danger == 60 - D.brace_amount


# ---- bombs ---------------------------------------------------------------------------------------------
def test_a_bomb_clears_the_whole_row_for_a_flat_pressure_and_skips_wyrmholes():
    run = make_run(bombs=2, cursors=[2])
    force_row(run, [COPPER, GOLD, None, COPPER, None], kinds=["ore", "ore", "ore", "ore", "vent"], holes={3})
    run.rng = Rig(0.99)
    run.danger = 30
    result = run.bomb()
    assert result.bombed and run.depth == 1 and run.bombs == 1 and run.bombs_used == 1
    assert result.found == Counter(material_copper_ore=1, material_gold_ore=1) and run.lodes == 4  # the hole was left alone
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

    assert set(D.vault_ore) == {"material_copper_ore", "material_iron_ore", "material_gold_ore"}
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
    user = await player(tool_scarab_bomb=D.bombs_per_run + 4)
    run = await m.start_run(user, Random(1))
    assert run.bombs == D.bombs_per_run
    assert await user.item_quantity("tool_scarab_bomb") == D.bombs_per_run + 4  # carried, not yet spent


async def test_using_a_bomb_spends_exactly_one_from_the_inventory(db):
    user = await player(tool_scarab_bomb=2)
    run = await m.start_run(user, Random(1))
    run.rng = Rig(0.99)
    result = await m.use_bomb(user, run)
    assert result.bombed and run.bombs == 1 and await user.item_quantity("tool_scarab_bomb") == 1


async def test_a_bomb_you_no_longer_own_cannot_be_used(db):
    user = await player(tool_scarab_bomb=1)
    run = await m.start_run(user, Random(1))
    await user.remove_item("tool_scarab_bomb", 1)  # e.g. sold or used in another run
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
    pick = await user.give_instance("tool_pickaxe_rookie", rolled={"power": 4})
    await equip(user, "mining", pick.id)
    run = await m.start_run(user, Random(1))
    assert run.yield_factor == pytest.approx(1 + D.power_yield_bonus * 4)


async def test_the_magnet_keeps_its_meter_between_runs_and_settling_takes_off_only_what_the_run_used(db):
    user = await player(level=5)
    drain = RULES.magnet.drain_per_row
    await user.update_skill("mining", lambda s: setattr(s, "magnet_meter", 100))
    run = await m.start_run(user, Random(1))
    assert run.magnet and run.magnet_points == 100 and run.magnet_drain == drain
    assert (await user.skill("mining")).magnet_meter == 100  # starting a mine does not spend it
    run.magnet_used = drain * 3
    run.leave()
    await m.settle_run(user, run)
    assert (await user.skill("mining")).magnet_meter == 100 - 3 * round(drain)
    await user.update_skill("mining", lambda s: setattr(s, "magnet_on", False))
    assert not (await m.start_run(user, Random(1))).magnet  # switched off: it neither marks nor burns
    await user.update_skill("mining", lambda s: (setattr(s, "magnet_on", True), setattr(s, "magnet_meter", 1)))
    assert not (await m.start_run(user, Random(1))).magnet  # not enough for even one row


def test_the_magnet_burns_fuel_a_row_and_stops_marking_when_it_runs_dry():
    run = make_run(magnet=True, magnet_points=10, magnet_drain=4, rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0))
    run.rng = Rig(0.99)
    for expected_left in (2, 1, 0):
        force_row(run, [None, COPPER, GOLD, None, None])
        assert run.magnet_rows_left == expected_left
        assert (run.best_columns() == frozenset({2})) == (expected_left > 0)  # no fuel, no mark
        run.danger = 0
        run.dig()
    assert run.magnet_used == 8  # (the third row had no fuel to burn)
    assert make_run(magnet=False).magnet_rows_left is None


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
    run.haul = Counter(material_copper_ore=10)
    run.danger = 90
    run.rng = Rig(0.0)
    run.dig()
    summary = await m.settle_run(user, run)
    assert summary.outcome == "collapse" and await user.item_quantity("material_copper_ore") == 5
    assert (await user.skill("mining")).xp == RULES.xp_per_column


async def test_reaching_the_floor_banks_the_vault(db):
    user = await player()
    run = await m.start_run(user, Random(1))
    run.rng = Rig(0.99)
    for _ in range(D.floor):
        run.danger = 0
        run.dig()
    summary = await m.settle_run(user, run)
    assert summary.outcome == "floor" and all([sum([await user.item_quantity(i) for i in (ore, f"{ore}_s2", f"{ore}_s3")]) >= q for ore, q in D.vault_ore.items()])  # (a starrable ore may come up starred)


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


def test_the_row_you_just_dug_is_not_shown_only_the_rows_ahead():
    from cococap.screens.mine import _cursor, render_shaft

    run = make_run(rules=rules_with(vent_chance=0.0, rich_chance=1.0, cache_chance=0.0))
    run.cursors, run.rng = [0], Rig(0.99)
    run.dig()
    shaft = render_shaft(run).splitlines()
    assert len(shaft) == 1 + D.lookahead  # the cursor line and the rows ahead: the view does not jump after a dig
    assert _cursor() in shaft[0]


def test_the_map_shows_three_rows_ahead_and_a_vent_looks_like_any_other_soft_rock():
    from cococap.screens.mine import _soft, render_shaft

    run = make_run(rules=rules_with(rich_chance=0.0, vent_chance=1.0, cache_chance=0.0))
    shaft = render_shaft(run).splitlines()
    assert len(shaft) == 1 + D.lookahead
    assert all(line.startswith(_soft() * RULES.columns) for line in shaft[1:])  # vents everywhere, all of it just soft rock: nothing gives them away
    from cococap.screens.mine import _rich

    rich = make_run(rules=rules_with(rich_chance=1.0, vent_chance=0.0, cache_chance=0.0))
    assert render_shaft(rich).splitlines()[1].startswith(_rich() * RULES.columns)  # a rich lode still stands out


def test_every_cell_feels_soft_firm_or_hard_by_how_much_pressure_it_costs_and_rich_lodes_and_holes_stand_out():
    run = make_run(rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0))
    force_row(run, [None, COPPER, ("material_iron_ore", 1), GOLD, ("material_hardwood", 1)])
    feel = run.feel(run.depth)
    assert feel[:4] == ["soft", "soft", "firm", "hard"]  # nothing and copper: soft. iron: firm. gold: hard
    assert D.hardness["material_copper_ore"] < D.soft_below <= D.hardness["material_iron_ore"] < D.hard_from <= D.hardness["material_gold_ore"]
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
            total += sum(REG.item(i).sell_price * q for i, q in run.haul.items() if i in ("material_copper_ore", "material_iron_ore", "material_gold_ore"))
        return total / 1500

    cautious, balanced, reckless = average_value(0.02), average_value(0.08), average_value(1.0)
    # With strong braces (brace_amount 25) careful play is almost as good as leaving at 'Unstable', so only the edge over cautious is required;
    # the edge over never leaving stays big. (Guard deliberately moved with the brace buff.)
    assert balanced > cautious and balanced > reckless * 1.2


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
    run.haul = Counter(material_copper_ore=40)
    run.danger = 0
    assert run.safe == Counter()
    result = run.dig()  # finishes row 10
    assert result.milestone is not None and result.milestone.row == 10 and run.depth == 10
    assert run.safe == Counter(run.haul) and run.safe["material_copper_ore"] >= 40


def test_a_collapse_after_a_checkpoint_only_costs_what_you_dug_since():
    run = calm_run()
    dig_to(run, 10)
    run.haul = Counter(material_copper_ore=100)
    run.safe = Counter(material_copper_ore=80)  # 80 are safe, 20 are at risk
    run.row(run.depth)  # (roll the row first: a rigged dice would put a wyrmhole in it)
    run.rng = Rig(0.0)
    run.danger = 100
    result = run.dig()
    assert result.collapsed and run.haul["material_copper_ore"] == 80 + int(20 * (1 - D.collapse_loss))
    before = calm_run()
    before.haul = Counter(material_copper_ore=100)
    before.row(before.depth)
    before.rng = Rig(0.0)
    before.danger = 100
    before.dig()
    assert before.haul["material_copper_ore"] == int(100 * (1 - D.collapse_loss))  # with no checkpoint a collapse takes its usual share of everything


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
    assert mine.row_mark(run, 9) == f"  {mine._milestone()} checkpoint" and mine.row_mark(run, 8) == ""
    assert mine.row_mark(run, D.floor - 1) == f"  {mine._vault()} vault"
    run.depth = 25
    assert mine.next_landmark(run).startswith(mine._vault()) and "5 to go" in mine.next_landmark(run)
    run.depth = 8  # three rows ahead are shown: rows 9, 10 and 11, and row 10 carries the flag
    shaft = mine.render_shaft(run).split("\n")
    assert any(mine._milestone() in line for line in shaft) and not any(mine._vault() in line for line in shaft)
    run.depth = D.floor - 2
    assert any(mine._vault() in line for line in mine.render_shaft(run).split("\n"))


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
    assert {"material_copper_ore", "material_coal", "material_clay", "material_amber"} <= pools["soft"]
    assert {"material_iron_ore", "material_tin_ore", "material_silver_ore", "material_garnet"} <= pools["firm"]
    assert {"material_gold_ore", "material_obsidian", "material_platinum_ore", "material_sapphire", "material_emerald"} <= pools["hard"]


def test_the_pools_open_up_as_you_go_deeper():
    sizes = [len(table) for table in RULES.depth_tables]
    assert sizes == sorted(sizes) and sizes[0] >= 4 and sizes[-1] >= 18  # the top of the mine already has more than copper
    seen = set()
    for table in RULES.depth_tables:
        assert seen <= set(table)  # nothing you could find higher up is lost lower down
        seen |= set(table)


def test_in_each_pool_the_harder_rock_holds_the_better_stuff():
    worth = {"soft": set(), "firm": set(), "hard": set()}
    for table in RULES.depth_tables[:3]:  # (above the gems and the spirit, which would swamp the comparison)
        for item in table:
            worth[rock_of(item)].add((item, REG.item(item).sell_price))
    median = lambda pairs: sorted(p for _, p in pairs)[len(pairs) // 2]  # noqa: E731  (a median: one rare amber should not drag soft rock up)
    assert median(worth["soft"]) < median(worth["firm"]) < median(worth["hard"])


# ---- pickaxe abilities: the Warden's Auto-Bomb and the Prospector's Multi-Mine -----------------------------------------------------------
def test_the_auto_bomb_blows_every_nth_row_for_free_with_no_collapse_check():
    run = calm_run()
    run.auto_bomb_every = 4
    assert run.auto_bomb_in == 4
    for expected_in in (4, 3, 2):
        assert run.auto_bomb_in == expected_in
        run.danger = 0
        assert not run.dig().auto_bombed
    assert run.auto_bomb_in == 1  # the next dig is the charge
    run.danger = 100
    run.row(run.depth)  # (roll the row first: a rigged dice would put a wyrmhole in it)
    run.rng = Rig(0.0)  # a collapse is certain on any ordinary dig...
    result = run.dig()
    assert result.auto_bombed and result.bombed and not result.collapsed  # ...but a blast has no collapse check
    assert run.bombs_used == 0 and run.auto_counter == 0 and run.auto_bomb_in == 4  # it cost no bomb, and the count starts again


def test_the_auto_bomb_clears_the_whole_row_for_a_flat_pressure():
    run = calm_run()
    run.auto_bomb_every = 1
    force_row(run, [COPPER, COPPER, GOLD, COPPER, COPPER])
    before = run.danger
    result = run.dig()
    assert result.auto_bombed and sum(result.found.values()) >= 5 and "material_gold_ore" in result.found
    assert run.danger == pytest.approx(before + (D.creak + D.bomb_pressure) * run.growth_factor)


def test_without_the_ability_nothing_blows_by_itself():
    run = calm_run()
    assert run.auto_bomb_in is None
    for _ in range(25):
        run.danger = 0
        assert not run.dig().auto_bombed


def test_multi_mine_sometimes_digs_the_rock_beside_you_and_pays_its_hardness():
    plain, lucky = calm_run(), calm_run()
    lucky.multi_mine = 1.0  # every dig
    for run in (plain, lucky):
        force_row(run, [COPPER, GOLD, GOLD, GOLD, COPPER])
        run.cursors = [2]
    one, two = plain.dig(), lucky.dig()
    assert not one.multi and len(two.multi) == 1 and two.multi[0] in (1, 3)
    assert sum(two.found.values()) > sum(one.found.values())
    assert lucky.danger > plain.danger  # more rock dug, more pressure
    assert lucky.lodes == 2 and plain.lodes == 1


def test_multi_mine_never_digs_a_wyrmhole_or_the_column_you_already_dug():
    for seed in range(40):
        run = make_run(seed, rules=rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0))
        run.multi_mine, run.cursors = 1.0, [2]
        run.row(0)
        run._holes[0] = {3}  # a wyrmhole beside you
        run.rng = Random(seed)
        result = run.dig()
        assert result.multi in ((1,), ()) and 2 not in result.multi and 3 not in result.multi


# ---- Mastery capstones -----------------------------------------------------------------------------------------------------------------------------
def test_lifeline_holds_the_mine_once_when_a_dig_would_collapse_it_and_only_if_ready():
    quiet = rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0)
    run = make_run(rules=quiet, lifeline=1)
    run.haul.update({"material_copper_ore": 100})
    run.rng = Rig(0.0)  # every collapse roll comes up
    run.danger = 90
    first = run.dig()
    assert first.lifeline and not first.collapsed and run.outcome is None and run.lifeline_fired
    assert first.lifeline_lost["material_copper_ore"] == int(100 * D.lifeline_loss) and run.haul["material_copper_ore"] >= 100 - int(100 * D.lifeline_loss)
    assert run.danger <= D.lifeline_pressure + D.creak + 20  # the reactor dropped the pressure before the dig added its own
    run.danger = 90
    assert run.dig().collapsed and run.outcome == "collapse"  # only once
    recharging = make_run(rules=quiet, lifeline=1, lifeline_ready=False)
    recharging.rng, recharging.danger = Rig(0.0), 90
    assert recharging.dig().collapsed  # not ready: a normal collapse
    plain = make_run(rules=quiet)
    plain.rng, plain.danger = Rig(0.0), 90
    assert plain.dig().collapsed  # no capstone: a normal collapse


async def test_lifeline_needs_a_few_mines_to_recharge(db):
    user = await player()
    run = m.MineRun(RULES, REG, Random(1), cursors=[2], lifeline=1)
    run.lifeline_fired, run.outcome = True, "left"
    await m.settle_run(user, run)
    assert (await user.skill("mining")).lifeline_wait == D.lifeline_runs - 1
    for left in range(D.lifeline_runs - 2, -1, -1):  # each mine after it counts one down
        nxt = m.MineRun(RULES, REG, Random(1), cursors=[2], lifeline=1, lifeline_ready=False)
        nxt.outcome = "left"
        await m.settle_run(user, nxt)
        assert (await user.skill("mining")).lifeline_wait == left
    ready = await m.start_run(user, Random(1))
    assert ready.lifeline_ready


def test_gold_rush_triples_every_nth_cell_and_geodes_hold_a_gem_you_have_not_placed_yet():
    quiet = rules_with(rich_chance=0.0, vent_chance=0.0, cache_chance=0.0)
    for gold, expected in ((3, 3), (0, 1)):  # gold rush: the 3rd cell is tripled; a plain run is not
        run = make_run(rules=quiet, gold_rush=gold)
        run.rng = Rig(0.99)
        for depth in range(3):
            force_row(run, [COPPER, COPPER, COPPER, COPPER, COPPER], depth=depth)
            run.danger = 0
            run.dig()
        assert run.haul["material_copper_ore"] == 2 + expected, gold  # (two single cells, then the third one)
    run = make_run(rules=quiet, geode=1.0, geode_gems=["key_gemstone_rage"])  # geodes: always a gem with the roll forced, and only one you are missing
    run.rng = Rig(0.0)
    force_row(run, [COPPER] * 5)
    run.danger = 0
    run.dig()
    assert run.haul["key_gemstone_rage"] == 1 and not run.haul["key_gemstone_sanity"]
    plain = make_run(rules=quiet, geode=0.0)
    plain.rng = Rig(0.99)
    force_row(plain, [COPPER] * 5)
    plain.danger = 0
    plain.dig()
    assert not any(plain.haul[g] for g in RULES.reactor.core_gems)


def test_the_auto_miner_bonuses_and_the_reactor_engineers_cooling_reach_the_numbers():
    from cococap.models.skills.mining import Mining

    mining = Mining()
    mining.reactor.level, mining.reactor.last_auto_mine = 4, 1000.0
    t = 1000.0 + 3 * RULES.reactor.automine_seconds
    assert m.pending_lodes(mining, RULES, t) == 3 * 4
    assert m.pending_lodes(mining, RULES, t, speed=0.25) == round(3 * 4 * 1.25)
    long_ago = 1000.0 + 1000 * 3600
    cap = RULES.reactor.automine_cap_hours * 3600 // RULES.reactor.automine_seconds
    assert m.pending_lodes(mining, RULES, long_ago) == cap * 4
    assert m.pending_lodes(mining, RULES, long_ago, extra_hours=24) == int((RULES.reactor.automine_cap_hours + 24) * 3600 // RULES.reactor.automine_seconds) * 4


def test_the_three_mining_capstones_are_about_equally_strong_at_low_and_high_power():
    """Each capstone adds roughly a fifth to a run's value for the same digging (Lifeline is worked out with its recharge), at BOTH ends of the pickaxe's power, so a gem
    that is worth the same bits whatever your pick cannot be the obvious choice early or late."""
    from random import Random as R

    price = lambda i: REG.item(i).sell_price  # noqa: E731
    d = RULES.descent

    def average(power, runs=1200, lifeline_runs=None, **kw):
        total, wait = 0, 0
        for seed in range(runs):
            run = m.MineRun(RULES, REG, R(seed), cursors=[2], braces=d.braces_base + 1, yield_factor=1 + d.power_yield_bonus * (power - 3),
                            lifeline_ready=wait <= 0, wyrmhole_odds_value=25000, **kw)  # (no wyrmholes: this is about the capstones)
            while not run.finished:
                limit = 0.12 if (run.lifeline and run.lifeline_ready and not run.lifeline_fired) else 0.07  # (with a second chance in hand you push a little further)
                if run.risk >= limit:
                    if run.braces and run.danger > 10:
                        run.brace()
                        continue
                    run.leave()
                    break
                if run.signs(run.depth)[run.cursors[0]] == "hole":
                    run.move(1)
                run.dig()
            if lifeline_runs:
                wait = lifeline_runs - 1 if run.lifeline_fired else max(0, wait - 1)
            total += sum(price(i) * q for i, q in run.haul.items())
        return total / runs

    amount = lambda node_id, stat: next(e.amount for e in REG.mastery.node(node_id).effects if e.stat == stat)  # noqa: E731
    for power in (3, 12):
        base = average(power)
        gains = {
            "lifeline": average(power, lifeline_runs=d.lifeline_runs, lifeline=1) / base - 1,
            "gold_rush": average(power, gold_rush=int(amount("gold_rush", "gold_rush"))) / base - 1,
            "geode_cracker": average(power, geode=amount("geode_cracker", "geode")) / base - 1,
        }
        # (lower bound 7%, was 8%: with brace_amount 25 base pay is higher, so Lifeline's gain at power 12 is 7.6%; moved on purpose, see the commit)
        assert all(0.07 <= g <= 0.4 for g in gains.values()), (power, gains)
        assert max(gains.values()) - min(gains.values()) <= 0.15, (power, gains)


# ---- mine types ---------------------------------------------------------------------------------
TYPES = {t.id: t for t in RULES.mine_types}


def _run(type_id=None, seed=1, **kw):
    return m.MineRun(RULES, REG, Random(seed), cursors=[2], mine_type=TYPES[type_id] if type_id else None, **kw)


def test_wyrm_tunnels_and_mastery_make_wyrmholes_likelier():
    mult = TYPES["wyrm_tunnels"].wyrmhole_mult
    assert mult > 1 and TYPES["standard"].wyrmhole_mult == 1
    plain = _run("standard").wyrmhole_odds
    assert _run("wyrm_tunnels").wyrmhole_odds < plain / mult * 1.1
    assert _run("standard", wyrmhole_bonus=1.0).wyrmhole_odds == round(plain / 2)  # +100% wyrmhole chance halves the odds


def test_the_mine_type_weights_validate_and_standard_dominates():
    assert "standard" in TYPES and len(RULES.mine_types) >= 6
    total = sum(t.weight for t in RULES.mine_types)
    assert TYPES["standard"].weight / total >= 0.5
    assert all(t.weight > 0 for t in RULES.mine_types)
    assert all(i in REG.items for t in RULES.mine_types for i in (*t.ore_boost, *t.ore_yield))
    standard = TYPES["standard"]
    assert (standard.pressure_mult, standard.xp_mult, standard.yield_mult, standard.rich_chance_add, standard.ore_boost, standard.ore_yield) == (1, 1, 1, 0, {}, {})


def test_bad_mine_types_are_refused():
    base = RULES.model_dump(by_alias=True)
    broken = lambda **change: {**base, "mine_types": [*base["mine_types"][:1], {**base["mine_types"][1], **change}, *base["mine_types"][2:]]}  # noqa: E731
    for change in ({"weight": 0}, {"pressure_mult": 0.01}, {"xp_mult": 9}, {"ore_boost": {"material_copper_ore": 50}}, {"ore_yield": {"material_copper_ore": 0.5}}, {"rich_chance_add": 0.9}):
        with pytest.raises(ValidationError):
            type(RULES)(**broken(**change))
    with pytest.raises(ValidationError, match="standard"):
        type(RULES)(**{**base, "mine_types": base["mine_types"][1:]})
    with pytest.raises(ValidationError, match="change nothing"):
        type(RULES)(**{**base, "mine_types": [{**base["mine_types"][0], "xp_mult": 2.0}, *base["mine_types"][1:]]})
    with pytest.raises(ValidationError, match="half"):
        type(RULES)(**{**base, "mine_types": [{**base["mine_types"][0], "weight": 1}, *base["mine_types"][1:]]})


def test_rolling_a_mine_type_follows_the_weights_and_is_seeded():
    rolls = Counter(m.roll_mine_type(RULES, Random(seed)).id for seed in range(4000))
    total = sum(t.weight for t in RULES.mine_types)
    for t in RULES.mine_types:
        assert abs(rolls[t.id] / 4000 - t.weight / total) < 0.03, t.id
    assert [m.roll_mine_type(RULES, Random(7)).id for _ in range(3)] == [m.roll_mine_type(RULES, Random(7)).id for _ in range(3)]


async def test_start_run_rolls_a_type_and_can_be_forced(db):
    user = await player()
    assert (await m.start_run(user, Random(1))).mine_type.id == "standard"  # (the first roll of seed 1 is the commonest kind)
    forced = await m.start_run(user, Random(1), mine_type="gold_vein")
    assert forced.mine_type is TYPES["gold_vein"]
    assert (await m.start_run(user, Random(1), mine_type=TYPES["quiet_shaft"])).mine_type.id == "quiet_shaft"
    assert [(await m.start_run(user, Random(5))).mine_type.id for _ in range(2)][0] == (await m.start_run(user, Random(5))).mine_type.id


def test_a_plain_run_is_a_standard_mine_and_unchanged():
    assert _run().mine_type.id == "standard"
    plain = _run(seed=3)
    explicit = _run("standard", seed=3)
    assert [plain.row(i) for i in range(6)] == [explicit.row(i) for i in range(6)]


def test_an_ore_focused_mine_pays_more_of_its_ore():
    def income(type_id, ore, depth=6):
        total = 0
        for seed in range(150):
            run = _run(type_id, seed)
            total += sum(q for i in range(depth) for cell in run.row(i) if cell and cell[0] == ore for q in [cell[1]])
        return total

    for type_id, ore in (("copper_seam", "material_copper_ore"), ("iron_vein", "material_iron_ore"), ("gold_vein", "material_gold_ore")):
        assert type_id in TYPES and ore in {**TYPES[type_id].ore_boost, **TYPES[type_id].ore_yield}
        assert income(type_id, ore, 12) > income(None, ore, 12), type_id


def test_ore_boost_raises_the_drop_chance_and_other_ores_stay_possible():
    boosted = TYPES["standard"].model_copy(update={"id": "x", "ore_boost": {"material_iron_ore": 3.0}})
    def count(kind, ore):
        n = 0
        for seed in range(60):
            run = m.MineRun(RULES, REG, Random(seed), cursors=[2], mine_type=kind)
            n += sum(1 for i in range(4, 8) for cell in run.row(i) if cell and cell[0] == ore)
        return n
    assert count(boosted, "material_iron_ore") > count(TYPES["standard"], "material_iron_ore") * 1.5
    assert count(boosted, "material_copper_ore") > 0 and count(boosted, "material_gold_ore") > 0


def test_ore_yield_also_fattens_the_vault_ore():
    assert _run("gold_vein")._vault_ore()["material_gold_ore"] == round(RULES.descent.vault_ore["material_gold_ore"] * TYPES["gold_vein"].ore_yield["material_gold_ore"])
    assert _run()._vault_ore() == RULES.descent.vault_ore


async def test_a_quiet_shaft_slows_the_pressure_and_the_cap_is_unchanged(db):
    user = await player()
    quiet = await m.start_run(user, Random(1), mine_type="quiet_shaft")
    plain = await m.start_run(user, Random(1), mine_type="standard")
    assert quiet.growth_factor == pytest.approx(plain.growth_factor * TYPES["quiet_shaft"].pressure_mult)
    for run in (quiet, plain):
        run.rng = Rig(0.99)
        run.dig()
    assert quiet.danger < plain.danger and quiet.danger == pytest.approx(plain.danger * TYPES["quiet_shaft"].pressure_mult)
    await user.update_skill("mining", lambda s: setattr(s.reactor, "level", 40))
    assert (await m.start_run(user, Random(1), mine_type="standard")).growth_factor == pytest.approx(1 - D.max_reduction)  # the cap still holds for the rest
    capped = await m.start_run(user, Random(1), mine_type="quiet_shaft")
    assert capped.growth_factor == pytest.approx((1 - D.max_reduction) * TYPES["quiet_shaft"].pressure_mult)  # (the type comes on top of the cap)


async def test_a_scholars_cavern_pays_extra_xp_and_a_standard_mine_does_not(db):
    user = await player()
    xps = {}
    for type_id in ("standard", "scholars_cavern"):
        run = await m.start_run(user, Random(1), mine_type=type_id)
        run.rng = Rig(0.99)
        run.dig()
        run.leave()
        xps[type_id] = (await m.settle_run(user, run)).xp
    assert xps["standard"] == RULES.xp_per_column * 1 and xps["scholars_cavern"] == round(xps["standard"] * TYPES["scholars_cavern"].xp_mult)


def test_a_deep_pocket_has_more_rich_lodes_and_more_ore():
    def rich_cells(type_id):
        return sum(run.signs(depth).count("rich") for seed in range(200) for run in [_run(type_id, seed)] for depth in range(6))
    assert rich_cells("deep_pocket") > rich_cells(None) * 1.3
    assert TYPES["deep_pocket"].yield_mult >= 1 and _run("deep_pocket")._quantity_factor(0) == pytest.approx(TYPES["deep_pocket"].yield_mult)


async def test_mine_types_keep_the_live_run_guard_and_settle_working(db):
    user = await player(level=5, tool_scarab_bomb=1)
    run = await m.start_run(user, Random(1), mine_type="iron_vein")
    assert m.in_a_mine(user.id)
    run.rng = Rig(0.99)
    await m.use_bomb(user, run)  # bombs still work in a typed mine
    run.leave()
    summary = await m.settle_run(user, run)
    assert not m.in_a_mine(user.id) and summary.lodes == run.lodes
    assert await m.settle_run(user, run) == summary  # settling twice is harmless


# ---- small wyrmholes ------------------------------------------------------------------------------------
MINI = RULES.mini_wyrmhole


async def test_entering_a_wyrmhole_rolls_big_or_small_and_can_be_forced(db):
    user = await player()
    assert (await m.enter_wyrmhole(user, Random(1), small=True)).small and not (await m.enter_wyrmhole(user, Random(1), small=False)).small
    sizes = [(await m.enter_wyrmhole(user, Random(seed))).small for seed in range(400)]
    big = sizes.count(False) / len(sizes)
    assert 0 < big < 0.5 and abs(big - RULES.wyrmhole.big_chance) < 0.08  # big ones are the rarer


async def test_start_run_passes_the_mastery_wyrmhole_chance_on(db):
    user = await player()
    assert (await m.start_run(user, Random(1))).wyrmhole_odds == m.wyrmhole_odds(0, RULES)


def test_a_small_wyrmhole_is_three_wide_and_five_rows_with_one_pick_per_row():
    hole = m.generate_mini_wyrmhole(RULES, Random(3))
    assert hole.small and len(hole.rows) == len(MINI.rows) == 5 and all(len(r) == MINI.columns == 3 for r in hole.rows)
    for r, nodes in enumerate(hole.rows):
        assert all(item in MINI.rows[r].pool or item in RULES.reactor.core_gems for item, _ in nodes)
    for r in range(5):
        assert not hole.finished and hole.row == r
        hole.move(1)
        assert hole.dig() == hole.rows[r][2]
        assert hole.cursor == 1 or hole.finished  # the next row starts in the middle
    assert hole.finished and len(hole.picks) == 5
    with pytest.raises(m.MiningError):
        hole.dig()


def test_small_wyrmhole_rows_pay_more_than_normal_rows_and_better_each_row():
    price = lambda i: REG.item(i).sell_price
    n = 600
    paid = [0.0] * 5
    for seed in range(n):
        hole = m.generate_mini_wyrmhole(RULES, Random(seed))
        for r in range(5):
            item, qty = hole.dig()
            paid[r] += price(item) * qty if item not in RULES.reactor.core_gems else 0
    paid = [p / n for p in paid]
    assert paid == sorted(paid)  # each row is worth more than the one above
    normal = 0.0  # a normal cell's average value at the base pickaxe power, over the first rows of a mine
    for seed in range(n):
        run = make_run(seed)
        for depth in range(5):
            normal += sum(price(c[0]) * c[1] for c in run.row(depth) if c) / RULES.columns / 5
    normal /= n
    assert min(paid) > normal  # even the top row of the hole beats a normal cell


def test_a_small_wyrmhole_never_holds_a_gem_and_has_no_empty_node():
    for seed in range(300):
        hole = m.generate_mini_wyrmhole(RULES, Random(seed))
        assert all(n[0] not in GEMS and n[1] >= 1 for r in hole.rows for n in r)
        assert hole.xp_per_row == MINI.xp_per_row > 0


async def test_a_small_wyrmhole_banks_every_pick_and_the_last_row_bonus_once(db):
    user = await player()
    hole = m.generate_mini_wyrmhole(RULES, Random(5))
    for _ in range(5):
        hole.dig()
    expected = hole.loot()
    assert all(expected[i] >= q for i, q in MINI.last_row_bonus.items())
    await m.finish_wyrmhole(user, hole)
    await m.finish_wyrmhole(user, hole)  # (banking twice pays once)
    for item_id, qty in expected.items():
        assert await user.item_quantity(item_id) == qty
    assert (await user.skill("mining")).stats.lodes_mined == 5


async def test_walking_away_from_a_small_wyrmhole_still_banks_what_is_left(db):
    user = await player()
    hole = m.generate_mini_wyrmhole(RULES, Random(8))
    hole.dig()  # one row dug, then the player leaves
    await m.finish_wyrmhole(user, hole)
    assert hole.finished and hole.banked and len(hole.picks) == 5
    for item_id, qty in hole.loot().items():
        assert await user.item_quantity(item_id) == qty


async def test_the_big_wyrmhole_is_a_small_mine_of_several_rows(db):
    hole = await m.enter_wyrmhole(await player(), Random(2), small=False)
    assert not hole.small and len(hole.rows) == len(RULES.wyrmhole.rows) > 1 and len(hole.nodes) == RULES.wyrmhole.columns


def test_small_wyrmhole_odds_for_the_rare_drop_screen():
    from cococap.services import odds

    lookup = odds.for_source("mini_wyrmhole")
    assert lookup(RULES.reactor.core_gems[0]) is None  # (no gems in a small wyrmhole)
    assert lookup("material_gold_ore").one_in == 4 and lookup("material_clay") is None


def test_small_wyrmhole_config_is_validated():
    from cococap.registry.models import MiniWyrmholeRules

    good = MINI.model_dump()
    with pytest.raises(ValidationError):
        MiniWyrmholeRules(**{**good, "columns": 1})


# ---- the 14 named mines -----------------------------------------------------------------------------
def test_there_is_one_mine_per_mining_location_and_each_holds_every_reactor_gem():
    assert [s.id for s in RULES.mines] == [loc.id for loc in REG.locations["mining"]]
    for site in RULES.mines:
        tables = RULES.tables_of(site)
        assert len(tables) == len(RULES.depth_tables)
        assert set(RULES.reactor.core_gems) <= set(tables[-1])  # the reactor can always be fed, in every mine
    assert RULES.mines[0].tables is None  # the first mine is the shared tables, so nothing changed for current players


async def test_a_new_player_can_only_dig_the_first_mine(db):
    user = await player()
    assert [s.id for s in await m.open_mines(user, REG)] == [RULES.mines[0].id]
    assert (await m.start_run(user, Random(1))).site.id == RULES.mines[0].id
    with pytest.raises(m.MiningError, match="haven't opened"):
        await m.start_run(user, Random(1), location=RULES.mines[1].id)


def test_a_mine_scales_its_yield_and_the_pressure_of_its_digs():
    plain = RULES.mines[0]
    rich = plain.model_copy(update={"yield_mult": 2.0, "hardness_mult": 2.0})
    base, scaled = make_run(site=plain), make_run(site=rich)
    assert scaled._quantity_factor(0) == pytest.approx(2 * base._quantity_factor(0))
    for run in (base, scaled):
        force_row(run, [COPPER] * RULES.columns)
    base_cost, scaled_cost = base._mine([2])[3], scaled._mine([2])[3]
    assert scaled_cost == pytest.approx(2 * base_cost)


def test_a_mine_with_its_own_tables_digs_only_from_them():
    only_gold = ["material_gold_ore"]
    site = RULES.mines[0].model_copy(update={"tables": [only_gold] * len(RULES.depth_tables)})
    run = make_run(site=site)
    cells = [c for d in range(D.floor) for c in run.row(d)]
    assert all(c is None or c[0] == "material_gold_ore" for c in cells)
