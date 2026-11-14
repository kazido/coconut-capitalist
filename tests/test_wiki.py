import pytest

from cococap.registry import get_registry
from cococap.services import wiki
from tests.test_hub import all_text, choose, click, find_button, hub, select_named

REG = get_registry()


def all_blocks(topic):
    return "\n".join(wiki.page(topic, REG))


def test_every_topic_has_a_page_that_fits_a_discord_message():
    for topic, title, emoji in wiki.TOPICS:
        blocks = wiki.page(topic, REG)
        assert blocks and all(block.strip() for block in blocks), topic
        assert sum(len(b) for b in blocks) < 3600, (topic, sum(len(b) for b in blocks))  # leaves room for the panel around it
        assert all(len(b) <= 3500 for b in blocks)
    with pytest.raises(KeyError):
        wiki.page("nonsense", REG)


def test_the_wiki_covers_every_skill_and_the_systems_around_them():
    topics = {t for t, _, _ in wiki.TOPICS}
    assert {"mining", "farming", "foraging", "fishing", "pets", "party", "tools", "enchants", "pots", "waters", "fish", "items", "start"} <= topics


def test_the_fish_pages_list_every_fish_with_its_value_and_where_to_find_it():
    page = all_blocks("fish")
    for fish in (i for i in REG.items.values() if i.category == "fish"):
        assert fish.name in page and f"{fish.sell_price:,}" in page, fish.id
    assert "Quiet Pond" in page and "The Deep Sea" in page  # and where they live
    waters = all_blocks("waters")
    for water in REG.fishing.waters:
        assert water.name in waters and f"level {water.min_level}" in waters
        for fish_id in water.fish:
            assert REG.item(fish_id).name in waters


def test_the_pet_page_lists_every_pet_its_bonus_and_its_chance():
    page = all_blocks("pets")
    for pet in REG.pets.values():
        assert pet.name in page
        for bonus in pet.bonuses:
            assert bonus.text.format(v=bonus.value) in page
    assert "per orb" in page and "Hunt" in page


def test_the_tools_page_has_every_upgrade_step_with_what_it_costs():
    page = all_blocks("tools")
    for item in REG.items.values():
        if item.tool and item.tool.upgrade:
            up = item.tool.upgrade
            assert item.name in page and REG.item(up.to).name in page and f"{up.bits:,}" in page
            for material, quantity in up.items.items():
                assert f"{quantity:,} {REG.item(material).name}" in page


def test_the_pots_enchants_and_crop_pages_use_the_real_numbers():
    pots = all_blocks("pots")
    for bait in (i for i in REG.items.values() if i.bait):
        assert bait.name in pots
    for level in REG.fishing.pots.levels:
        assert f"holds {level.capacity}" in pots
    enchants = all_blocks("enchants")
    assert all(e.name in enchants for e in REG.enchants.values())
    farming = all_blocks("farming")
    assert all(c.name in farming for c in REG.items.values() if c.crop)


def test_the_party_page_states_the_bonus_for_each_size():
    page = all_blocks("party")
    for bonus in REG.economy.party_xp_bonus_by_size:
        assert f"+{bonus:.0%}" in page


def test_the_wiki_follows_the_data(monkeypatch):
    cat = REG.pets["cat"]
    stronger = cat.model_copy(update={"bonuses": [cat.bonuses[0].model_copy(update={"value": 0.77})]})
    monkeypatch.setitem(REG.pets, "cat", stronger)
    assert "77%" in all_blocks("pets")  # change the data and the wiki changes with it


def test_every_item_can_be_found_by_browsing_its_skill():
    seen = set()
    for skill in wiki.SKILL_FILTERS:
        seen |= {i.id for i in wiki.items_for(skill, REG)}
    assert seen == set(REG.items)


async def test_the_wiki_screen_switches_topics_and_looks_items_up(db):
    nav, inter = await hub("wiki")
    assert "Two currencies" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Pick a topic"), "pets")
    assert "Familiar Orbs" in all_text(nav) and "Wiki: Pets" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Pick a topic"), "items")
    await choose(nav, inter, select_named(nav, "Pick a skill"), "fishing")
    await choose(nav, inter, select_named(nav, "Pick an item"), "cod")
    page = all_text(nav)
    assert "Cod" in page and "Rarity" in page


async def test_item_lists_longer_than_a_menu_get_pages(db):
    assert len(wiki.items_for("fishing", REG)) > 25  # (more fish, bait and fishing gear than one menu holds)
    nav, inter = await hub("wiki", topic="items", skill="fishing")
    assert find_button(nav, "1/2")
    first = {o.value for s in nav.walk_children() if getattr(s, "placeholder", "").startswith("Pick an item") for o in s.options}
    await click(nav, inter, None, "▶️")
    menu = next(s for s in nav.walk_children() if getattr(s, "placeholder", "").startswith("Pick an item"))
    assert "(2/2)" in menu.placeholder and not first & {o.value for o in menu.options}  # the second page has the rest
    assert len(first) + len(menu.options) == len(wiki.items_for("fishing", REG))


async def test_the_wiki_is_on_the_more_page_and_the_command_opens_it(db):
    nav, inter = await hub("more")
    assert "Wiki" in all_text(nav)
    opened, _ = await hub("wiki", topic="items", skill="fishing", item="marlin")
    assert "Blue Marlin" in all_text(opened)
