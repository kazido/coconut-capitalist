"""Star quality of starrable drops: the curve in economy.toml, never the majority at 3 stars, deeper = better."""

import random
from collections import Counter

import pytest

from cococap.registry import RegistryError, get_registry, load_registry
from cococap.services import stars

REG = get_registry()
CURVE = REG.economy.stars.curve
DEPTHS = [i / 20 for i in range(21)]


def test_weights_add_up_and_the_start_has_no_three_star():
    assert all(abs(sum(stars.weights(d)) - 1) < 1e-9 for d in DEPTHS)
    assert stars.weights(0.0)[2] == 0 and stars.weights(0.0)[0] > 0.9  # the first forest is nearly all plain


def test_three_star_is_never_the_majority_and_two_star_leads_from_the_middle():
    for d in DEPTHS:
        one, two, three = stars.weights(d)
        assert three < 0.5 and three < two + one  # never the main drop
        if d >= 0.5:
            assert two > 0.5 or two > one and two > three, d  # 2-star is the main drop from the middle on
    assert stars.weights(0.5)[1] > stars.weights(0.5)[0]


def test_deeper_never_makes_stars_rarer():
    prev = (1.0, 0.0, 0.0)
    for d in DEPTHS:
        one, two, three = stars.weights(d)
        assert one <= prev[0] + 1e-9 and three >= prev[2] - 1e-9
        prev = (one, two, three)


def test_the_roll_follows_the_weights():
    rng = random.Random(1)
    for d in (0.0, 0.5, 1.0):
        n = 20_000
        got = [0, 0, 0]
        for _ in range(n):
            got[stars.roll_stars(d, rng) - 1] += 1
        for share, want in zip((g / n for g in got), stars.weights(d), strict=True):
            assert abs(share - want) < 0.02, (d, share, want)


def test_only_starrable_items_change_id():
    rng = random.Random(2)
    assert all(stars.roll_item("material_copper_ore", 1.0, rng) == "material_copper_ore" for _ in range(200))  # not starrable
    seen = {stars.roll_item("material_gold_ore", 1.0, rng) for _ in range(500)}
    assert seen == {"material_gold_ore", "material_gold_ore_s2", "material_gold_ore_s3"}
    assert {stars.roll_item("material_gold_ore", 0.0, rng) for _ in range(500)} == {"material_gold_ore", "material_gold_ore_s2"}  # no 3-star at the start
    assert all(REG.find_item(i) for i in seen)  # every id it can return is a real item


def test_progress_maps_a_step_onto_zero_to_one():
    assert stars.progress(1, 20) == 0 and stars.progress(20, 20) == 1 and stars.progress(1, 1) == 0
    assert stars.progress(10, 20) < 0.5 < stars.progress(11, 20)


def test_a_curve_with_a_majority_three_star_is_refused(tmp_path):
    import shutil

    from cococap.registry.loader import CONFIG_DIR

    shutil.copytree(CONFIG_DIR, tmp_path / "c")
    path = tmp_path / "c" / "economy.toml"
    path.write_text(path.read_text().replace("weights = [15, 65, 20]", "weights = [10, 30, 60]"))
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
    """A roll that lands in the 2-star band or above, the top one that exists at this depth (3-star only when it has weight)."""
    w = stars.weights(at)
    return (1.0 + w[0] + w[1]) / 2 if w[2] > 0 else 1.0 - w[1] / 2


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
    assert stars.weights(0.0)[2] == 0  # the curve has no 3-star at the start
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
