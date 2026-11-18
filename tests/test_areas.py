import pytest

from cococap.registry import get_registry
from cococap.services import areas
from cococap.services.areas import AreaError
from cococap.user import User
from tests.conftest import set_columns

REG = get_registry()
RULES = REG.areas


async def level_all(user, level):
    xp = User.level_to_xp(level + 1)  # (level_to_xp(n) is just short of level n)
    for skill in areas.SKILLS:
        await user.update_skill(skill, lambda s: setattr(s, "xp", xp))


async def stock_tier(user, n):
    tier = RULES.ship_tiers[n - 1]
    for item_id, qty in tier.parts.items():
        await user.add_item(item_id, qty)
    await set_columns(user, purse=tier.bits)
    await level_all(user, max(tier.skill_floors.values()))


async def stock_fuel(user, area_index):
    for item_id, qty in RULES.areas[area_index].fuel.items():
        await user.add_item(item_id, qty)


# ---- the data ----------------------------------------------------------------------------------------------------------------------------
def test_there_are_seven_areas_and_one_ship_tier_per_trip():
    assert [a.name for a in RULES.areas][0] == "Slime Hill" and len(RULES.areas) == 7
    assert len(RULES.ship_tiers) == 6


def test_every_trip_has_fuel_that_is_craftable_from_all_four_skills():
    crafted = {r.output: r for r in REG.recipes.values()}
    for area in RULES.areas[1:]:
        for fuel in area.fuel:
            skills = {REG.item(i).skill for i in crafted[fuel].inputs}
            assert skills == set(areas.SKILLS), (fuel, skills)


def test_the_location_schedule_has_two_locations_per_area_and_ends_at_level_50():
    levels = RULES.location_levels
    assert len(levels) == 2 * len(RULES.areas) and levels[0] == 1 and levels == sorted(set(levels))
    assert levels[-1] <= 50
    assert [areas.area_of_location(n) for n in (1, 2, 3, 4, 13, 14)] == [0, 0, 1, 1, 6, 6]


# ---- the ship ----------------------------------------------------------------------------------------------------------------------------
async def test_a_new_player_starts_in_the_first_area_with_no_ship(db):
    user = await User.get(1)
    st = await areas.state(user)
    assert (st.tier, st.current, st.highest) == (0, 0, 0)
    assert (await areas.current_area(user)).id == RULES.areas[0].id
    assert await areas.open_locations(user, "foraging") == 1  # level 1: the first location


async def test_building_the_ship_needs_levels_then_takes_bits_and_parts(db):
    user = await User.get(1)
    tier = RULES.ship_tiers[0]
    await stock_tier(user, 1)
    for skill in areas.SKILLS:
        await user.update_skill(skill, lambda s: setattr(s, "xp", 0))
    with pytest.raises(AreaError, match="any one skill"):
        await areas.upgrade_ship(user)
    assert await user.item_quantity(next(iter(tier.parts))) == tier.parts[next(iter(tier.parts))]  # nothing was taken
    # ANY ONE skill at the floor is enough, the others can stay at level 1
    await user.update_skill("farming", lambda s: setattr(s, "xp", User.level_to_xp(max(tier.skill_floors.values()) + 1)))
    await areas.upgrade_ship(user)
    assert (await areas.state(user)).tier == 1
    await user.refresh()
    assert user.purse == 0 and await user.item_quantity(next(iter(tier.parts))) == 0


async def test_a_short_part_changes_nothing(db):
    user = await User.get(1)
    await stock_tier(user, 1)
    first = next(iter(RULES.ship_tiers[0].parts))
    await user.remove_item(first, 1)
    with pytest.raises(AreaError):
        await areas.upgrade_ship(user)
    assert (await areas.state(user)).tier == 0


async def test_the_last_tier_is_the_end(db):
    user = await User.get(1)
    for n in range(1, 7):
        await stock_tier(user, n)
        await areas.upgrade_ship(user)
    assert (await areas.state(user)).tier == 6
    with pytest.raises(AreaError, match="fully"):
        await areas.upgrade_ship(user)


# ---- travel ------------------------------------------------------------------------------------------------------------------------------
async def test_the_first_trip_needs_the_ship_and_burns_the_fuel_then_going_back_and_forth_is_free(db):
    user = await User.get(1)
    nxt = RULES.areas[1]
    with pytest.raises(AreaError, match="ship tier"):
        await areas.travel(user, nxt.id)
    await stock_tier(user, 1)
    await areas.upgrade_ship(user)
    with pytest.raises(AreaError):  # no fuel yet
        await areas.travel(user, nxt.id)
    await stock_fuel(user, 1)
    assert (await areas.travel(user, nxt.id)).id == nxt.id
    fuel = next(iter(nxt.fuel))
    assert await user.item_quantity(fuel) == 0
    assert await areas.open_locations(user, "foraging") == 3  # (the ship's level floor is 8: locations 1-3)
    await areas.travel(user, RULES.areas[0].id)  # back: free
    await areas.travel(user, nxt.id)  # forward to a reached area: free
    assert await user.item_quantity(fuel) == 0 and (await areas.state(user)).highest == 1


async def test_you_cannot_skip_an_area_or_travel_where_you_already_are(db):
    user = await User.get(1)
    await stock_tier(user, 1)
    await areas.upgrade_ship(user)
    with pytest.raises(AreaError, match="first"):
        await areas.travel(user, RULES.areas[2].id)
    with pytest.raises(AreaError, match="already"):
        await areas.travel(user, RULES.areas[0].id)
    with pytest.raises(AreaError, match="no such"):
        await areas.travel(user, "atlantis")


async def test_the_next_area_needs_the_next_ship_tier(db):
    user = await User.get(1)
    await stock_tier(user, 1)
    await areas.upgrade_ship(user)
    await stock_fuel(user, 1)
    await areas.travel(user, RULES.areas[1].id)
    await stock_fuel(user, 2)
    with pytest.raises(AreaError, match="ship tier 2"):
        await areas.travel(user, RULES.areas[2].id)
    assert await user.item_quantity(next(iter(RULES.areas[2].fuel))) == 1  # fuel kept


# ---- locations: the area caps what the level would allow ---------------------------------------------------------------------------------
async def test_a_high_level_is_capped_by_the_area_you_are_in_until_you_travel(db):
    user = await User.get(1)
    await stock_tier(user, 1)
    await level_all(user, 50)
    for skill in areas.SKILLS:
        assert await areas.open_locations(user, skill) == 2  # Slime Hill holds locations 1-2 only
    assert "be in Twilight Desert" in await areas.next_location_hint(user, "mining")
    await level_all(user, 8)  # (building the ship needs only level 8)
    await areas.upgrade_ship(user)
    await level_all(user, 50)
    await stock_fuel(user, 1)
    await areas.travel(user, RULES.areas[1].id)
    assert await areas.open_locations(user, "mining") == 4
    await areas.travel(user, RULES.areas[0].id)  # sailing back narrows it again
    assert await areas.open_locations(user, "mining") == 2


async def test_a_low_level_is_capped_by_the_level_even_in_a_later_area(db):
    user = await User.get(1)
    await stock_tier(user, 1)
    await areas.upgrade_ship(user)
    await stock_fuel(user, 1)
    await areas.travel(user, RULES.areas[1].id)
    await level_all(user, RULES.location_levels[2] - 1)  # one short of location 3
    assert await areas.open_locations(user, "fishing") == 2
    assert await areas.next_location_hint(user, "fishing") == f"Needs level {RULES.location_levels[2]} fishing"
    await level_all(user, RULES.location_levels[2])
    assert await areas.open_locations(user, "fishing") == 3


async def test_skills_open_locations_on_their_own_levels(db):
    user = await User.get(1)
    await user.update_skill("mining", lambda s: setattr(s, "xp", User.level_to_xp(RULES.location_levels[1] + 1)))
    assert await areas.open_locations(user, "mining") == 2
    assert await areas.open_locations(user, "farming") == 1
