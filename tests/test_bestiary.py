"""The Bestiary: every creature (monsters, fish, fishing bosses), per-creature counters that never stop, and its page."""

import random

from cococap.registry import get_registry
from cococap.services import bestiary, combat
from cococap.user import SKILL_MODELS, User
from tests.test_combat import foe, hero
from tests.test_hub import all_text, buttons, click, hub, select_named

REG = get_registry()
RULES = REG.bestiary


def empty_skills() -> dict:
    return {name: SKILL_MODELS[name]() for name in bestiary.SKILLS}


def by_name(skills) -> dict:
    return {c.name: c for c in bestiary.creatures(skills, REG)}


# ---- what it tracks ---------------------------------------------------------------------------------------------------------------
def test_the_bestiary_counts_every_monster_fish_species_and_fishing_boss():
    skills = empty_skills()
    names = {c.name for c in bestiary.creatures(skills, REG)}
    fish = [i for i in REG.items.values() if i.skill == "fishing" and i.category == "fish" and i.drop]
    assert {i.name for i in fish} <= names and {b.name for b in REG.fishing.boss.bosses} <= names and {e.name for e in REG.enemies.values()} <= names
    skills["fishing"].stats.caught = {fish[0].id: 40}
    skills["fishing"].stats.bosses = {REG.fishing.boss.bosses[0].name: 1}
    skills["combat"].kills = {"zombie": 30, "gravewarden": 1}
    creatures = by_name(skills)
    assert creatures[fish[0].name].count == 40 and creatures[fish[0].name].next_goal == RULES.fish_steps[2]
    assert creatures[REG.fishing.boss.bosses[0].name].count == 1 and creatures[REG.fishing.boss.bosses[0].name].boss
    assert creatures["Zombie"].next_goal == RULES.steps[2] and creatures["The Gravewarden"].boss and creatures[fish[1].name].count == 0


def test_a_fish_you_hold_a_record_for_counts_as_met_even_before_the_counter_existed():
    fish = next(i for i in REG.items.values() if i.skill == "fishing" and i.category == "fish" and i.drop)
    skills = empty_skills()
    skills["fishing"].records = {fish.id: 31.0}
    found = by_name(skills)[fish.name]
    assert found.count == 1 and "31" in found.detail


def test_the_goals_have_no_end_in_sight_and_a_creature_past_the_last_one_has_none_left():
    assert max(RULES.steps) >= 10_000 and max(RULES.boss_steps) >= 500
    skills = empty_skills()
    skills["combat"].kills = {"zombie": max(RULES.steps) + 49_000}
    zombie = by_name(skills)["Zombie"]
    assert zombie.count == max(RULES.steps) + 49_000 and zombie.next_goal is None  # still counted: only the goals stop


async def test_landing_a_fish_counts_it_in_the_bestiary_with_its_extras(db):
    from cococap.services import fishing as f

    user = await User.get(1)
    cast = f.Cast(REG.item("fish_salmon"), 10.0, 20.0, [f.LEFT], 0, hooked=True, extra_fish=2)
    cast.press(f.LEFT, 11.0)
    await f.land(user, cast, REG)
    assert (await user.skill("fishing")).stats.caught["fish_salmon"] == 3  # the fish and its two extras


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


# ---- the page -----------------------------------------------------------------------------------------------------------------------
async def test_the_bestiary_hides_what_you_have_not_met_and_shows_what_you_have(db):
    user = await User.get(1)
    nav, _ = await hub("bestiary")
    assert all_text(nav).count("❓ Unknown") == len(REG.enemies) and "Zombie" not in all_text(nav)
    await user.update_skill("combat", lambda s: s.kills.update({"zombie": 30}))
    nav, _ = await hub("bestiary")
    text = all_text(nav)
    assert "Zombie" in text and "Slain **30**" in text and "Moves: Strike" in text and text.count("❓ Unknown") == len(REG.enemies) - 1
    assert f"next goal {RULES.steps[2]}" in text
    assert "point" not in text.lower()  # (it is a record, not a reward)


async def test_the_fishing_bestiary_page_hides_unmet_fish_and_has_a_group_picker(db):
    user = await User.get(1)
    fish = next(i for i in REG.items.values() if i.skill == "fishing" and i.category == "fish" and i.drop)
    await user.update_skill("fishing", lambda s: s.stats.caught.update({fish.id: 7}))
    nav, inter = await hub("bestiary")
    menu = select_named(nav, "Show")
    menu._values = ["fishing"]
    await menu.callback(inter)
    text = all_text(nav)
    assert fish.name in text and "7 caught" in text and "❓ Unknown" in text and "Sea bosses" in text


async def test_the_kill_counter_keeps_climbing_after_the_last_goal(db):
    user = await User.get(1)
    top = max(RULES.steps)
    await user.update_skill("combat", lambda s: s.kills.update({"zombie": top + 49_000}))
    nav, _ = await hub("bestiary")
    assert f"Slain **{top + 49_000:,}**" in all_text(nav) and "every goal reached" in all_text(nav)
    await user.update_skill("combat", lambda s: s.kills.update({"zombie": s.kills["zombie"] * 100}))
    assert (await user.skill("combat")).kills["zombie"] == (top + 49_000) * 100  # the stat itself has no ceiling


async def test_the_fight_lobby_and_the_more_page_lead_to_the_bestiary(db):
    nav, inter = await hub("fight")
    await click(nav, inter, "Bestiary")
    assert nav.screen.id == "bestiary" and buttons(nav)
    nav, inter = await hub("more")
    assert "Bestiary" in all_text(nav)
