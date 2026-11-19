import pytest

from cococap.registry import get_registry
from cococap.services import fishing, wiki
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
    page = all_blocks("fish") + all_blocks("fish2")
    for fish in (i for i in REG.items.values() if i.category == "fish"):
        assert fish.name in page and f"{fish.sell_price:,}" in page, fish.id
    assert "Slime Pond" in page and "Slimeflow River" in page and "The Bottomless" in page  # and where they live
    waters = all_blocks("waters") + all_blocks("waters2")
    for water in REG.fishing.waters:
        assert water.name in waters and f"level {fishing.water_level(REG, water.id)}" in waters
        for fish_id in water.fish:
            assert REG.item(fish_id).name in waters


def test_the_pet_page_lists_every_pet_its_bonus_and_its_chance():
    page = all_blocks("pets") + all_blocks("pets2")  # two pages, so each stays under Discord's text limit
    for pet in REG.pets.values():
        assert pet.name in page
        for bonus in pet.bonuses:
            assert bonus.text.format(v=bonus.value) in page
    assert "per orb" in page and "Hunt" in all_blocks("pets")


def test_the_tools_page_has_every_upgrade_step_with_what_it_costs():
    page = all_blocks("tools") + all_blocks("tools2") + all_blocks("tools3")  # axes, rods, then pickaxes / swords
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
    cat = REG.pets["drizzle"]
    stronger = cat.model_copy(update={"trait": cat.trait.model_copy(update={"value": 0.77})})
    monkeypatch.setitem(REG.pets, "drizzle", stronger)
    assert "77%" in all_blocks("pets2")  # change the data and the wiki changes with it


def test_every_item_can_be_found_by_browsing_its_skill():
    seen = set()
    for skill in wiki.SKILL_FILTERS:
        seen |= {i.id for i in wiki.items_for(skill, REG)}
    assert seen == {i for i, item in REG.items.items() if not item.star_of}  # (star variants sit under their base item)


async def test_the_wiki_screen_switches_topics_and_looks_items_up(db):
    nav, inter = await hub("wiki")
    assert "Two currencies" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Pick a topic"), "pets")
    assert "Familiar Orbs" in all_text(nav) and "Wiki: Pets" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Pick a topic"), "items")
    await choose(nav, inter, select_named(nav, "Pick a skill"), "fishing")
    await choose(nav, inter, select_named(nav, "Pick an item"), "fish_cod")
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
    opened, _ = await hub("wiki", topic="items", skill="fishing", item="fish_marlin")
    assert "Blue Marlin" in all_text(opened)


def test_the_foraging_page_explains_styles_and_wear_without_giving_the_answers_away():
    page = all_blocks("foraging")
    assert "chop style" in page and "Overhead" in page and "Sidecut" in page and "Undercut" in page and "Grain notes" in page
    assert "wedge" in page and "wear" in page and "Seasoned" in page
    assert all(g.name in page or g.name.split()[0] in page for g in REG.foraging.chopping.grains)
    # (the wiki teaches the game, it does not say which grain likes which style)
    assert not any(f"{g.name} likes" in page or f"{g.name}: {g.stance}" in page for g in REG.foraging.chopping.grains)


# ---- where to catch each fish -----------------------------------------------------------------------------------------------------------
def test_every_waters_chances_add_up_and_the_rare_ones_are_rarer():
    from cococap.services import fishing

    for water in REG.fishing.waters:
        chances = fishing.water_chances(water)
        assert sum(chances.values()) == pytest.approx(1.0) and all(c > 0 for c in chances.values()), water.id
        by_rate = sorted(water.fish.items(), key=lambda kv: -kv[1])
        assert chances[by_rate[0][0]] < chances[by_rate[-1][0]]  # the rarest is less likely than the catch-all


def test_chances_match_what_casting_really_gives():
    from random import Random

    from cococap.services import fishing

    water = REG.fishing.waters[0]
    rng, seen = Random(3), {}
    for _ in range(40_000):
        fish = fishing.roll_fish(rng, REG, water)
        seen[fish.id] = seen.get(fish.id, 0) + 1
    for fish_id, chance in fishing.water_chances(water).items():
        if chance > 0.02:
            assert seen.get(fish_id, 0) / 40_000 == pytest.approx(chance, rel=0.12), fish_id


def test_the_wiki_tells_you_the_best_water_for_every_fish():
    from cococap.services import fishing, wiki

    page = "\n".join(wiki.page_text("fish", REG)) if hasattr(wiki, "page_text") else "\n".join(wiki._fish(REG))
    fish = [i for i in REG.items.values() if i.category == "fish" and fishing.where_to_catch(i.id, REG)]
    assert fish and page.count("Max odds in") == len(fish)
    eel = next(i for i in fish if len(fishing.where_to_catch(i.id, REG)) > 1)
    best, chance = fishing.where_to_catch(eel.id, REG)[0]
    assert all(chance >= c for _, c in fishing.where_to_catch(eel.id, REG)) and f"Max odds in {best.emoji} {best.name}" in page
    assert "casts" in page and "Needs fishing level" in page


async def test_looking_up_a_fish_says_where_it_is_caught_not_a_raw_drop_rate(db):
    from cococap.services import fishing

    nav, inter = await hub("wiki")
    await choose(nav, inter, select_named(nav, "Pick a topic"), "items")
    await choose(nav, inter, select_named(nav, "Pick a skill"), "fishing")
    for fish_id in ("fish_muskie", "fish_cod", "fish_golden_koi"):
        nav.screen.item = fish_id
        await nav.screen.nav.refresh(inter)
        page = all_text(nav)
        best, chance = fishing.where_to_catch(fish_id, REG)[0]
        assert "Where to catch it" in page and f"Max odds in {best.emoji} {best.name}" in page and "Drop Rate" not in page, fish_id
        assert "Size" in page
    nav.screen.skill, nav.screen.item = "foraging", "food_acorn_mix"
    await nav.screen.nav.refresh(inter)
    assert "Drop Rate" in all_text(nav) and "Pet xp" in all_text(nav)  # other things still show their drop rate


def test_the_fishing_page_explains_double_hook():
    page = all_blocks("fishing")
    assert "Double Hook" in page and "Quick cast" in page and f"{REG.fishing.double_hook.window_seconds:g} seconds" in page


def test_every_item_has_wiki_text():
    from cococap.registry import get_registry

    missing = [i.id for i in get_registry().items.values() if not i.wiki]
    assert not missing, f"items without wiki text: {missing}"
