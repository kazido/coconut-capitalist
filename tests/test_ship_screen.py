"""The ship screen: build, sail, craft fuel (the rules are tested in test_areas.py)."""

import pytest

from cococap.registry import get_registry
from cococap.services import areas
from cococap.user import User
from tests.test_areas import level_all, stock_fuel, stock_tier
from tests.test_hub import all_text, buttons, choose, click, hub, select_named

REG = get_registry()


async def test_build_then_sail_to_the_next_area(db):
    user = await User.get(1)
    await stock_tier(user, 1)
    await stock_fuel(user, 1)
    nav, inter = await hub("ship")
    assert "none yet" in all_text(nav)
    await click(nav, inter, "Build")
    assert (await areas.state(user)).tier == 1
    await choose(nav, inter, select_named(nav, "Sail"), REG.areas.areas[1].id)
    st = await areas.state(user)
    assert st.current == 1 and st.highest == 1


async def test_a_short_ship_says_why_and_changes_nothing(db):
    user = await User.get(1)
    await level_all(user, 1)
    nav, inter = await hub("ship")
    with pytest.raises(areas.AreaError, match="any one skill"):
        await click(nav, inter, "Build")
    assert (await areas.state(user)).tier == 0


async def test_craft_fuel_button_follows_what_you_can_make(db):
    nav, _ = await hub("ship")
    assert next(b for b in buttons(nav) if b.label == "Craft fuel").disabled
