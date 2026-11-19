"""Starred materials are wired into foraging and fishing: each drop is starred by how deep the forest or water is."""

from collections import Counter
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import fishing as f
from cococap.services import foraging as fg
from cococap.services import stars
from cococap.user import User
from tests.test_fishing import T0, cast_of

REG = get_registry()
RULES = REG.foraging
HARDWOOD = "material_hardwood"  # starrable in economy.toml
CORAL = "material_coral_shard"  # starrable in economy.toml


@pytest.fixture
def spy_apply(monkeypatch):
    """Record the depth each apply call is given; the real apply still runs (with a roll near the top of the curve)."""
    real = stars.apply
    depths: list[float] = []

    def spy(drops, at, rng, registry=None):
        depths.append(at)
        return real(drops, at, rng, registry)

    monkeypatch.setattr(stars, "apply", spy)
    return depths


async def test_felling_a_tree_stars_its_drops_by_forest_depth(db, monkeypatch, spy_apply):
    monkeypatch.setattr(fg, "roll_drops", lambda *a, **k: Counter({HARDWOOD: 5}))

    for zone in (1, RULES.zones):
        user = await User.get(zone)
        tree = fg.Tree(zone, 100, 100)
        tree.chop(100, 1.0)
        reward = await fg.fell_private(user, tree, Random(3), REG)
        assert sum(reward.drops.values()) == 5
        assert all(REG.find_item(i) for i in reward.drops)
    assert spy_apply[0] == stars.progress(1, RULES.zones) == 0.0
    assert spy_apply[1] == stars.progress(RULES.zones, RULES.zones) == 1.0


async def test_a_felled_forest_drop_lands_as_the_star_apply_chose(db, monkeypatch):
    monkeypatch.setattr(fg, "roll_drops", lambda *a, **k: Counter({HARDWOOD: 5}))
    top = _TopRoll()
    real = stars.apply
    monkeypatch.setattr(stars, "apply", lambda drops, at, rng, registry=None: real(drops, at, top, registry))
    user = await User.get(2)
    tree = fg.Tree(RULES.zones, 100, 100)
    tree.chop(100, 1.0)
    reward = await fg.fell_private(user, tree, Random(3), REG)
    star = stars.star_id(HARDWOOD, 3) if stars.weights(1.0)[3] > 0 else stars.star_id(HARDWOOD, 2)
    assert reward.drops == Counter({star: 5})
    assert await user.item_quantity(star) == 5


class _TopRoll:
    """An rng that always rolls the highest band (the deepest forest has 3-star weight, so this gives the top star)."""

    def random(self) -> float:
        return 0.999999


async def test_landing_a_catch_stars_its_extras_by_water_depth(db, monkeypatch, spy_apply):
    monkeypatch.setattr(f, "catch_extras", lambda rng, reg: Counter({CORAL: 2}))
    waters = REG.fishing.waters
    for water in (waters[0], waters[-1]):
        user = await User.get(3 if water is waters[0] else 4)
        cast = cast_of("fish_cod")
        cast.water = water
        for arrow in cast.pattern:
            cast.press(arrow, T0 + 11)
        await f.land(user, cast, REG)
        held = [await user.item_quantity(stars.star_id(CORAL, n)) for n in range(4)]  # plain + 1/2/3-star
        assert sum(held) == 2
    assert spy_apply == [stars.progress(1, len(waters)), stars.progress(len(waters), len(waters))] == [0.0, 1.0]
