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


PRICE = get_registry().item("material_rotation_wedge").price


async def test_buying_a_stackable_spends_bits_and_adds_items(db):
    user = await rich(1_000_000)
    purchase = await buy(user, "material_rotation_wedge", 3)
    assert purchase.total == 3 * PRICE and purchase.instances == []
    assert await user.items() == {"material_rotation_wedge": 3}
    assert await user.get_bits() == 1_000_000 - 3 * PRICE


async def test_the_shop_sells_no_tools_and_starter_tools_are_free_once(db):
    from cococap.constants import STARTER_TOOLS
    from cococap.services.shop import claim_starter_tools

    reg = get_registry()
    assert not [i.id for i in reg.shop_items() if i.tool]
    user = await rich()
    for item_id in (*STARTER_TOOLS, "tool_axe_reinforced"):
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
    await user.give_instance("tool_axe_reinforced")  # an axe of another make: no free axe
    got = await claim_starter_tools(user)
    assert "tool_axe_starter" not in got and len(got) == 3
    assert await claim_starter_tools(user) == []  # each is handed out once ever


@pytest.mark.parametrize("item_id, qty", [("fish_cod", 1), ("nope", 1), ("material_rotation_wedge", 0), ("material_rotation_wedge", 10**6), ("tool_scarab_bomb", 1)])
async def test_invalid_purchases_rejected(db, item_id, qty):
    user = await rich()
    with pytest.raises(ShopError):
        await buy(user, item_id, qty)
    assert await user.get_bits() == 10_000_000


async def test_concurrent_purchases_cannot_overspend(db):
    user = await rich(2 * PRICE + PRICE // 2)
    results = await asyncio.gather(*(buy(user, "material_rotation_wedge") for _ in range(5)), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 2  # two fit, a third does not
    assert await user.get_bits() == PRICE // 2 and await user.item_quantity("material_rotation_wedge") == 2


async def test_selling(db):
    user = await rich(0)
    await user.add_item("material_gold_ore", 5)
    price = get_registry().item("material_gold_ore").sell_price
    assert await sell(user, "material_gold_ore", 2) == 2 * price
    assert await user.get_bits() == 2 * price and await user.item_quantity("material_gold_ore") == 3
    with pytest.raises(ShopError, match="don't have"):
        await sell(user, "material_gold_ore", 4)
    with pytest.raises(ShopError):
        await sell(user, "seed_apple", 1)  # sell_price 0: can't be sold
    await user.give_instance("tool_axe_starter")
    with pytest.raises(ShopError):
        await sell(user, "tool_axe_starter", 1)  # unique items aren't sold by id
    assert await user.get_bits() == 2 * price


async def test_the_sell_list_shows_the_count_the_price_each_and_the_price_for_all(db):
    from tests.test_hub import all_text, hub

    user = await User.get(1)
    await user.add_item("material_coral_shard", 7)
    price = get_registry().item("material_coral_shard").sell_price
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


def test_crafted_items_are_not_sold_in_the_shop_any_more():
    reg = get_registry()
    for recipe in reg.recipes.values():
        assert reg.item(recipe.output).price == 0 and reg.item(recipe.output) not in reg.shop_items()
    assert {"material_radar_battery", "material_iron_wedge", "material_gilded_wedge", "tool_scarab_bomb"} <= {r.output for r in reg.recipes.values()}
    assert all(reg.item(i).sellable for i in ("material_radar_battery", "material_iron_wedge", "material_gilded_wedge", "tool_scarab_bomb"))  # (they still sell)


# ---- how many you can buy / sell, and the Shop's amount buttons -------------------------------------------------------------

async def test_max_affordable_is_what_the_bits_pay_for_capped_per_purchase(db):
    from cococap.services.shop import MAX_PER_PURCHASE, max_affordable

    user = await rich(PRICE * 3 + PRICE // 2)
    assert await max_affordable(user, "material_rotation_wedge") == 3  # the half is not enough for a fourth
    assert await max_affordable(user, "nope") == 0 and await max_affordable(user, "tool_axe_starter") == 0  # not in the shop
    await set_columns(user, purse=10**12)
    assert await max_affordable(user, "material_rotation_wedge") == MAX_PER_PURCHASE
    await set_columns(user, purse=0)
    assert await max_affordable(user, "material_rotation_wedge") == 0


async def test_max_affordable_matches_what_buy_accepts(db):
    from cococap.services.shop import max_affordable

    user = await rich(PRICE * 5)
    n = await max_affordable(user, "material_rotation_wedge")
    await buy(user, "material_rotation_wedge", n)  # buying the max works
    with pytest.raises(ShopError):
        await buy(user, "material_rotation_wedge", 1)  # one more does not


@pytest.mark.parametrize("raw, maximum, expected", [("5", 12, 5), ("99", 12, 12), (" 1,000 ", 5000, 1000), ("1", 1, 1)])
def test_clamp_quantity_takes_the_number_and_caps_it_at_the_max(raw, maximum, expected):
    from cococap.screens.shop import clamp_quantity

    assert clamp_quantity(raw, maximum) == expected


@pytest.mark.parametrize("raw", ["lots", "", "2.5", "0", "-3"])
def test_clamp_quantity_rejects_non_numbers_and_numbers_below_one(raw):
    from cococap.errors import CustomError
    from cococap.screens.shop import clamp_quantity

    with pytest.raises(CustomError, match="whole number from 1 to 12"):
        clamp_quantity(raw, 12)


async def test_shop_buy_one_and_ten_at_a_time(db):
    from tests.test_hub import all_text, click, hub, select_named

    user = await rich(10_000_000)
    nav, inter = await hub("shop")
    first = select_named(nav, "Pick an item").options[0].value  # whatever the page starts on
    price = get_registry().item(first).price
    await click(nav, inter, "Buy 10x")
    assert await user.item_quantity(first) == 10 and await user.get_bits() == 10_000_000 - 10 * price
    await click(nav, inter, "Buy 1x")
    assert await user.item_quantity(first) == 11
    assert "Bought 1 ×" in all_text(nav)


async def test_shop_ten_buy_is_off_when_you_cannot_afford_ten(db):
    from tests.test_hub import find_button, hub, select_named

    user = await rich(10_000_000)
    first = select_named((await hub("shop"))[0], "Pick an item").options[0].value
    price = get_registry().item(first).price
    await set_columns(user, purse=price * 9)
    nav, _ = await hub("shop")
    assert find_button(nav, "Buy 10x").disabled and not find_button(nav, "Buy 1x").disabled
    await set_columns(user, purse=price - 1)
    nav, _ = await hub("shop")
    assert find_button(nav, "Buy 1x").disabled and find_button(nav, "Buy custom") is not None


async def test_shop_buy_custom_prefills_the_max_you_can_afford(db):
    from tests.test_hub import click, hub, select_named
    from cococap.services.shop import max_affordable

    user = await rich(10_000_000)
    first = select_named((await hub("shop"))[0], "Pick an item").options[0].value
    await set_columns(user, purse=get_registry().item(first).price * 7)
    nav, inter = await hub("shop")
    expected = await max_affordable(user, first)
    assert expected == 7
    await click(nav, inter, "Buy custom")
    modal = inter.response.send_modal.await_args.args[0]
    assert modal.field.default == str(expected) and modal.field.max_length == 9
    assert any(f"(max {expected})" in getattr(c, "text", "") for c in modal.children)


async def test_shop_buy_custom_clamps_too_big_to_the_max(db):
    from tests.test_hub import click, hub, select_named, submit

    user = await rich(10_000_000)
    nav, inter = await hub("shop")
    first = select_named(nav, "Pick an item").options[0].value
    await click(nav, inter, "Buy custom")
    modal = await submit(inter, "10000000")
    await modal.on_submit(inter)
    assert await user.item_quantity(first) > 0 and (await user.get_bits()) >= 0  # bought what the bits paid for, not an error


async def test_shop_sell_one_ten_and_custom(db):
    from tests.test_hub import buttons, click, find_button, hub, submit

    user = await rich(0)
    await user.add_item("material_gold_ore", 12)
    nav, inter = await hub("shop")
    await click(nav, inter, "Sell")
    assert find_button(nav, "Sell 10x").disabled is False
    await click(nav, inter, "Sell 10x")
    assert await user.item_quantity("material_gold_ore") == 2
    await click(nav, inter, "Sell 1x")
    assert await user.item_quantity("material_gold_ore") == 1
    assert find_button(nav, "Sell 10x").disabled
    await click(nav, inter, "Sell custom")
    modal = await submit(inter, "99")
    await modal.on_submit(inter)  # clamped to the 1 you own
    assert await user.item_quantity("material_gold_ore") == 0 and (await user.get_bits()) > 0


async def test_shop_sell_custom_prefills_what_you_own(db):
    from tests.test_hub import click, hub

    user = await rich(0)
    await user.add_item("material_gold_ore", 4)
    nav, inter = await hub("shop")
    await click(nav, inter, "Sell")
    await click(nav, inter, "Sell custom")
    modal = inter.response.send_modal.await_args.args[0]
    assert modal.field.default == "4"
    assert any("(max 4)" in getattr(c, "text", "") for c in modal.children)


async def test_skill_pages_have_no_sell_all_button(db):
    from tests.test_hub import buttons, hub

    for screen in ("fish", "forage", "farm", "mining"):
        nav, _ = await hub(screen)
        assert not any(b.label and b.label.startswith("Sell all") for b in buttons(nav)), screen
