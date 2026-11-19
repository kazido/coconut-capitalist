"""Star quality of starrable drops: the curve in economy.toml, never the majority at 3 stars, deeper = better."""

import random
from collections import Counter

import pytest

from cococap.registry import RegistryError, get_registry, load_registry
from cococap.services import stars

REG = get_registry()
CURVE = REG.economy.stars.curve
DEPTHS = [i / 20 for i in range(21)]


def _ids_with_weight(base: str, at: float) -> set[str]:
    """The inventory ids a starrable drop can take at this depth: only the tiers the curve gives weight to."""
    return {stars.star_id(base, n) for n, w in enumerate(stars.weights(at)) if w > 0}


def test_weights_add_up_and_the_start_has_no_two_or_three_star():
    assert all(abs(sum(stars.weights(d)) - 1) < 1e-9 for d in DEPTHS)
    start = stars.weights(0.0)
    assert len(start) == 4 and start[2] == 0 and start[3] == 0  # the first forest gives no 2- or 3-star
    assert start[0] > 0.9  # and is nearly all plain


def test_three_star_is_never_the_majority_and_plain_leads_at_the_start():
    for d in DEPTHS:
        assert stars.weights(d)[3] < 0.5  # 3-star is never the main drop
    start = stars.weights(0.0)
    assert start.index(max(start)) == 0  # plain is the most common at the top of the list
    mid = stars.weights(0.5)
    assert mid[1] > mid[2] > mid[3]  # among the stars, 1-star is the usual one in the middle (plain can still lead)


def test_deeper_never_makes_stars_rarer():
    prev = stars.weights(0.0)
    for d in DEPTHS:
        w = stars.weights(d)
        assert w[0] <= prev[0] + 1e-9 and w[3] >= prev[3] - 1e-9
        prev = w


def test_the_roll_follows_the_weights():
    rng = random.Random(1)
    for d in (0.0, 0.5, 1.0):
        n = 20_000
        got = [0, 0, 0, 0]
        for _ in range(n):
            got[stars.roll_stars(d, rng)] += 1
        for share, want in zip((g / n for g in got), stars.weights(d), strict=True):
            assert abs(share - want) < 0.02, (d, share, want)


def test_only_starrable_items_change_id():
    rng = random.Random(2)
    assert all(stars.roll_item("material_copper_ore", 1.0, rng) == "material_copper_ore" for _ in range(200))  # not starrable
    gold = "material_gold_ore"
    seen = {stars.roll_item(gold, 1.0, rng) for _ in range(500)}
    assert seen == _ids_with_weight(gold, 1.0) == {stars.star_id(gold, n) for n in range(4)}
    assert {stars.roll_item(gold, 0.0, rng) for _ in range(500)} == _ids_with_weight(gold, 0.0)  # no 2- or 3-star at the start
    assert all(REG.find_item(i) for i in seen)  # every id it can return is a real item


def test_progress_maps_a_step_onto_zero_to_one():
    assert stars.progress(1, 20) == 0 and stars.progress(20, 20) == 1 and stars.progress(1, 1) == 0
    assert stars.progress(10, 20) < 0.5 < stars.progress(11, 20)


def test_a_curve_with_a_majority_three_star_is_refused(tmp_path):
    import shutil

    from cococap.registry.loader import CONFIG_DIR

    shutil.copytree(CONFIG_DIR, tmp_path / "c")
    path = tmp_path / "c" / "economy.toml"
    # swap the deepest anchor for one where 3-star is the majority (the last "weights = [...]" line in the curve)
    text = path.read_text()
    head, _, _ = text.rpartition("weights = [")
    tail = text[len(head) :].split("]", 1)[1]
    path.write_text(head + "weights = [10, 20, 20, 50]" + tail)
    with pytest.raises(RegistryError, match="majority"):
        load_registry(tmp_path / "c")


# ---- apply: a whole drop bundle at once ----------------------------------------------------------------------------
class _Fixed:
    """An rng whose every roll is the same number: forces the tier band it falls in."""

    def __init__(self, x: float):
        self.x = x

    def random(self) -> float:
        return self.x


def _top_band_x(at: float) -> float:
    """A roll just under 1: the highest tier that has any weight at this depth (the cumulative pick ends at the top)."""
    return 0.999999


def test_apply_leaves_non_starrable_drops_alone():
    drops = Counter({"material_copper_ore": 3, "fish_cod": 2})
    assert stars.apply(drops, 1.0, random.Random(4), REG) == drops


def test_apply_conserves_counts():
    starrable = REG.economy.stars.starrable
    drops = Counter({starrable[0]: 5, starrable[1]: 3, "material_copper_ore": 2})
    for seed in range(50):
        out = stars.apply(drops, 0.5, random.Random(seed), REG)
        assert sum(out.values()) == sum(drops.values())
        assert all(REG.find_item(i) for i in out)


def test_apply_at_the_deepest_depth_can_give_a_higher_star():
    gold = REG.economy.stars.starrable[0]
    got = {k for seed in range(500) for k in stars.apply(Counter({gold: 1}), 1.0, random.Random(seed), REG)}
    assert got & {stars.star_id(gold, 2), stars.star_id(gold, 3)}
    assert stars.apply(Counter({gold: 1}), 1.0, _Fixed(_top_band_x(1.0)), REG) != Counter({gold: 1})


def test_apply_at_the_start_never_gives_three_star():
    gold = REG.economy.stars.starrable[0]
    assert stars.weights(0.0)[3] == 0  # the curve has no 3-star at the start
    for seed in range(500):
        out = stars.apply(Counter({gold: 1}), 0.0, random.Random(seed), REG)
        assert stars.star_id(gold, 3) not in out


def test_apply_gives_the_whole_stack_one_star():
    gold = REG.economy.stars.starrable[0]
    for seed in range(30):
        out = stars.apply(Counter({gold: 7}), 0.6, random.Random(seed), REG)
        assert len(out) == 1 and sum(out.values()) == 7


def test_apply_is_deterministic_for_a_seed():
    starrable = REG.economy.stars.starrable
    drops = Counter({starrable[0]: 4, starrable[1]: 2, "material_copper_ore": 1})
    first = stars.apply(drops, 0.6, random.Random(9), REG)
    assert all(stars.apply(drops, 0.6, random.Random(9), REG) == first for _ in range(3))


def test_the_first_mine_gives_no_two_or_three_star_and_mine_five_is_all_but_no_three_star():
    mines = len(REG.mining.mines)
    first = stars.weights(stars.progress(1, mines))
    assert first[2] == 0 and first[3] == 0  # mine 1: plain and 1-star only
    # mine 5 is still almost 3-star-free (the curve's 3-star ramp starts just before it): under 1%, not exactly zero
    assert stars.weights(stars.progress(5, mines))[3] < 0.01
