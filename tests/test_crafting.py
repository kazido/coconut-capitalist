"""The Workbench: recipes (data), the craft rules, and the screen end to end."""

import shutil

import pytest

from cococap.registry import RegistryError, get_registry, load_registry
from cococap.registry.loader import CONFIG_DIR
from cococap.services import crafting, shop, wiki
from cococap.services.crafting import CraftError
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, buttons, choose, click, find_button, hub, selects

REG = get_registry()
BATTERY = REG.recipes["material_radar_battery"]
WEDGE = REG.recipes["material_iron_wedge"]  # (has a bits fee)
GILDED = REG.recipes["material_gilded_wedge"]  # (needs foraging level)
CRAFTED = ("material_radar_battery", "material_iron_wedge", "material_gilded_wedge", "tool_scarab_bomb")


async def stock(user, recipe, times=1, bits=0):
    for item_id, need in recipe.inputs.items():
        await user.add_item(item_id, need * times)
    await set_columns(user, purse=bits)


# ---- the data ----------------------------------------------------------------------------------------------------------------------------
def test_the_four_first_recipes_exist_and_their_outputs_are_no_longer_in_the_shop():
    assert set(CRAFTED) <= set(REG.recipes)
    for item_id in CRAFTED:
        item = REG.item(item_id)
        assert item.price == 0 and item not in REG.shop_items() and item.sellable and not item.is_instance


def test_every_recipe_points_at_real_items_and_makes_something_new():
    for recipe in REG.recipes.values():
        assert REG.item(recipe.output) and recipe.quantity >= 1 and recipe.emoji
        assert recipe.inputs and all(REG.item(i) and q >= 1 for i, q in recipe.inputs.items())
        assert recipe.output not in recipe.inputs and not any(REG.item(i).is_instance for i in recipe.inputs)


def _with_recipes(tmp_path, text):
    shutil.copytree(CONFIG_DIR, tmp_path / "configs", ignore=shutil.ignore_patterns("local"))
    (tmp_path / "configs" / "recipes.toml").write_text(text)
    return load_registry(tmp_path / "configs")


@pytest.mark.parametrize("body, problem", [
    ('output = "nope"\ninputs = { material_coal = 1 }', "unknown output"),
    ('output = "material_radar_battery"\ninputs = { nope = 1 }', "unknown input"),
    ('output = "tool_pickaxe_rookie"\ninputs = { material_coal = 1 }', "tool"),
    ('output = "material_radar_battery"\ninputs = { material_coal = 1, tool_pickaxe_rookie = 1 }', "is a tool"),
    ('output = "material_radar_battery"\ninputs = { material_radar_battery = 1, material_coal = 1 }', "its own output"),
    ('output = "material_radar_battery"\ninputs = { material_coal = 0 }', "at least 1"),
    ('output = "material_radar_battery"\nquantity = 0\ninputs = { material_coal = 1 }', "quantity"),
    ('output = "material_radar_battery"\ninputs = {}', "inputs"),
    ('output = "material_radar_battery"\nmin_level = 5\ninputs = { material_coal = 1 }', "needs a skill"),
])
def test_bad_recipes_are_refused_at_load(tmp_path, body, problem):
    with pytest.raises(RegistryError, match=problem):
        _with_recipes(tmp_path, f'[bad]\nname = "Bad"\n{body}\n')


def test_a_good_recipe_loads(tmp_path):
    reg = _with_recipes(tmp_path, '[ok]\nname = "Ok"\noutput = "material_radar_battery"\nquantity = 3\nbits = 5\ninputs = { material_coal = 2 }\n')
    assert reg.recipe("ok").quantity == 3 and reg.recipe("ok").inputs == {"material_coal": 2}


# ---- the rules ---------------------------------------------------------------------------------------------------------------------------
async def test_craft_takes_exactly_the_inputs_and_bits_and_gives_the_output(db):
    user = await User.get(1)
    await stock(user, WEDGE, times=1, bits=WEDGE.bits + 7)
    await user.add_item("material_copper_ore", 3)  # (spare)
    made = await crafting.craft(user, "material_iron_wedge")
    assert made.items == {"material_iron_wedge": WEDGE.quantity} and made.bits == WEDGE.bits
    items = await user.items()
    assert items["material_iron_wedge"] == WEDGE.quantity and items["material_copper_ore"] == 3 and "material_iron_ore" not in items
    await user.refresh()
    assert user.purse == 7


async def test_craft_several_scales_everything(db):
    user = await User.get(1)
    await stock(user, WEDGE, times=4, bits=WEDGE.bits * 4)
    made = await crafting.craft(user, "material_iron_wedge", 4)
    assert made.items == {"material_iron_wedge": 4 * WEDGE.quantity} and made.bits == 4 * WEDGE.bits
    await user.refresh()
    assert await user.items() == {"material_iron_wedge": 4 * WEDGE.quantity} and user.purse == 0


async def test_a_short_input_or_short_bits_changes_nothing(db):
    user = await User.get(1)
    await stock(user, WEDGE, bits=WEDGE.bits * 2)
    await user.remove_item("material_hardwood", 1)  # one input short, bits and the others plenty
    before = await user.items()
    with pytest.raises(CraftError, match="Hardwood"):
        await crafting.craft(user, "material_iron_wedge")
    assert await user.items() == before
    await user.refresh()
    assert user.purse == WEDGE.bits * 2
    await user.add_item("material_hardwood", 1)
    await set_columns(user, purse=WEDGE.bits - 1)  # now only the bits are short
    with pytest.raises(CraftError, match="more bits"):
        await crafting.craft(user, "material_iron_wedge")
    assert await user.items() == {**before, "material_hardwood": 1} and (await User.get(1)).purse == WEDGE.bits - 1


async def test_asking_for_more_than_you_have_is_refused_whole(db):
    user = await User.get(1)
    await stock(user, BATTERY, times=2)
    with pytest.raises(CraftError):
        await crafting.craft(user, "material_radar_battery", 3)
    assert await user.item_quantity("material_radar_battery") == 0 and await user.item_quantity("material_coral_shard") == 2 * BATTERY.inputs["material_coral_shard"]


async def test_craftable_count_is_the_scarcest_input_or_the_bits(db):
    user = await User.get(1)
    await stock(user, WEDGE, times=5, bits=WEDGE.bits * 3)
    assert await crafting.craftable_count(user, WEDGE) == 3  # bits are the limit
    await set_columns(user, purse=10**9)
    await user.remove_item("material_iron_ore", 2 * WEDGE.inputs["material_iron_ore"])
    assert await crafting.craftable_count(user, WEDGE) == 3  # iron ore: 3 crafts left
    assert await crafting.craftable_count(user, BATTERY) == 0
    made = await crafting.craft(user, "material_iron_wedge", await crafting.craftable_count(user, WEDGE))
    assert made.times == 3 and await crafting.craftable_count(user, WEDGE) == 0


async def test_a_recipe_can_ask_for_a_skill_level(db):
    user = await User.get(1)
    await stock(user, GILDED, bits=GILDED.bits)
    assert await crafting.craftable_count(user, GILDED) == 0
    with pytest.raises(CraftError, match="level"):
        await crafting.craft(user, "material_gilded_wedge")
    assert await user.item_quantity("material_gold_ore") == GILDED.inputs["material_gold_ore"]  # nothing was taken
    await user.update_skill("foraging", lambda s: setattr(s, "xp", 10**6))
    assert await crafting.craftable_count(user, GILDED) == 1
    await crafting.craft(user, "material_gilded_wedge")
    assert await user.item_quantity("material_gilded_wedge") == 1


async def test_unknown_recipe_and_zero_times_are_refused(db):
    user = await User.get(1)
    with pytest.raises(CraftError):
        await crafting.craft(user, "nope")
    with pytest.raises(CraftError):
        await crafting.craft(user, "material_radar_battery", 0)


# ---- the screen --------------------------------------------------------------------------------------------------------------------------
async def test_the_workbench_is_one_button_away_from_the_inventory(db):
    nav, inter = await hub("inventory")
    await click(nav, inter, "Workbench")
    assert nav.screen.id == "craft" and "Radar Battery" in all_text(nav)
    await click(nav, inter, "Back")
    assert nav.screen.id == "inventory"


async def test_the_screen_crafts_one_ten_and_max_and_shows_the_result(db):
    user = await User.get(1)
    await stock(user, BATTERY, times=12)
    nav, inter = await hub("craft")
    sel = selects(nav)[0]
    await choose(nav, inter, sel, "material_radar_battery")
    assert "Coral Shard" in all_text(nav) and "✅" in all_text(nav)
    assert find_button(nav, "Craft 1") and not find_button(nav, "Craft 10").disabled
    await click(nav, inter, "Craft 1")
    assert nav.screen.id == "result" and "Radar Battery" in all_text(nav)
    assert await user.item_quantity("material_radar_battery") == BATTERY.quantity
    await click(nav, inter, "Back to the Workbench")
    assert nav.screen.id == "craft"
    await click(nav, inter, "Craft 10")
    assert await user.item_quantity("material_radar_battery") == 11 * BATTERY.quantity
    await click(nav, inter, "Back to the Workbench")
    assert find_button(nav, "Craft max (1)")
    await click(nav, inter, "Craft max (1)")
    assert await user.item_quantity("material_radar_battery") == 12 * BATTERY.quantity and await user.item_quantity("material_coral_shard") == 0
    await click(nav, inter, "Back to the Workbench")
    assert find_button(nav, "Craft 1").disabled and "❌" in all_text(nav)


async def test_the_screen_marks_what_is_missing_and_disables_crafting(db):
    nav, inter = await hub("craft")
    assert all(b.disabled for b in buttons(nav) if (b.label or "").startswith("Craft"))
    assert "❌" in all_text(nav)


# ---- the wiki -------------------------------------------------------------------------------------------------------------------------------
def test_the_wiki_explains_crafting_from_the_recipes():
    assert "crafting" in [t[0] for t in wiki.TOPICS]
    text = "\n".join(wiki.page("crafting"))
    assert "Workbench" in text and all(r.name in text for r in REG.recipes.values())
    assert "Workbench" in "\n".join(wiki.page("foraging"))  # (the wedges are no longer "buy it in the shop")
