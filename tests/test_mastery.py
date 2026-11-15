"""Mastery: points from skill levels, branch-ordered nodes, trade-off stats that reach the tools, and the screen."""

import pytest

from cococap.registry import get_registry
from cococap.services import mastery
from cococap.services.equipment import equip, equipped_stats
from cococap.services.mastery import MasteryError
from cococap.user import User
from tests.test_hub import all_text, buttons, click, hub

REG = get_registry()
RULES = REG.mastery


async def level_up(user, skill, level):
    await user.add_xp(skill, User.level_to_xp(level) + 1)


# ---- the data --------------------------------------------------------------------------------------------------------------------
def test_every_tree_is_a_real_choice_not_everything_fits():
    for tree in RULES.trees:
        assert len(tree.branches) >= 3
        costs = [sum(n.cost for n in b.nodes) for b in tree.branches]
        most = mastery.points_earned(100, REG)
        assert sum(costs) > most >= max(costs)  # one full branch is within reach, all of them are not


def test_each_branch_has_a_trade_off_or_a_different_stat_so_branches_differ():
    for tree in RULES.trees:
        stats = [{e.stat for n in b.nodes for e in n.effects} for b in tree.branches]
        assert len({frozenset(s) for s in stats}) == len(stats)  # no two branches are the same


def test_mastery_stats_are_ones_the_game_reads():
    known = {"danger_reduction", "ore_yield", "braces", "rich_chance", "vault_gem", "bite_speed", "slips", "treasure_luck", "rare_luck", "boss_luck",
             "lifeline", "gold_rush", "geode", "hot_streak", "salvage", "chum",  # (the capstones: each has its own test in its skill's file)
             "crop_yield", "drop_luck", "seed_back", "evergreen", "heirloom", "haggler", "good_chop", "double_chop", "wear_slow", "shake", "windfall", "final_cut", "clean_cut"}
    used = {e.stat for t in RULES.trees for b in t.branches for n in b.nodes for e in n.effects}
    assert used <= known


def test_the_arithmetic_of_points():
    assert [mastery.points_earned(lv, REG) for lv in (1, 4, 5, 9, 10, 100)] == [0, 0, 1, 1, 2, 20]
    assert mastery.stats([]) == {}
    safe = mastery.stats(["steady_hands", "spare_braces"])
    assert safe == {"danger_reduction": 0.05, "braces": 1}
    assert mastery.stats(["pay_dirt", "motherlode"])["danger_reduction"] == pytest.approx(-0.08)  # trade-offs add up
    assert mastery.stats(["not_a_node"]) == {}


# ---- buying ---------------------------------------------------------------------------------------------------------------------
async def test_a_node_needs_its_level_and_a_free_point_and_the_one_before_it(db):
    user = await User.get(1)
    with pytest.raises(MasteryError, match="level 5"):
        await mastery.buy(user, "mining", "steady_hands")
    await level_up(user, "mining", 5)
    with pytest.raises(MasteryError, match="Take the node before"):
        await mastery.buy(user, "mining", "spare_braces")
    node = await mastery.buy(user, "mining", "steady_hands")
    assert node.name == "Steady Hands" and (await user.skill("mining")).mastery == ["steady_hands"]
    with pytest.raises(MasteryError, match="already"):
        await mastery.buy(user, "mining", "steady_hands")
    with pytest.raises(MasteryError, match="level 10"):
        await mastery.buy(user, "mining", "spare_braces")  # (level is not enough yet)
    with pytest.raises(MasteryError, match="no such node"):
        await mastery.buy(user, "mining", "nope")
    with pytest.raises(MasteryError, match="no Mastery tree"):
        await mastery.buy(user, "combat", "steady_hands")


async def test_you_cannot_spend_more_points_than_you_have(db):
    user = await User.get(1)
    await level_up(user, "mining", 10)  # 2 points
    await mastery.buy(user, "mining", "steady_hands")  # 1
    await mastery.buy(user, "mining", "pay_dirt")  # 1 (a second branch)
    with pytest.raises(MasteryError, match="needs 1 points"):
        await mastery.buy(user, "mining", "rich_veins")
    owned, level, free = await mastery.status(user, "mining")
    assert (owned, level, free) == (["steady_hands", "pay_dirt"], 10, 0)


async def test_each_skill_has_its_own_tree_and_points(db):
    user = await User.get(1)
    await level_up(user, "mining", 5)
    await mastery.buy(user, "mining", "steady_hands")
    assert (await mastery.status(user, "fishing"))[2] == 0 and (await user.skill("fishing")).mastery == []
    with pytest.raises(MasteryError):
        await mastery.buy(user, "fishing", "quick_bite")  # no fishing level yet


async def test_a_respec_clears_the_tree_for_bits_and_gives_the_points_back(db):
    user = await User.get(1)
    await level_up(user, "mining", 10)
    with pytest.raises(MasteryError, match="nothing"):
        await mastery.respec(user, "mining")
    await mastery.buy(user, "mining", "steady_hands")
    await mastery.buy(user, "mining", "spare_braces")
    with pytest.raises(MasteryError, match="costs"):
        await mastery.respec(user, "mining")  # no bits
    await user.refresh()
    start = user.purse
    await user.add_bits(RULES.respec_bits)
    assert await mastery.respec(user, "mining") == 2
    await user.refresh()
    assert user.purse == start and (await mastery.status(user, "mining"))[2] == 2 and (await user.skill("mining")).mastery == []


# ---- the effects reach the game ------------------------------------------------------------------------------------------------
async def test_owned_nodes_change_the_tool_stats_the_game_reads(db):
    user = await User.get(1)
    pick = await user.give_instance("rookiepickaxe")
    await equip(user, "mining", pick.id)
    assert (await equipped_stats(user, "mining")).stats.get("danger_reduction", 0) == 0
    await level_up(user, "mining", 10)
    await mastery.buy(user, "mining", "steady_hands")
    await mastery.buy(user, "mining", "spare_braces")
    stats = await equipped_stats(user, "mining")
    assert stats.stats["danger_reduction"] == pytest.approx(0.05) and stats.stats["braces"] == 1 and stats.power == REG.item("rookiepickaxe").tool.power


async def test_mastery_changes_how_a_mine_run_starts(db):
    from random import Random

    from cococap.services import mining

    user = await User.get(1)
    pick = await user.give_instance("rookiepickaxe")
    await equip(user, "mining", pick.id)
    plain = await mining.start_run(user, Random(1))
    await level_up(user, "mining", 10)
    await mastery.buy(user, "mining", "pay_dirt")
    await mastery.buy(user, "mining", "rich_veins")
    greedy = await mining.start_run(user, Random(1))
    assert greedy.yield_factor == pytest.approx(plain.yield_factor * 1.10)
    assert greedy.growth_factor > plain.growth_factor  # a creakier tunnel: the price of the ore
    assert greedy.rich_bonus == pytest.approx(0.04) and plain.rich_bonus == 0
    safe_user = await User.get(2)
    spick = await safe_user.give_instance("rookiepickaxe")
    await equip(safe_user, "mining", spick.id)
    await level_up(safe_user, "mining", 10)
    await mastery.buy(safe_user, "mining", "steady_hands")
    await mastery.buy(safe_user, "mining", "spare_braces")
    careful = await mining.start_run(safe_user, Random(1))
    assert careful.growth_factor < plain.growth_factor and careful.braces == plain.braces + 1


async def test_fishing_mastery_changes_bites_boss_odds_and_luck(db):
    from random import Random

    from cococap.services import fishing

    user = await User.get(1)
    rod = await user.give_instance("starter_rod")
    await equip(user, "fishing", rod.id)
    plain = await equipped_stats(user, "fishing")
    await level_up(user, "fishing", 10)
    await mastery.buy(user, "fishing", "big_game")
    stats = await equipped_stats(user, "fishing")
    assert stats.stats["boss_luck"] == 0.25 and stats.stats["bite_speed"] == pytest.approx(-0.05)
    bosses = lambda s: sum(bool(fishing.cast_line(s, Random(i), 0.0).boss) for i in range(6000))  # noqa: E731
    assert bosses(stats) > 1.15 * bosses(plain)  # more bosses...
    slow = fishing.typical_wait(stats.power, REG.fishing, stats.stats["bite_speed"])
    assert slow > fishing.typical_wait(plain.power, REG.fishing, 0)  # ...but slower bites


# ---- the screen ----------------------------------------------------------------------------------------------------------------
async def test_the_mastery_screen_shows_branches_and_takes_a_node(db):
    user = await User.get(1)
    await level_up(user, "mining", 5)
    nav, inter = await hub("mastery", skill="mining")
    text = all_text(nav)
    assert "Safe Digger" in text and "Greedy Digger" in text and "Gem Hunter" in text and "**1** point(s)" in text
    await click(nav, inter, "Safe Digger: Steady Hands")
    assert (await user.skill("mining")).mastery == ["steady_hands"] and "You took" in all_text(nav)
    await click(nav, inter, "Fishing")
    assert "Fishing Mastery" in all_text(nav) and "Angler" in all_text(nav)
    assert not [b for b in buttons(nav) if b.label.startswith("Angler") and not b.disabled]  # no fishing points yet


async def test_the_mastery_screen_respec_button_and_the_skill_pages_link_to_it(db):
    user = await User.get(1)
    await level_up(user, "mining", 5)
    await mastery.buy(user, "mining", "steady_hands")
    nav, inter = await hub("mastery", skill="mining")
    respec = next(b for b in buttons(nav) if b.label.startswith("Respec"))
    assert not respec.disabled
    await click(nav, inter, respec.label)
    assert "bits" in all_text(nav) and (await user.skill("mining")).mastery == ["steady_hands"]  # (no bits: nothing happened)
    for screen, skill in (("mining", "mining"), ("fish", "fishing")):
        nav, inter = await hub(screen)
        await click(nav, inter, "Mastery")
        assert nav.screen.id == "mastery" and nav.screen.skill == skill


def test_rich_lode_and_vault_gem_bonuses_really_change_what_a_mine_makes():
    from random import Random

    from cococap.services import mining as m

    def rich_cells(bonus):
        count = 0
        for seed in range(300):
            run = m.MineRun(REG.mining, REG, Random(seed), cursors=[2], rich_bonus=bonus)
            count += sum(kind == "rich" for depth in range(1, 6) for kind in run.signs(depth))
        return count

    assert rich_cells(0.3) > 1.5 * rich_cells(0)

    def vault_gems(bonus):
        found = 0
        for seed in range(2000):
            run = m.MineRun(REG.mining, REG, Random(seed), cursors=[2], vault_gem_bonus=bonus)
            run.depth = REG.mining.descent.floor - 1
            found += any(item in REG.mining.reactor.core_gems for item in run._descend(0, 0))
        return found

    assert vault_gems(2.0) > 2 * vault_gems(0)


def test_every_skill_with_a_tool_has_a_tree_of_three_branches_each_ending_in_a_capstone_worth_four_points():
    assert {t.skill for t in RULES.trees} == {"mining", "fishing", "farming", "foraging"}  # (combat is paused)
    for tree in RULES.trees:
        assert len(tree.branches) == 3
        for branch in tree.branches:
            assert len(branch.nodes) == 5 and branch.nodes[-1].description.startswith("CAPSTONE") and branch.nodes[-1].cost == 4 and branch.nodes[-1].level == 50
            assert not any(n.description.startswith("CAPSTONE") for n in branch.nodes[:-1])
            assert [n.level for n in branch.nodes] == sorted(n.level for n in branch.nodes)


async def test_farming_and_foraging_pages_link_to_their_mastery_and_it_opens(db):
    from cococap.services.equipment import equip as _equip  # noqa: F401

    for screen, skill in (("farm", "farming"), ("forage", "foraging")):
        nav, inter = await hub(screen)
        await click(nav, inter, "Mastery")
        assert nav.screen.id == "mastery" and nav.screen.skill == skill and f"{skill.title()} Mastery" in all_text(nav)
