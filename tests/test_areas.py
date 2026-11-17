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


def test_later_areas_never_cap_a_skill_lower_than_earlier_ones():
    waters = [w.id for w in REG.fishing.waters]
    caps = [waters.index(a.fishing_max_water) for a in RULES.areas]
    assert caps == sorted(caps)


# ---- the ship ----------------------------------------------------------------------------------------------------------------------------
async def test_a_new_player_starts_in_the_first_area_with_no_ship(db):
    user = await User.get(1)
    st = await areas.state(user)
    assert (st.tier, st.current, st.highest) == (0, 0, 0)
    assert (await areas.current_area(user)).id == RULES.areas[0].id
    assert await areas.max_zone(user) == RULES.areas[0].foraging_max_zone
    assert await areas.max_water(user) == RULES.areas[0].fishing_max_water


async def test_building_the_ship_needs_levels_then_takes_bits_and_parts(db):
    user = await User.get(1)
    tier = RULES.ship_tiers[0]
    await stock_tier(user, 1)
    await user.update_skill("mining", lambda s: setattr(s, "xp", 0))
    with pytest.raises(AreaError, match="mining"):
        await areas.upgrade_ship(user)
    assert await user.item_quantity(next(iter(tier.parts))) == tier.parts[next(iter(tier.parts))]  # nothing was taken
    await level_all(user, 100)
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
    assert await areas.max_zone(user) == nxt.foraging_max_zone
    await areas.travel(user, RULES.areas[0].id)  # back: free
    assert await areas.max_zone(user) == RULES.areas[0].foraging_max_zone
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
