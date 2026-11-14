from random import Random

import pytest

from cococap.registry import get_registry
from cococap.screens import fish as fish_screen
from cococap.services import enchanting, equipment
from cococap.services import fishing as f
from cococap.services import foraging as forage
from cococap.services.equipment import equip, effective_stats
from cococap.user import User
from tests.test_hub import all_text, choose, click, find_button, hub, select_named

REG = get_registry()


async def with_tool(template, skill, user_id=1, scrolls=None):
    user = await User.get(user_id)
    inst = await user.give_instance(template)
    await equip(user, skill, inst.id)
    for scroll, quantity in (scrolls or {}).items():
        await user.add_item(scroll, quantity)
    return user, inst


# ---- the data ---------------------------------------------------------------------------------------------------------
def test_every_enchant_has_a_scroll_somewhere_it_can_be_found():
    scrolled = {i.scroll.enchant for i in REG.items.values() if i.scroll}
    assert scrolled == set(REG.enchants) - {"soloist"}  # soloist has its own story
    for item in REG.items.values():
        if item.scroll:
            assert item.category == "scroll" and item.sell_price == 0
            loot_rows = [r.item for r in (*REG.fishing.treasure.loot, *REG.fishing.boss.loot)]
            found_in_play = item.drop is not None or item.id in loot_rows
            assert found_in_play, f"nothing drops {item.id}"


def test_every_kind_of_tool_with_an_upgrade_chain_can_be_enchanted():
    kinds = {k for e in REG.enchants.values() for k in e.applies_to}
    assert {"pickaxe", "axe", "rod"} <= kinds


# ---- applying a scroll --------------------------------------------------------------------------------------------------
async def test_a_scroll_is_used_up_and_puts_one_level_of_its_enchant_on_the_tool(db):
    user, rod = await with_tool("starter_rod", "fishing", scrolls={"scroll_lure": 2})
    done = await enchanting.apply_scroll(user, "scroll_lure", rod.id, REG)
    assert done.enchants == {"lure": 1} and await user.item_quantity("scroll_lure") == 1
    again = await enchanting.apply_scroll(user, "scroll_lure", rod.id, REG)
    assert again.enchants == {"lure": 2} and await user.item_quantity("scroll_lure") == 0
    assert effective_stats(again, REG).stats["bite_speed"] == pytest.approx(0.2)


async def test_it_only_fits_the_right_kind_of_tool_and_never_past_the_maximum_and_a_refusal_keeps_the_scroll(db):
    user, axe = await with_tool("starter_axe", "foraging", scrolls={"scroll_lure": 1, "scroll_keen": 5})
    with pytest.raises(enchanting.EnchantError, match="fits a rod"):
        await enchanting.apply_scroll(user, "scroll_lure", axe.id, REG)
    assert await user.item_quantity("scroll_lure") == 1
    for _ in range(REG.enchant("keen").max_level):
        await enchanting.apply_scroll(user, "scroll_keen", axe.id, REG)
    with pytest.raises(enchanting.EnchantError, match="highest level"):
        await enchanting.apply_scroll(user, "scroll_keen", axe.id, REG)
    assert await user.item_quantity("scroll_keen") == 5 - REG.enchant("keen").max_level


async def test_you_cannot_enchant_someone_elses_tool_or_with_a_scroll_you_do_not_have(db):
    _, rod = await with_tool("starter_rod", "fishing", user_id=1)
    thief = await User.get(2)
    await thief.add_item("scroll_lure", 1)
    with pytest.raises(enchanting.EnchantError, match="don't own"):
        await enchanting.apply_scroll(thief, "scroll_lure", rod.id, REG)
    mine, rod2 = await with_tool("starter_rod", "fishing", user_id=3)
    with pytest.raises(enchanting.EnchantError, match="don't have"):
        await enchanting.apply_scroll(mine, "scroll_lure", rod2.id, REG)
    with pytest.raises(enchanting.EnchantError, match="isn't a scroll"):
        await enchanting.apply_scroll(mine, "cod", rod2.id, REG)


async def test_keen_works_on_every_tool(db):
    for template, skill, uid in (("starter_rod", "fishing", 1), ("starter_axe", "foraging", 2), ("rookiepickaxe", "mining", 3)):
        user, tool = await with_tool(template, skill, uid, scrolls={"scroll_keen": 1})
        before = effective_stats(tool, REG).power
        done = await enchanting.apply_scroll(user, "scroll_keen", tool.id, REG)
        assert effective_stats(done, REG).power == before + 1


# ---- the enchants really do something -------------------------------------------------------------------------------------
def stats_with(**stats):
    return equipment.EffectiveStats(power=3, requirement=0, stats={"power": 3.0, **stats})


def test_lure_makes_fish_bite_sooner():
    rules = REG.fishing
    plain = sum(f.wait_seconds(3, rules, Random(i)) for i in range(300)) / 300
    lured = sum(f.wait_seconds(3, rules, Random(i), bite_speed=0.3) for i in range(300)) / 300
    assert lured == pytest.approx(plain * 0.7, rel=0.01)
    assert f.wait_seconds(3, rules, Random(1), bite_speed=5) == pytest.approx(f.wait_seconds(3, rules, Random(1)) * 0.4)  # capped


def test_steady_line_forgives_more_wrong_arrows_and_the_cast_uses_it():
    assert f.slips_allowed(3, REG.fishing) == 0 and f.slips_allowed(3, REG.fishing, 2) == 2
    cast = f.cast_line(stats_with(slips=2, bite_speed=0.2), Random(1), 0, REG)
    assert cast.slips_left == 2
    assert cast.bite_at < f.cast_line(stats_with(), Random(1), 0, REG).bite_at


def test_sharp_eye_makes_good_chops_more_likely():
    rules = REG.foraging
    good = lambda bonus: sum(forage.Spot().swing(10, rules, Random(i), bonus).good for i in range(4000))  # noqa: E731
    assert good(0.2) > good(0) + 500
    assert good(0) / 4000 == pytest.approx(rules.chopping.good_chop_chance, abs=0.03)


async def test_iron_frame_slows_the_mines_pressure(db):
    from cococap.services import mining

    user, pick = await with_tool("rookiepickaxe", "mining", scrolls={"scroll_iron_frame": 2})
    plain = (await mining.start_run(user, Random(1))).growth_factor
    await enchanting.apply_scroll(user, "scroll_iron_frame", pick.id, REG)
    await enchanting.apply_scroll(user, "scroll_iron_frame", pick.id, REG)
    assert (await mining.start_run(user, Random(1))).growth_factor == pytest.approx(plain - 0.06)


# ---- finding scrolls ------------------------------------------------------------------------------------------------------
def test_scrolls_drop_from_chopping_and_mining_and_fishing_bosses_and_chests():
    foraging_drops = {i.id for i in forage.drop_pool(REG)}
    assert {"scroll_keen", "scroll_sharp_eye"} <= foraging_drops
    deep = REG.mining.depth_tables[-1]
    assert "scroll_iron_frame" in deep
    assert {r.item for r in REG.fishing.boss.loot} >= {"scroll_lure", "scroll_steady_line", "scroll_keen"}
    assert {r.item for r in REG.fishing.treasure.loot} >= {"scroll_lure", "scroll_steady_line"}


# ---- the screen -----------------------------------------------------------------------------------------------------------
async def test_the_enchant_screen_picks_a_scroll_then_a_tool(db):
    user, rod = await with_tool("starter_rod", "fishing", scrolls={"scroll_lure": 1})
    axe = await user.give_instance("starter_axe")
    nav, inter = await hub("inventory")
    await click(nav, inter, "Enchant")
    assert nav.screen.id == "enchant"
    await choose(nav, inter, select_named(nav, "Pick a scroll"), "scroll_lure")
    menu = select_named(nav, "Put it on")
    assert [o.value for o in menu.options] == [str(rod.id)]  # the axe can't take it
    await choose(nav, inter, menu, str(rod.id))
    assert "Lure" in all_text(nav) and "is now on your Starter Rod [Lure]" in all_text(nav)
    assert (await user.instance(rod.id)).enchants == {"lure": 1} and await user.item_quantity("scroll_lure") == 0
    assert axe.id and find_button(nav, "Back to inventory")


async def test_the_enchant_screen_without_scrolls_says_where_to_find_them(db):
    nav, _ = await hub("enchant")
    assert "no scrolls" in all_text(nav) and "treasure chests" in all_text(nav)


async def test_a_boss_can_drop_a_scroll_you_can_then_use(db):
    class Lucky(Random):
        def randint(self, a, b):
            return a

        def random(self):
            return 0.0

    user, rod = await with_tool("starter_rod", "fishing")
    boss = f.cast_line(equipment.EffectiveStats(power=3, requirement=0, stats={"power": 3.0}), Lucky(1), 0, REG)
    boss.hook(boss.bite_at + 1)
    for arrow in list(boss.pattern):
        boss.press(arrow, boss.bite_at + 2)
    won = await f.defeat_boss(user, boss, Lucky(2), REG)
    assert won.items["scroll_lure"] == 1 and await user.item_quantity("scroll_lure") == 1
    await enchanting.apply_scroll(user, "scroll_lure", rod.id, REG)
    assert (await user.instance(rod.id)).enchants["lure"] == 1
    assert fish_screen  # (the screen module is what shows the loot)


async def test_if_the_enchant_fails_the_scroll_is_given_back(db, monkeypatch):
    user, rod = await with_tool("starter_rod", "fishing", scrolls={"scroll_lure": 1})

    async def broken(*_args, **_kwargs):
        raise RuntimeError("database hiccup")

    monkeypatch.setattr(enchanting, "add_enchant", broken)
    with pytest.raises(RuntimeError):
        await enchanting.apply_scroll(user, "scroll_lure", rod.id, REG)
    assert await user.item_quantity("scroll_lure") == 1 and (await user.instance(rod.id)).enchants == {}
