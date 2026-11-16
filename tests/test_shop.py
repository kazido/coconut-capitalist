import asyncio

import pytest

from cococap.registry import get_registry
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


async def test_the_shop_sells_no_tools_and_starter_tools_are_free_once(db):
    from cococap.constants import STARTER_TOOLS
    from cococap.services.shop import claim_starter_tools

    reg = get_registry()
    assert not [i.id for i in reg.shop_items() if i.tool]
    user = await rich()
    for item_id in (*STARTER_TOOLS, "reinforced_axe"):
        with pytest.raises(ShopError, match="isn't sold"):
            await buy(user, item_id)
    assert sorted(await claim_starter_tools(user)) == sorted(STARTER_TOOLS)
    assert sorted(i.template_id for i in await user.instances()) == sorted(STARTER_TOOLS)
    assert await user.items() == {} and await user.get_bits() == 10_000_000  # free, and tools are not stackables
    assert await user.equipped_instance("foraging") is not None  # the first tool of a skill is equipped
    assert await claim_starter_tools(user) == []


async def test_claiming_starters_skips_kinds_you_own_and_tools_you_already_had(db):
    from cococap.services.shop import claim_starter_tools

    user = await rich()
    await user.give_instance("reinforced_axe")  # an axe of another make: no free axe
    got = await claim_starter_tools(user)
    assert "starter_axe" not in got and len(got) == 3
    assert await claim_starter_tools(user) == []  # each is handed out once ever


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
    price = get_registry().item("gold_ore").sell_price
    assert await sell(user, "gold_ore", 2) == 2 * price
    assert await user.get_bits() == 2 * price and await user.item_quantity("gold_ore") == 3
    with pytest.raises(ShopError, match="don't have"):
        await sell(user, "gold_ore", 4)
    with pytest.raises(ShopError):
        await sell(user, "apple_seed", 1)  # sell_price 0: can't be sold
    await user.give_instance("starter_axe")
    with pytest.raises(ShopError):
        await sell(user, "starter_axe", 1)  # unique items aren't sold by id
    assert await user.get_bits() == 2 * price


async def test_the_sell_list_shows_the_count_the_price_each_and_the_price_for_all(db):
    from tests.test_hub import all_text, hub

    user = await User.get(1)
    await user.add_item("coral_shard", 7)
    price = get_registry().item("coral_shard").sell_price
    nav, _ = await hub("shop")
    nav.screen.mode = "sell"
    await nav.screen.nav.refresh(_)
    text = all_text(nav)
    assert f"×7  ·  {price:,} each  ·  **{price * 7:,}** for all" in text
    assert "sells for" not in text and "You have **7" not in text
    heading = next(line for line in text.split("\n") if line.startswith("### ") and "Coral Shard" in line)
    assert "×" not in heading  # (the count is not in the bold heading)


def test_work_wages_climb_with_rank_and_the_early_ranks_still_give_a_start():
    wages = [get_registry().rank(r).wage for r in range(16)]
    assert wages == sorted(wages) and wages[0] == wages[1] == 2500
    assert wages[7] <= 120_000 and wages[15] <= 2_000_000  # (cut to 30%: skills, not the Work button, are where the bits come from)
