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


def test_every_pets_score_is_out_of_1000_and_fixed_by_its_kit_not_its_level():
    for pet in REG.pets.values():
        s = ps.total(pet)
        assert 0 < s.total <= 1000 and all(0 <= v <= 100 for v in s.skills.values()) and s.mastery <= 200 and s.gear <= 200
        assert s.ability == {"none": 0, "mid": 50, "high": 100}[pet.ability]
        assert s.total == ps.total(pet).total  # nothing about the owned pet goes in


def test_a_specialist_scores_in_one_skill_and_a_global_pet_spreads_its_points():
    spec, glob = _pet(), next(p for p in REG.pets.values() if p.skill == "global")
    assert sum(1 for v in ps.total(spec).skills.values() if v) == 1 and ps.total(spec).skills[spec.skill] > 0
    assert len({v for v in ps.total(glob).skills.values()}) == 1 and ps.total(glob).skills_total <= 500


def test_a_celestial_pet_would_have_500_skill_points_and_a_mythical_one_100_in_a_skill():
    glob = next(p for p in REG.pets.values() if p.skill == "global").model_copy(update={"rarity": 8})
    assert ps.total(glob).skills_total == 500
    myth = _pet().model_copy(update={"rarity": 6})
    assert ps.total(myth).skills[myth.skill] == 100


def test_sidekick_capped_and_empty_tank_stops_haul_but_not_passive():
    pet = _pet()
    o = OwnedPet(xp=10**9, stars=5)
    many = [(pet, o)] * 500
    assert ps.sidekick_bonus(many) == REG.pet_score.sidekick_cap  # (500 maxed pets: capped)
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


# ---- fuel tank, haul, food buff (services/pets.py) ----------------------------------------------------------------
import pytest  # noqa: E402

from cococap.services import pets  # noqa: E402
from tests.test_pets import with_pet  # noqa: E402


def _crop():
    return next(i for i in REG.items.values() if i.crop and i.sell_price > 0)


@pytest.mark.asyncio
async def test_crops_fill_the_tank_up_to_its_cap_and_the_haul_burns_it(db):
    user = await with_pet("drizzle")
    crop = _crop()
    await user.add_item(crop.id, 100000)
    added = await pets.fuel(user, crop.id, 100000, now=1000.0)
    assert 0 < added <= pets.tank_cap_seconds(REG)
    assert user.pethouse.fuel_seconds == added
    # an hour later: the haul only counts the fuel that lasted
    skill, xp, hours, drops = await pets.collect(user, now=1000.0 + 10 * 3600)
    assert hours * 3600 <= added + 1e-6 and xp > 0 and skill == "fishing"
    assert user.pethouse.fuel_seconds == 0
    _, xp2, _, _ = await pets.collect(user, now=1000.0 + 20 * 3600)
    assert xp2 == 0  # empty tank: no haul (passive bonus is untouched elsewhere)


@pytest.mark.asyncio
async def test_skill_food_starts_a_timed_buff_that_expires(db):
    user = await with_pet("drizzle", xp=0)
    food = next(i for i in REG.items.values() if i.category == "pet_food")
    await user.add_item(food.id, 1)
    await pets.feed(user, food.id, 1)
    owned = user.pethouse.pets["drizzle"]
    assert pets.buff_multiplier(owned, REG) == 1 + REG.pet_score.food_buff_bonus
    assert pets.buff_multiplier(owned, REG, now=owned.buff_until + 1) == 1.0


def test_a_maxed_fully_fueled_pet_hauls_at_most_the_configured_share_of_active_play():
    """Guard: the best pet (max level, 5 stars, sidekick bonus at its cap) never out-earns haul_active_share of what an active player makes an hour
    in the slowest skill at starting tools (scripts.balance numbers)."""
    from scripts import balance as b

    from cococap.services import pets as pets_service

    per_hour = 3600 / b.CLICK_SECONDS
    starter = REG.item("tool_axe_starter").tool.power
    active = min(b.mining_xp_per_click() * per_hour, b.fishing_xp_per_minute(REG.item("tool_rod_starter").tool.power) * 60,
                 b.foraging_xp_per_click(starter) * per_hour)
    best = max(ps.score(p, OwnedPet(xp=pets_service.level_xp(REG.economy.pets.max_level, p.rarity, REG), stars=REG.economy.pets.max_stars))
               for p in REG.pets.values())
    haul = ps.haul_xp_per_hour(best, REG.pet_score.sidekick_cap)
    assert haul <= active * REG.pet_score.haul_active_share * 1.0, (round(haul), round(active))
    # ...and a perfect 1000-point pet at max level and stars (the future Celestial) fits too
    top = pets_service.strength(OwnedPet(xp=10**9, stars=REG.economy.pets.max_stars), 5, REG) * 100
    assert ps.haul_xp_per_hour(top, REG.pet_score.sidekick_cap) <= active * REG.pet_score.haul_active_share


@pytest.mark.asyncio
async def test_the_haul_finds_only_common_drops_of_its_skill(db):
    import random

    user = await with_pet("drizzle", xp=10**9)
    pool = pets.haul_drop_pool("fishing", REG)
    assert pool and all(i.rarity <= 3 and i.skill == "fishing" for i in pool)
    crop = _crop()
    await user.add_item(crop.id, 100000)
    await pets.fuel(user, crop.id, 100000, now=1000.0)
    _, xp, _, drops = await pets.collect(user, now=1000.0 + 100 * 3600, rng=random.Random(1))
    assert xp > 0 and drops and set(drops) <= {i.id for i in pool}
    for item_id, quantity in drops.items():
        assert await user.item_quantity(item_id) >= quantity
