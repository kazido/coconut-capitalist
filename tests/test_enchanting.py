from random import Random

import pytest

from cococap.registry import get_registry
from cococap.screens import fish as fish_screen
from cococap.services import enchanting, equipment, scrolls
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
            assert item.category == "scroll" and item.sell_price > 0
            assert scrolls.scroll_skills(item.id, REG), f"nothing drops {item.id}"


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
def test_every_skill_has_three_scrolls_of_its_own_and_shares_the_same_three_global_ones():
    own = {"mining": {"scroll_iron_frame", "scroll_veinfinder", "scroll_bounty"}, "fishing": {"scroll_lure", "scroll_steady_line", "scroll_deepcall"},
           "foraging": {"scroll_sharp_eye", "scroll_seasoned", "scroll_double_strike"}, "farming": {"scroll_fertile", "scroll_seedkeeper", "scroll_gleaner"}}
    shared = {"scroll_keen", "scroll_scholar", "scroll_appraiser"}
    for skill, mine in own.items():
        found = {i.id for i in REG.items.values() if i.category == "scroll" and skill in scrolls.scroll_skills(i.id, REG)}
        assert found == mine | shared, skill  # the same number (and the same global ones) in every skill
        assert all(REG.item(i).skill == skill for i in mine)
    for i in shared:  # a global scroll fits every kind of tool
        assert REG.item(i).skill is None and set(REG.enchants[REG.item(i).scroll.enchant].applies_to) >= {"pickaxe", "axe", "rod", "can"}


def test_scrolls_are_rare_about_one_every_few_hours_in_each_skill():
    # per hour of play: mining ~720 cells, foraging ~45 private trees, farming ~9 growth cycles (nine plots), fishing ~2 bosses and a chest now and then
    per_hour = {"mining": 720 / REG.scrolls.mining.odds, "foraging": 45 / REG.scrolls.foraging.odds, "farming": 9 / REG.scrolls.farming.odds}
    boss = sum(r.chance for r in REG.fishing.boss.loot if r.item.startswith("scroll_"))
    per_hour["fishing"] = 1.5 * boss  # (bosses are hooked about 1 in 80 casts and not every one is landed)
    for skill, rate in per_hour.items():
        assert 1 / 6 <= rate <= 1 / 2, f"{skill}: a scroll every {1 / rate:.1f} hours"


def test_the_scroll_roll_drops_at_its_odds_from_the_skills_own_pool():
    rng = Random(1)
    hits = [scrolls.roll("foraging", rng, REG) for _ in range(30_000)]
    got = [h for h in hits if h]
    assert len(got) == pytest.approx(30_000 / REG.scrolls.foraging.odds, rel=0.25)
    assert set(got) <= set(REG.scrolls.foraging.pool) and len(set(got)) == 6


# ---- the screen -----------------------------------------------------------------------------------------------------------
async def test_the_enchant_screen_picks_a_scroll_then_a_tool(db):
    user, rod = await with_tool("starter_rod", "fishing", scrolls={"scroll_lure": 1})
    axe = await user.give_instance("starter_axe")
    nav, inter = await hub("tools")
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
    for arrow in list(boss.truth):  # (what the boss really wants, which a mirror boss flips)
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


async def test_the_scholar_scroll_adds_xp_and_the_appraiser_scroll_adds_to_what_the_skills_items_sell_for(db):
    from cococap.services import shop
    from cococap.services.party import xp_multiplier

    user, pick = await with_tool("rookiepickaxe", "mining", scrolls={"scroll_scholar": 2, "scroll_appraiser": 2})
    xp_before, sale_before = await xp_multiplier(user.id, REG, "mining"), await shop.haggle(user, REG.item("copper_ore"), REG)
    for scroll in ("scroll_scholar", "scroll_scholar", "scroll_appraiser", "scroll_appraiser"):
        await enchanting.apply_scroll(user, scroll, pick.id, REG)
    assert await xp_multiplier(user.id, REG, "mining") == pytest.approx(xp_before * 1.10)  # +5% a level, two levels
    assert await shop.haggle(user, REG.item("copper_ore"), REG) == pytest.approx(sale_before + 0.08)
    assert await shop.haggle(user, REG.item("apple"), REG) == 0  # (it only helps the tool's own skill)
    assert await xp_multiplier(user.id, REG, "foraging") == pytest.approx(xp_before)  # (and its xp)
