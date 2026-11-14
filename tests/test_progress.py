"""Coconut Level (global progress): milestone points that can only be earned once, the Bestiary, and the Home/Progress screens."""

import random

import pytest
from discord import ui

from cococap.models.pethouse import OwnedPet, Pethouse
from cococap.registry import get_registry
from cococap.services import combat, pets, progress
from cococap.user import SKILL_MODELS, User
from tests.test_combat import foe, hero
from tests.test_hub import all_text, buttons, click, hub, select_named

REG = get_registry()
RULES = REG.progress
SKILLS = progress.SKILLS


def empty_snapshot(**changes) -> progress.Snapshot:
    snap = progress.Snapshot(skills={name: SKILL_MODELS[name]() for name in SKILLS}, rank=0, pethouse=Pethouse(), owned_templates=set())
    for key, value in changes.items():
        setattr(snap, key, value)
    return snap


def maxed_snapshot() -> progress.Snapshot:
    """Someone who has done absolutely everything, several times over."""
    skills = {name: SKILL_MODELS[name](xp=User.level_to_xp(RULES.skills.max_level + 20) + 1) for name in SKILLS}
    for ladder in RULES.ladders:
        skill, stat = ladder.stat.split(".")
        setattr(skills[skill].stats, stat, 10**9)
    for n in range(1, 10):
        getattr(skills["farming"].farm, f"plot_{n}").unlocked = True
    skills["combat"].kills = {e: 10**9 for e in REG.enemies}
    top_xp = pets.level_xp(REG.economy.pets.max_level, REG)
    house = Pethouse(pets={p: OwnedPet(stars=REG.economy.pets.max_stars + 3, xp=top_xp) for p in REG.pets})
    return empty_snapshot(skills=skills, rank=len(REG.ranks) + 5, pethouse=house, owned_templates=set(progress.tool_levels(REG)))


# ---- the arithmetic ---------------------------------------------------------------------------------------------------------
def test_a_brand_new_player_is_level_zero_with_no_points():
    p = progress.build(empty_snapshot(), REG)
    assert (p.points, p.level, p.into) == (0, 0, 0) and p.tier.name == RULES.tiers[0].name


def test_skill_levels_pay_more_above_the_threshold_and_stop_at_the_max():
    s = RULES.skills
    assert progress.skill_points(1, RULES) == 0
    assert progress.skill_points(2, RULES) == s.per_level
    assert progress.skill_points(s.after_level, RULES) == (s.after_level - 1) * s.per_level
    assert progress.skill_points(s.after_level + 1, RULES) == (s.after_level - 1) * s.per_level + s.per_level_after
    top = progress.skill_points(s.max_level, RULES)
    assert top == (s.after_level - 1) * s.per_level + (s.max_level - s.after_level) * s.per_level_after
    assert progress.skill_points(s.max_level + 40, RULES) == top  # nothing for levels past the max


def test_points_become_levels_at_points_per_level():
    assert progress.level_of(0, RULES) == (0, 0)
    assert progress.level_of(RULES.points_per_level - 1, RULES) == (0, RULES.points_per_level - 1)
    assert progress.level_of(RULES.points_per_level * 3 + 7, RULES) == (3, 7)


def test_tiers_change_at_their_levels_and_have_colors():
    for tier in RULES.tiers:
        assert progress.tier_of(tier.from_level, RULES) == tier
        if tier.from_level:
            assert progress.tier_of(tier.from_level - 1, RULES) != tier
    assert progress.tier_of(10**6, RULES) == RULES.tiers[-1]


def test_every_counter_in_the_data_is_a_real_stat():
    skills = {name: SKILL_MODELS[name]() for name in SKILLS}
    for ladder in RULES.ladders:
        assert progress.stat_value(skills, ladder.stat) == 0, ladder.stat


def test_a_counter_pays_each_step_once_you_pass_it():
    ladder = next(l for l in RULES.ladders if l.stat == "fishing.fish_caught")
    snap = empty_snapshot()
    snap.skills["fishing"].stats.fish_caught = ladder.steps[1] - 1
    before = progress.build(snap, REG)
    snap.skills["fishing"].stats.fish_caught = ladder.steps[1]
    after = progress.build(snap, REG)
    assert after.points - before.points == ladder.points  # exactly the step reached


def test_next_up_lists_the_counters_closest_to_paying():
    snap = empty_snapshot()
    snap.skills["fishing"].stats.fish_caught = 95  # 95 of 100
    snap.skills["foraging"].stats.trees_chopped = 10
    first = progress.build(snap, REG).next_up(2)[0]
    assert first[0] == "Fish caught" and first[1:] == (95, 100, 10)


# ---- it cannot be ground ----------------------------------------------------------------------------------------------------------
def test_doing_everything_gives_exactly_the_maximum_and_doing_more_adds_nothing():
    p = progress.build(maxed_snapshot(), REG)
    assert p.points == p.max_points > 0
    assert all(c.points == c.max_points for c in p.categories)
    snap = maxed_snapshot()
    snap.skills["fishing"].stats.fish_caught *= 1000
    snap.skills["combat"].kills = {e: n * 1000 for e, n in snap.skills["combat"].kills.items()}
    assert progress.build(snap, REG).points == p.points  # grinding past the last milestone is worth nothing


def test_the_maximum_is_a_sensible_level():
    p = progress.build(maxed_snapshot(), REG)
    assert 90 <= p.level <= 130 and progress.tier_of(p.level, RULES) == RULES.tiers[-1]  # finishing everything reaches the top tier


# ---- the sources -------------------------------------------------------------------------------------------------------------------
def test_ranks_pets_stars_and_max_level_pets_each_pay():
    snap = empty_snapshot(rank=3, pethouse=Pethouse(pets={
        "cat": OwnedPet(stars=3, xp=pets.level_xp(REG.economy.pets.max_level, REG)), "dog": OwnedPet(stars=1)}))
    cats = {c.key: c for c in progress.build(snap, REG).categories}
    assert cats["ranks"].points == 3 * RULES.ranks.per_rank
    assert [e.points for e in cats["pets"].entries] == [2 * RULES.pets.per_pet, 2 * RULES.pets.per_extra_star, RULES.pets.maxed_level]


def test_only_your_best_tool_of_each_kind_counts():
    levels = progress.tool_levels(REG)
    assert levels["starter_axe"] == ("axe", 1) and {kind for kind, _ in levels.values()} == {"axe", "pickaxe", "rod", "sword"}
    chain = sorted((lv, tid) for tid, (kind, lv) in levels.items() if kind == "axe")
    snap = empty_snapshot(owned_templates={chain[0][1], chain[2][1]})  # an old axe and a better one
    gear = next(c for c in progress.build(snap, REG).categories if c.key == "gear")
    axe = next(e for e in gear.entries if e.label == "Best axe")
    assert axe.points == 2 * RULES.tools.per_level  # level 3: two levels above the first


def test_unlocked_farm_plots_pay_but_the_free_plot_does_not():
    snap = empty_snapshot()
    snap.skills["farming"].farm.plot_1.unlocked = True
    snap.skills["farming"].farm.plot_2.unlocked = True
    snap.skills["farming"].farm.plot_3.unlocked = True
    gear = next(c for c in progress.build(snap, REG).categories if c.key == "gear")
    plots = next(e for e in gear.entries if e.label == "Farm plots")
    assert plots.points == 2 * RULES.farming.per_plot  # plots 2 and 3 (plot 1 is free)


def test_bestiary_pays_by_kill_milestones_and_bosses_pay_more():
    snap = empty_snapshot()
    snap.skills["combat"].kills = {"zombie": RULES.bestiary.steps[1], "gravewarden": 1}
    bestiary = next(c for c in progress.build(snap, REG).categories if c.key == "bestiary")
    by_name = {e.label: e for e in bestiary.entries}
    assert by_name["Zombie"].points == 2 * RULES.bestiary.points
    assert by_name["The Gravewarden"].points == RULES.bestiary.boss_points
    assert by_name["Skeleton"].points == 0


async def test_a_real_player_gains_points_from_real_progress(db):
    user = await User.get(1)
    before = await progress.progress_of(user)
    await user.add_xp("fishing", User.level_to_xp(10) + 1)
    await user.update_skill("fishing", lambda s: setattr(s.stats, "fish_caught", 120))
    after = await progress.progress_of(user)
    expected = progress.skill_points(10, RULES) + 2 * next(l for l in RULES.ladders if l.stat == "fishing.fish_caught").points
    assert after.points - before.points == expected


# ---- the Bestiary records ---------------------------------------------------------------------------------------------------------
def won(foe_unit):
    battle = combat.Battle(REG.combat, [hero(attack=500), foe_unit], random.Random(0))
    battle.start()
    battle.play("slash", foe_unit.id)
    assert battle.outcome == "win"
    return battle


async def test_a_win_counts_kills_per_enemy_and_boss_kills(db):
    user = await User.get(1)
    zombie = combat.enemy_unit(REG.enemies["zombie"], "e1")
    zombie.hp = zombie.max_hp = 5
    await combat.settle(user, won(zombie), REG, random.Random(1))
    await combat.settle(user, won(combat.enemy_unit(REG.enemies["zombie"], "e1")), REG, random.Random(1))
    boss = combat.enemy_unit(REG.enemies["gravewarden"], "e1")
    boss.hp = boss.max_hp = 5
    await combat.settle(user, won(boss), REG, random.Random(1))
    skill = await user.skill("combat")
    assert skill.kills == {"zombie": 2, "gravewarden": 1}
    assert skill.stats.monsters_slain == 3 and skill.stats.bosses_slain == 1


async def test_a_loss_records_no_kills(db):
    user = await User.get(1)
    weak = foe("e1", max_hp=10)
    weak.enemy_id = "zombie"
    tough = foe("e2", max_hp=10**6, attack=900, speed=50)
    battle = combat.Battle(REG.combat, [hero(attack=500, max_hp=5, speed=300), weak, tough], random.Random(0))
    battle.start()
    battle.play("slash", "e1")
    while not battle.outcome:
        battle.play("slash", "e2")
    await combat.settle(user, battle, REG, random.Random(1))
    assert (await user.skill("combat")).kills == {}


# ---- the screens -------------------------------------------------------------------------------------------------------------------
async def test_home_shows_the_level_with_an_avatar_and_the_tier_color(db):
    user = await User.get(1)
    nav, _ = await hub("home")
    assert "Coconut Level 0" in all_text(nav)
    thumbs = [c for c in nav.walk_children() if isinstance(c, ui.Thumbnail)]
    assert len(thumbs) == 1
    container = next(c for c in nav.children if isinstance(c, ui.Container))
    assert container.accent_colour.value == int(RULES.tiers[0].color, 16)
    for skill in ("mining", "farming", "foraging", "fishing"):
        await user.add_xp(skill, User.level_to_xp(60) + 1)  # plenty of points for a higher tier
    nav, _ = await hub("home")
    p = await progress.progress_of(user)
    assert p.tier != RULES.tiers[0] and f"Coconut Level {p.level}" in all_text(nav)
    container = next(c for c in nav.children if isinstance(c, ui.Container))
    assert container.accent_colour.value == int(p.tier.color, 16)


async def test_home_has_a_progress_button_that_opens_the_progress_page(db):
    nav, inter = await hub("home")
    await click(nav, inter, "Progress")
    assert nav.screen.id == "progress" and "Closest to paying out" in all_text(nav) or nav.screen.id == "progress"
    assert "points" in all_text(nav)


async def test_the_progress_page_overview_and_a_category_view(db):
    user = await User.get(1)
    await user.update_skill("fishing", lambda s: setattr(s.stats, "fish_caught", 95))
    nav, inter = await hub("progress")
    text = all_text(nav)
    assert "Skills" in text and "Bestiary" in text and "Fish caught: 95/100" in text
    menu = select_named(nav, "Look closer")
    menu._values = ["skills"]
    await menu.callback(inter)
    assert "Mining level" in all_text(nav) and "Level 1" in all_text(nav)


async def test_the_bestiary_hides_what_you_have_not_met_and_shows_what_you_have(db):
    user = await User.get(1)
    nav, _ = await hub("bestiary")
    assert all_text(nav).count("❓ Unknown") == len(REG.enemies) and "Zombie" not in all_text(nav)
    await user.update_skill("combat", lambda s: s.kills.update({"zombie": 30}))
    nav, _ = await hub("bestiary")
    text = all_text(nav)
    assert "Zombie" in text and "Slain **30**" in text and "Moves: Strike" in text and text.count("❓ Unknown") == len(REG.enemies) - 1
    assert "next milestone 100" in text


async def test_the_fight_lobby_links_to_the_bestiary(db):
    nav, inter = await hub("fight")
    await click(nav, inter, "Bestiary")
    assert nav.screen.id == "bestiary"
    assert buttons(nav)  # (Home/Back are there to leave)
