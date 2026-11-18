"""Sell all: one button on each skill's page sells everything that skill gave you, behind a confirm you can turn off."""

import pytest

from cococap.registry import get_registry
from cococap.services import shop
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, buttons, click, find_button, hub

REG = get_registry()
PRICE = lambda item_id: REG.item(item_id).sell_price  # noqa: E731


async def stock(user):
    """Some of everything. Sell All's keep-materials setting is off here: these tests are about selling (copper and iron ore are also Scarab Bomb inputs now)."""
    await user.set_setting("keep_upgrade_materials", False)
    for item, qty in (("material_copper_ore", 10), ("material_iron_ore", 3), ("material_hardwood", 4), ("material_feather", 20), ("fish_salmon", 2), ("material_coral_shard", 5)):
        await user.add_item(item, qty)


# ---- the service -----------------------------------------------------------------------------------------------------------------------------
async def test_a_skills_sell_all_sells_only_that_skills_stacks(db):
    user = await User.get(1)
    await stock(user)
    start = (await User.get(1)).purse
    earned, sold = await shop.sell_all_for_skill(user, "mining")
    assert sold == {"material_copper_ore": 10, "material_iron_ore": 3} and earned == 10 * PRICE("material_copper_ore") + 3 * PRICE("material_iron_ore")
    await user.refresh()
    assert user.purse == start + earned and await user.item_quantity("material_hardwood") == 4 and await user.item_quantity("fish_salmon") == 2  # the other skills' things stay
    assert (await shop.sell_all_for_skill(user, "mining")) == (0, {})  # nothing left


async def test_fishing_sell_all_includes_the_fish_and_the_fishing_materials(db):
    user = await User.get(1)
    await stock(user)
    earned, sold = await shop.sell_all_for_skill(user, "fishing")
    assert set(sold) == {"fish_salmon", "material_coral_shard"} and earned == 2 * PRICE("fish_salmon") + 5 * PRICE("material_coral_shard")


async def test_keeping_what_the_next_upgrade_needs(db):
    user = await User.get(1)
    await stock(user)
    earned, sold = await shop.sell_all_for_skill(user, "mining", keep={"material_copper_ore": 4, "material_iron_ore": 99})
    assert sold == {"material_copper_ore": 6} and await user.item_quantity("material_copper_ore") == 4 and await user.item_quantity("material_iron_ore") == 3
    assert earned == 6 * PRICE("material_copper_ore")


def test_tools_keys_and_unsellable_things_are_never_sold():
    owned = {"key_graveyard": 2, "seed_apple": 5, "material_copper_ore": 1, "scroll_keen": 1}
    assert shop.sellable_for_skill(owned, "mining", REG) == {"material_copper_ore": 1}
    assert shop.sellable_for_skill(owned, "combat", REG) == {} and shop.sellable_for_skill(owned, "foraging", REG) == {}  # (no price, or not that skill)


# ---- the buttons ------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("screen", ["mining", "farm", "forage", "fish"])
async def test_every_skill_page_has_a_sell_all_button_that_asks_first(db, screen):
    user = await User.get(1)
    await stock(user)
    await user.add_item("crop_lemon", 3)
    nav, inter = await hub(screen)
    assert find_button(nav, "Sell all")
    await click(nav, inter, "Sell all")
    assert nav.screen.id == "shop" and nav.screen.tab == "sellall" and "Sell everything from" in all_text(nav)
    assert await user.item_quantity("material_copper_ore") == 10  # nothing sold yet: it asked


async def test_confirming_sells_everything_and_shows_what_it_paid(db):
    user = await User.get(1)
    await stock(user)
    start = (await User.get(1)).purse
    nav, inter = await hub("mining")
    await click(nav, inter, "Sell all")
    assert "10" in all_text(nav) and "Copper Ore" in all_text(nav)
    await next(b for b in buttons(nav) if (b.label or "").startswith("Sell everything")).callback(inter)
    assert nav.screen.id == "result" and "You sold" in all_text(nav)
    assert (await User.get(1)).purse == start + 10 * PRICE("material_copper_ore") + 3 * PRICE("material_iron_ore") and await user.item_quantity("material_copper_ore") == 0


async def test_cancelling_keeps_everything(db):
    user = await User.get(1)
    await stock(user)
    nav, inter = await hub("mining")
    await click(nav, inter, "Sell all")
    await click(nav, inter, "Cancel")
    assert nav.screen.id == "mining" and await user.item_quantity("material_copper_ore") == 10


async def test_with_the_setting_off_it_sells_at_once(db):
    user = await User.get(1)
    await stock(user)
    await user.set_setting("confirm_sell_all", False)
    nav, inter = await hub("mining")
    await click(nav, inter, "Sell all")
    assert nav.screen.id == "mining" and "Sold" in all_text(nav) and await user.item_quantity("material_copper_ore") == 0


async def test_the_confirm_page_offers_to_keep_what_your_next_upgrade_needs(db):
    from cococap.services.equipment import equip

    user = await User.get(1)
    await set_columns(user, purse=10**9)
    inst = await user.give_instance("tool_pickaxe_rookie")
    await equip(user, "mining", inst.id)
    need = REG.item("tool_pickaxe_rookie").tool.upgrade.items  # copper and iron for the first upgrade
    for item, qty in need.items():
        await user.add_item(item, qty + 7)
    nav, inter = await hub("mining")
    await click(nav, inter, "Sell all")
    text = all_text(nav)
    from cococap.services import crafting

    held = {i: max(q, crafting.needed_items().get(i, (0, []))[0]) for i, q in need.items()}  # (the upgrade, or a recipe that uses the same ore)
    assert "needs" in text and all(f"needs {q:,}" in text for q in held.values())
    keep = next(b for b in buttons(nav) if b.label.startswith("Sell, keep upgrade materials"))
    assert not keep.disabled
    await keep.callback(inter)
    for item, qty in need.items():
        assert await user.item_quantity(item) == min(qty + 7, held[item])  # exactly what the upgrade (or a recipe) needs was kept
    assert "kept" in all_text(nav)


async def test_nothing_to_sell_says_so(db):
    nav, inter = await hub("mining")
    await click(nav, inter, "Sell all")
    assert "nothing from" in all_text(nav)


# ---- more settings ------------------------------------------------------------------------------------------------------------------------
async def test_the_settings_page_lists_every_setting_and_each_toggle_saves():
    from cococap.models.settings import Settings
    from cococap.screens.settings import SETTINGS

    assert set(SETTINGS) == set(Settings.model_fields)  # (nothing is stored that the page cannot show, nor shown that is not stored)


async def test_keep_upgrade_materials_makes_sell_all_hold_back_what_upgrades_need(db):
    from cococap.screens.sellall import upgrade_needs

    user = await User.get(1)
    await user.give_instance("tool_pickaxe_rookie")
    needs = await upgrade_needs(user)
    assert needs
    item_id, need = next(iter(needs.items()))
    skill = get_registry().item(item_id).skill
    await user.add_item(item_id, need + 3)
    await user.set_setting("confirm_sell_all", False)
    await user.set_setting("keep_upgrade_materials", True)
    nav, inter = await hub("skills")
    from cococap.screens.sellall import start_sell_all

    await start_sell_all(nav.screen, inter, skill)
    assert await user.item_quantity(item_id) == need  # only the spare ones were sold
