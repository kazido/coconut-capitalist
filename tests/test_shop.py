import asyncio

import pytest

from cococap.services.shop import ShopError, buy, sell
from cococap.user import User
from tests.conftest import set_columns


async def rich(purse=10_000_000):
    user = await User.get(1)
    await set_columns(user, purse=purse)
    return user


async def test_buying_a_stackable_spends_bits_and_adds_items(db):
    user = await rich(1_000_000)
    purchase = await buy(user, "scarab_bomb", 3)  # 100,000 each
    assert purchase.total == 300_000 and purchase.instances == []
    assert await user.items() == {"scarab_bomb": 3}
    assert await user.get_bits() == 700_000


async def test_buying_a_tool_creates_unique_instances(db):
    user = await rich()
    purchase = await buy(user, "starter_axe", 2)
    assert len(purchase.instances) == 2 and len({i.id for i in purchase.instances}) == 2
    assert [i.template_id for i in await user.instances()] == ["starter_axe"] * 2
    assert await user.items() == {}  # tools are not stackables


async def test_cannot_afford_changes_nothing(db):
    user = await rich(50)
    with pytest.raises(ShopError, match="need"):
        await buy(user, "starter_axe")
    assert await user.get_bits() == 50 and await user.instances() == []


@pytest.mark.parametrize("item_id, qty", [("cod", 1), ("nope", 1), ("scarab_bomb", 0), ("scarab_bomb", 10**6)])
async def test_invalid_purchases_rejected(db, item_id, qty):
    user = await rich()
    with pytest.raises(ShopError):
        await buy(user, item_id, qty)
    assert await user.get_bits() == 10_000_000


async def test_concurrent_purchases_cannot_overspend(db):
    user = await rich(250_000)
    results = await asyncio.gather(*(buy(user, "scarab_bomb") for _ in range(5)), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 2  # 2 x 100,000 fits in 250,000
    assert await user.get_bits() == 50_000 and await user.item_quantity("scarab_bomb") == 2


async def test_selling(db):
    user = await rich(0)
    await user.add_item("gold_ore", 5)
    assert await sell(user, "gold_ore", 2) == 2000
    assert await user.get_bits() == 2000 and await user.item_quantity("gold_ore") == 3
    with pytest.raises(ShopError, match="don't have"):
        await sell(user, "gold_ore", 4)
    with pytest.raises(ShopError):
        await sell(user, "apple_seed", 1)  # sell_price 0: can't be sold
    await user.give_instance("starter_axe")
    with pytest.raises(ShopError):
        await sell(user, "starter_axe", 1)  # unique items aren't sold by id
    assert await user.get_bits() == 2000
