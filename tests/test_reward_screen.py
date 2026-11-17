"""The shared reward screen: one layout everywhere, rare drops on pages of their own with their drop rate (from the loot tables)."""

from cococap.registry import get_registry
from cococap.services import odds
from cococap.ui import flair
from cococap.ui.rewards import drop_rate_line, rewards_result

REG = get_registry()


async def noop(interaction):
    return None


def test_the_reward_screen_lists_items_then_bits_and_xp_then_notes():
    result = rewards_result("Harvest!", items={"material_copper_ore": 3, "material_coal": 0}, bits=1200, xp=45, headline=["⛏️ Row 3"], notes=["a note"])
    assert not result.then
    head, items, totals, note = result.lines
    assert head == "⛏️ Row 3" and "**+3** Copper Ore" in items and "Coal" not in items
    assert "1,200" in totals and "+45" in totals and note == "a note"


def test_an_empty_reward_still_says_so():
    assert rewards_result("Nothing", items={}).lines == ["Nothing this time."]


def test_rare_drops_leave_the_reward_screen_and_get_a_page_each_in_order():
    assert flair.level(REG.item("scroll_keen")) == 2 and flair.level(REG.item("material_iron_wedge")) == 1
    result = rewards_result("TIMBER!", items={"material_copper_ore": 2, "material_iron_wedge": 1, "scroll_keen": 1}, xp=10, odds=odds.foraging(),
                            again=noop, again_label="Another tree", back=noop, back_label="Back to foraging", actions=[("Donate", "🌱", noop)])
    text = "\n".join(result.lines)
    assert "Copper Ore" in text and "Scroll" not in text and "Wedge" not in text  # nothing rare on the plain screen
    assert result.again is None and not result.actions  # the choices wait for the last page
    assert [p.title for p in result.then] == ["A super rare find!", "A rare find!"]  # the best find first
    first, last = result.then
    assert "SUPER RARE" in first.lines[0] and "1 in 2,200" not in first.lines[1]
    assert first.again is None and first.then == []
    assert last.again is noop and last.back_label == "Back to foraging" and last.actions == [("Donate", "🌱", noop)]


def test_drop_rate_is_worked_out_from_the_loot_tables():
    pool = REG.scrolls.foraging.pool
    n = REG.scrolls.foraging.odds * len(pool)
    page = rewards_result("x", items={pool[0]: 1}, odds=odds.foraging()).then[0]
    assert f"1 in {n:,} trees felled" in page.lines[1]
    mine = odds.mining(REG)("scroll_keen")
    assert mine.one_in == REG.scrolls.mining.odds * len(REG.scrolls.mining.pool)
    # a table item: the first that drops wins, so a later item needs the earlier ones to miss first
    table = REG.mining.depth_tables[-1]
    first, second = table[0], table[1]
    rate = lambda i: REG.item(i).drop.rate  # noqa: E731
    assert abs(odds.table_chance(table, first, REG) - 1 / rate(first)) < 1e-12
    assert abs(odds.table_chance(table, second, REG) - (1 - 1 / rate(first)) / rate(second)) < 1e-12
    assert odds.fishing_chest(REG)("spirit_of_the_sea").text() == "1 in 1,000 chests"


def test_without_a_table_only_the_rarity_is_shown():
    item = REG.item("scroll_keen")
    assert "Drop rate" not in drop_rate_line(item, None) and "Rarity" in drop_rate_line(item, None)
    page = rewards_result("x", items={"scroll_keen": 1}).then[0]
    assert "Rarity" in page.lines[1] and " in " not in page.lines[1]


def test_a_super_rare_only_reward_still_has_a_first_screen():
    result = rewards_result("x", items={"scroll_keen": 1})
    assert result.lines and result.then


def test_the_rare_drop_screen_shows_a_species_drops_rate():
    from cococap.registry import get_registry
    from cococap.services import odds

    from tests.conftest import with_signature_drops

    reg = with_signature_drops(get_registry())
    sp = reg.foraging.species_of("redwood")
    rare = sp.drops[1]
    assert odds.foraging(reg)(rare.item).text() == f"1 in {round(1 / rare.rate):,} drop rolls"
    assert drop_rate_line(reg.item(rare.item), odds.foraging(reg)(rare.item)).startswith("🎲 **Drop rate:** 1 in")
