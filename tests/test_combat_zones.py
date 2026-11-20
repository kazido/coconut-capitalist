"""Combat zones: one per combat location, who you meet there, and who may walk in."""

import random

import pytest

from cococap.registry import get_registry
from cococap.services import combat
from cococap.user import User

REG = get_registry()


def test_there_is_one_zone_per_combat_location_in_order():
    locs = [loc.id for loc in REG.locations["combat"]]
    assert len(locs) == 14 and list(REG.combat.zones) == locs and locs[0] == "graveyard"


def test_every_zone_enemy_has_a_drop_table():
    for zone in REG.combat.zones.values():
        for eid in [*zone.enemies, *([zone.rare] if zone.rare else [])]:
            assert REG.enemies[eid].drops in REG.drop_tables, (zone.id, eid)


def test_roll_foes_respects_max_foes_and_the_rare_comes_alone():
    zone = next(z for z in REG.combat.zones.values() if z.rare)
    seen = set()
    for seed in range(200):
        foes = combat.roll_foes(zone.id, rng=random.Random(seed))
        seen.add(len(foes))
        assert 1 <= len(foes) <= zone.max_foes and (foes == [zone.rare] or set(foes) <= set(zone.enemies))
    assert len(seen) > 1

    class Forced(random.Random):
        def randint(self, a, b):
            return 1  # always under rare_chance

    assert combat.roll_foes(zone.id, rng=Forced()) == [zone.rare]


async def test_explore_refuses_a_closed_zone_and_opens_zone_one(db):
    user = await User.get(1)
    with pytest.raises(combat.CombatError, match="not open"):
        await combat.explore(user, REG.locations["combat"][-1].id)
    battle = await combat.explore(user, "graveyard")
    assert battle.living("enemy") and all(f.hp == f.max_hp for f in battle.living("enemy"))
