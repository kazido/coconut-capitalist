import pytest

from cococap.registry import get_registry
from cococap.services import areas, crafting, party
from cococap.services.areas import AreaError
from cococap.services.crafting import CraftError
from cococap.user import User
from tests.conftest import set_columns
from tests.test_areas import stock_fuel

REG = get_registry()
RULES = REG.areas
FUELS = [next(iter(a.fuel)) for a in RULES.areas if a.fuel]


async def reach(user, n):
    """Pretend the player has reached area n (state lives in the ship doc)."""
    from cococap.services import community
    await community.update(areas._key(user.id), areas._DEFAULT, lambda d: d.update({"tier": n, "current": n, "highest": n}))


def test_each_fuel_recipe_needs_the_one_before():
    for prev, fuel in zip(FUELS, FUELS[1:], strict=False):
        assert REG.recipes[fuel].inputs[prev] == 1


async def test_burning_takes_the_fuel_sets_the_timer_and_boosts_xp(db):
    user = await User.get(1)
    await reach(user, 2)
    await stock_fuel(user, 1)
    base = await party.xp_multiplier(1, REG, "mining")
    await areas.burn_fuel(user, RULES.areas[1].id)
    assert await user.item_quantity(FUELS[0]) == 0
    area, left = await areas.overdrive_state(user)
    assert area.id == RULES.areas[1].id and 0 < left <= RULES.overdrive_minutes * 60
    assert await areas.overdrive_bonus(user) == (area.overdrive.xp, area.overdrive.drop_amount)
    assert await party.xp_multiplier(1, REG, "mining") == pytest.approx(base * (1 + area.overdrive.xp))


async def test_same_fuel_stacks_to_the_cap_and_a_different_one_replaces(db):
    user = await User.get(1)
    await reach(user, 2)
    for _ in range(5):
        await user.add_item(FUELS[0], 1)
        await areas.burn_fuel(user, RULES.areas[1].id)
    assert (await areas.overdrive_state(user))[1] <= RULES.overdrive_max_minutes * 60
    await user.add_item(FUELS[1], 1)
    await areas.burn_fuel(user, RULES.areas[2].id)
    area, left = await areas.overdrive_state(user)
    assert area.id == RULES.areas[2].id and left <= RULES.overdrive_minutes * 60


async def test_burning_needs_the_fuel_and_a_reached_area_and_ends_on_time(db):
    user = await User.get(1)
    with pytest.raises(AreaError):  # area 1 not reached
        await areas.burn_fuel(user, RULES.areas[1].id)
    await reach(user, 1)
    with pytest.raises(AreaError):  # no fuel held
        await areas.burn_fuel(user, RULES.areas[1].id)
    await stock_fuel(user, 1)
    await areas.burn_fuel(user, RULES.areas[1].id)
    from cococap.services import community
    await community.update(areas._key(1), areas._DEFAULT, lambda d: d["overdrive"].update({"until": 1}))
    assert await areas.overdrive_state(user) is None and await areas.overdrive_bonus(user) == (0.0, 0.0)


async def test_auto_craft_makes_the_chain_from_raw_materials_all_or_nothing(db):
    user = await User.get(1)
    star = REG.recipes[FUELS[4]]
    chain, bits = [REG.recipes[f] for f in FUELS[:5]], 0
    for r in chain:
        bits += r.bits
        for item, q in r.inputs.items():
            if item not in FUELS:
                await user.add_item(item, q)
    await set_columns(user, purse=bits - 1)
    with pytest.raises(CraftError):  # one bit short: nothing is taken
        await crafting.craft(user, star.id, 1, REG, auto=True)
    assert await user.item_quantity(next(i for i in star.inputs if i not in FUELS)) > 0
    await set_columns(user, purse=bits)
    made = await crafting.craft(user, star.id, 1, REG, auto=True)
    assert made.bits == bits and await user.item_quantity(FUELS[4]) == 1
    assert [await user.item_quantity(f) for f in FUELS[:4]] == [0] * 4


async def test_auto_craft_off_still_errors_and_held_fuels_are_used_first(db):
    user = await User.get(1)
    rust = REG.recipes[FUELS[1]]
    for item, q in rust.inputs.items():
        if item != FUELS[0]:
            await user.add_item(item, q)
    await set_columns(user, purse=rust.bits + REG.recipes[FUELS[0]].bits)
    with pytest.raises(CraftError):
        await crafting.craft(user, rust.id, 1, REG, auto=False)
    await user.add_item(FUELS[0], 1)  # now held: auto must not craft another (it has no twilight inputs)
    made = await crafting.craft(user, rust.id, 1, REG, auto=True)
    assert made.bits == rust.bits
