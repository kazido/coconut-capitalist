from cococap.models.pethouse import OwnedPet
from cococap.registry import get_registry
from cococap.services import pet_score as ps

REG = get_registry()


def _pet(rarity=None):
    return next(p for p in REG.pets.values() if p.skill != "global" and (rarity is None or p.rarity == rarity))


def test_score_rises_with_level_stars_and_lent_tool():
    pet = _pet()
    lo = OwnedPet(xp=0, stars=1)
    hi_xp = OwnedPet(xp=10**9, stars=1)
    assert ps.score(pet, hi_xp) > ps.score(pet, lo)
    assert ps.score(pet, OwnedPet(xp=0, stars=3)) > ps.score(pet, lo)
    assert ps.score(pet, lo, lent_tool_power=10) > ps.score(pet, lo)


def test_global_pet_scores_below_a_specialist_with_the_same_kit():
    pet = _pet()
    glob = pet.model_copy(update={"skill": "global"})
    o = OwnedPet(xp=10**9, stars=1)
    assert ps.score(glob, o) < ps.score(pet, o)


def test_sidekick_capped_and_empty_tank_stops_haul_but_not_passive():
    pet = _pet()
    o = OwnedPet(xp=10**9, stars=5)
    many = [(pet, o)] * 500
    assert ps.sidekick_bonus(many) == REG.pet_score.sidekick_cap
    assert ps.sidekick_bonus([]) == 0
    s = ps.score(pet, o)
    assert ps.haul_xp_per_hour(s, fueled=False) == 0
    assert ps.passive_bonus(s) > 0
    assert ps.passive_bonus(10**9) == REG.pet_score.passive_cap
    assert ps.haul_xp_per_hour(s, active_xp_per_hour=100) <= 100 * REG.pet_score.haul_active_share


def test_old_pethouse_json_loads_with_empty_tank():
    from cococap.models.pethouse import Pethouse

    house = Pethouse.model_validate({"active": "cinder", "pets": {"cinder": {"stars": 2, "xp": 50}}, "curve_version": 1})
    assert house.fuel_seconds == 0 and house.last_collect == 0
    assert house.pets["cinder"].lent_tool is None and house.pets["cinder"].buff_until == 0
    assert house.pets["cinder"].stars == 2 and house.pets["cinder"].xp == 50
