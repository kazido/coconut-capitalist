"""The shared reward screen: one layout everywhere; rare drops go to a popup embed with their drop rate (from the loot tables)."""

from cococap.registry import get_registry
from cococap.services import odds
from cococap.ui import flair
from cococap.ui.popup import rare_embed
from cococap.ui.rewards import drop_rate_line, rewards_result

REG = get_registry()


async def noop(interaction):
    return None


def test_the_reward_screen_lists_items_then_bits_and_xp_then_notes():
    result = rewards_result("Harvest!", items={"material_copper_ore": 3, "material_coal": 0}, bits=1200, xp=45, headline=["⛏️ Row 3"], notes=["a note"])
    assert not result.rare
    head, items, totals, note = result.lines
    assert head == "⛏️ Row 3" and "**+3** Copper Ore" in items and "Coal" not in items
    assert "1,200" in totals and "+45" in totals and note == "a note"


def test_an_empty_reward_still_says_so():
    assert rewards_result("Nothing", items={}).lines == ["Nothing this time."]


def test_rare_drops_are_listed_like_any_item_and_handed_to_the_popup_best_first():
    assert flair.level(REG.item("scroll_double_strike")) == 2 and flair.level(REG.item("material_iron_wedge")) == 1
    result = rewards_result("TIMBER!", items={"material_copper_ore": 2, "material_iron_wedge": 1, "scroll_double_strike": 1}, xp=10, odds=odds.foraging(),
                            again=noop, again_label="Another tree", back=noop, back_label="Back to foraging", actions=[("Donate", "🌱", noop)])
    text = "\n".join(result.lines)
    assert "Copper Ore" in text and "Wedge" in text and "Double Strike" in text  # everything is on the one loot screen
    assert result.again is noop and result.actions == [("Donate", "🌱", noop)]  # with the next-action buttons on it
    assert [f[1].id for f in result.rare] == ["scroll_double_strike", "material_iron_wedge"]  # the best find first


def test_drop_rate_is_worked_out_from_the_loot_tables():
    pool = REG.scrolls.foraging.pool
    n = REG.scrolls.foraging.odds * len(pool)
    embed = rare_embed(rewards_result("x", items={pool[0]: 1}, odds=odds.foraging()).rare)
    assert f"1 in {n:,} trees felled" in embed.fields[0].value
    # a table item: the first that drops wins, so a later item needs the earlier ones to miss first
    table = REG.mining.depth_tables[-1]
    first, second = table[0], table[1]
    rate = lambda i: REG.item(i).drop.rate  # noqa: E731
    assert abs(odds.table_chance(table, first, REG) - 1 / rate(first)) < 1e-12
    assert abs(odds.table_chance(table, second, REG) - (1 - 1 / rate(first)) / rate(second)) < 1e-12
    assert odds.fishing_chest(REG)("spirit_of_the_sea").text() == "1 in 1,000 chests"


def test_without_a_table_only_the_rarity_is_shown():
    item = REG.item("scroll_double_strike")
    assert "Drop rate" not in drop_rate_line(item, None) and "Rarity" in drop_rate_line(item, None)
    embed = rare_embed(rewards_result("x", items={"scroll_double_strike": 1}).rare)
    assert " in " not in embed.fields[0].value


def test_a_rare_only_reward_still_lists_the_item():
    result = rewards_result("x", items={"scroll_double_strike": 1})
    assert "Double Strike" in "\n".join(result.lines) and result.rare


def test_a_species_drops_rate_reaches_the_popup():
    from tests.conftest import with_signature_drops

    reg = with_signature_drops(get_registry())
    sp = reg.foraging.species_of("redwood")
    rare = sp.drops[1]
    assert odds.foraging(reg)(rare.item).text() == f"1 in {round(1 / rare.rate):,} drop rolls"
    assert drop_rate_line(reg.item(rare.item), odds.foraging(reg)(rare.item)).startswith("🎲 **Drop rate:** 1 in")
