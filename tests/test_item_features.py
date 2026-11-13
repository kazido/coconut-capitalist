import random
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from cococap.exts.core.inventory import inventory_lines
from cococap.registry import get_registry
from cococap.user import User
from utils.items.items import (
    MAX_CHOICES,
    construct_embed,
    item_autocomplete,
    roll_item,
)


@pytest.mark.parametrize("item_id", sorted(get_registry().items))
@pytest.mark.parametrize("for_shop", [False, True])
def test_every_item_renders_an_embed(item_id, for_shop):
    embed = construct_embed(item_id, for_shop)
    assert embed.title and len(embed.description) < 4096
    assert embed.footer.text == f"Wiki: {item_id}"


def test_shop_embed_hides_non_shop_fields():
    full, shop = construct_embed("cod").description, construct_embed("cod", True).description
    assert "Drop Rate" in full and "Drop Rate" not in shop


def test_roll_item_respects_drop_table():
    reg = get_registry()
    assert roll_item(reg.item("apple")) is None  # no drop table
    gem = reg.item("implosion_gemstone")  # 1-in-5, exactly 1
    random.seed(1)
    rolls = [roll_item(gem) for _ in range(2000)]
    assert set(rolls) == {None, 1}
    assert 300 < rolls.count(1) < 500  # ~20%
    ore = reg.item("copper_ore")
    assert {r for r in (roll_item(ore) for _ in range(500)) if r} <= {1, 2, 3}


async def test_autocomplete_is_capped_at_discords_limit():
    assert len(await item_autocomplete(None, "")) == MAX_CHOICES  # 47 items exist
    assert [c.value for c in await item_autocomplete(None, "SANITY")] == ["sanity_gemstone"]


def test_inventory_lines_filter_sort_and_unknown_items():
    items = {
        "iron_ore": 5,
        "copper_ore": 1200,
        "cod": 0,  # emptied stacks are hidden
        "ghost_item": 2,  # not in registry (renamed/removed)
    }
    lines = inventory_lines(items)
    assert len(lines) == 3
    assert "Copper Ore" in lines[0] and "ghost_item" in lines[1] and "Iron Ore" in lines[2]  # name order
    assert any("1,200 Copper Ore" in l for l in lines)
    assert any("unknown item" in l for l in lines)
    assert not any("Cod" in l for l in lines)
    assert len(inventory_lines(items, "mining")) == 2
    assert inventory_lines(items, "nothing-matches") == []


async def test_inventory_lists_tools_with_enchants_and_equipped_mark(db):
    from cococap.exts.core.inventory import instance_label, instance_lines
    from cococap.services.equipment import add_enchant

    user = await User.get(9)
    a = await user.give_instance("starter_axe")
    b = await user.give_instance("starter_axe")
    a = await add_enchant(user, a.id, "soloist")
    assert instance_label(a) == f"Starter Axe #{a.id} [Soloist]"
    lines = instance_lines([a, b], {b.id}, None)
    assert any("[Soloist]" in l and "✅" not in l for l in lines)
    assert any(f"#{b.id}" in l and "✅" in l for l in lines)
    assert len(instance_lines([a, b], set(), "soloist")) == 1  # filter matches enchant names
    assert instance_lines([a, b], set(), "nothing") == []
