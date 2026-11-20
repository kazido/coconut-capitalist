"""The /fight screen: lobby, picking a target, playing skills, winning, losing, fleeing."""

import pytest

from cococap.registry import get_registry
from cococap.services import combat, equipment
from tests.test_hub import all_text, buttons, click, find_button, hub


async def start(nav, inter, enemies=("zombie",)):
    """Put a battle against these enemies on the fight screen (Explore draws random foes, so tests pin them)."""
    nav.screen.zone = "graveyard"
    nav.screen.battle = combat.battle_with(await combat.build_player(nav.user), list(enemies))
    await nav.refresh(inter)


async def test_explore_starts_a_battle_and_locks_navigation(db):
    nav, inter = await hub("combat")
    assert "Graveyard" in all_text(nav)
    await click(nav, inter, "Explore")
    screen = nav.screen
    assert screen.id == "fight" and screen.battle is not None and screen.locked
    assert "Turn order" in all_text(nav) and "Slash" in [b.label for b in buttons(nav)]


async def test_the_fight_page_without_a_battle_points_to_the_combat_page(db):
    nav, inter = await hub("fight")
    assert "Pick a zone" in all_text(nav)
    await click(nav, inter, "Combat")
    assert nav.screen.id == "combat"


async def test_the_class_tab_shows_the_kit_of_the_equipped_weapon(db):
    nav, inter = await hub("combat", tab="class")
    assert "Bare hands" in all_text(nav)
    item = await nav.user.give_instance("tool_sword_starter")
    await equipment.equip(nav.user, "combat", item.id)
    nav, inter = await hub("combat", tab="class")
    text = all_text(nav)
    assert "Melee" in text and "Rage" in text and "Cleave" in text and "unlocks at combat level" in text


async def test_with_several_enemies_a_skill_asks_for_a_target_and_can_be_cancelled(db):
    nav, inter = await hub("fight")
    await start(nav, inter, ("zombie", "skeleton"))
    await click(nav, inter, "Slash")
    assert nav.screen.picking == "slash" and "pick a target" in all_text(nav)
    await click(nav, inter, "Cancel")
    assert nav.screen.picking is None
    await click(nav, inter, "Slash")
    target = next(b for b in buttons(nav) if b.label and b.label.startswith("Skeleton"))
    hp_before = nav.screen.battle.unit("e2").hp
    await target.callback(inter)
    assert nav.screen.picking is None and nav.screen.battle.unit("e2").hp < hp_before


async def test_a_single_enemy_needs_no_target_pick(db):
    nav, inter = await hub("fight")
    await start(nav, inter)
    before = nav.screen.battle.unit("e1").hp
    await click(nav, inter, "Slash")
    assert nav.screen.picking is None and nav.screen.battle.unit("e1").hp < before


async def test_winning_pays_xp_and_shows_the_result_then_fight_again_restarts(db):
    nav, inter = await hub("fight")
    await start(nav, inter)
    nav.screen.battle.unit("p1").attack = 10_000
    await click(nav, inter, "Slash")
    assert nav.screen.id == "result" and nav.screen.origin.battle is None
    skill = await nav.user.skill("combat")
    assert skill.xp == get_registry().enemies["zombie"].xp and skill.stats.monsters_slain == 1
    text = all_text(nav)
    assert "Victory" in text and "combat xp" in text
    await click(nav, inter, "Fight again")
    assert nav.screen.battle is not None and nav.screen.battle.unit("e1").hp == nav.screen.battle.unit("e1").max_hp


async def test_losing_costs_nothing(db):
    nav, inter = await hub("fight")
    await start(nav, inter)
    battle = nav.screen.battle
    battle.unit("p1").hp = 1  # the zombie out-lives one slash, then hits back
    battle.unit("e1").hp = battle.unit("e1").max_hp = 10_000
    await click(nav, inter, "Slash")
    assert nav.screen.id == "result" and nav.screen.origin.battle is None and "Defeated" in all_text(nav)
    skill = await nav.user.skill("combat")
    assert skill.xp == 0 and skill.stats.monsters_slain == 0


async def test_fleeing_ends_the_fight_without_xp(db):
    nav, inter = await hub("fight")
    await start(nav, inter)
    await click(nav, inter, "Flee")
    assert nav.screen.battle is None and not nav.screen.locked
    assert (await nav.user.skill("combat")).xp == 0 and "ran away" in all_text(nav)


async def test_the_boss_shows_its_next_move_and_the_controls_fit_discord_rows(db):
    nav, inter = await hub("fight")
    nav.screen.battle = combat.new_battle(await combat.build_player(nav.user), "gravewarden")
    nav.screen.encounter = "gravewarden"
    await nav.refresh(inter)
    text = all_text(nav)
    assert "Gravewarden" in text and "Next: **Death Knell**" in text
    rows = [r for r in nav.walk_children() if r.__class__.__name__ == "ActionRow"]
    assert all(len(r.children) <= 5 for r in rows)
    assert {"Slash", "Flee"} <= {b.label for b in buttons(nav)}


async def test_the_boss_fight_is_locked_until_level_20_and_needs_a_key_and_spends_it(db):
    nav, inter = await hub("combat")
    boss = [b for b in buttons(nav) if b.label == "Fight"][-1]
    assert boss.disabled and "Combat level 20" in all_text(nav)
    user = nav.user
    await user.add_xp("combat", 73_674)  # level 20
    nav, inter = await hub("combat")
    boss = [b for b in buttons(nav) if b.label == "Fight"][-1]
    assert boss.disabled and "needs a key" in all_text(nav)
    await user.add_item("key_graveyard", 1)
    nav, inter = await hub("combat")
    assert "Graveyard Key" in all_text(nav) and "×1" in all_text(nav)
    boss = [b for b in buttons(nav) if b.label == "Fight"][-1]
    assert not boss.disabled
    await boss.callback(inter)
    assert nav.screen.battle is not None and await user.item_quantity("key_graveyard") == 0


async def test_the_victory_page_lists_what_dropped(db, monkeypatch):
    from cococap.services import loot

    monkeypatch.setattr(loot, "roll_kill", lambda *a, **k: loot.Loot(item_id="material_iron_ore", quantity=3))
    nav, inter = await hub("fight")
    await start(nav, inter)
    nav.screen.battle.unit("p1").attack = 10_000
    await click(nav, inter, "Slash")
    assert "🎁" in all_text(nav) and "×3" in all_text(nav) and "Iron Ore" in all_text(nav)
    assert await nav.user.item_quantity("material_iron_ore") == 3


async def test_a_victory_with_no_drop_says_so(db, monkeypatch):
    from cococap.services import loot

    monkeypatch.setattr(loot, "roll_kill", lambda *a, **k: None)
    nav, inter = await hub("fight")
    await start(nav, inter)
    nav.screen.battle.unit("p1").attack = 10_000
    await click(nav, inter, "Slash")
    assert "Nothing dropped" in all_text(nav)
