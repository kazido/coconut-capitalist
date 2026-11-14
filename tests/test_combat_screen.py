"""The /fight screen: lobby, picking a target, playing skills, winning, losing, fleeing."""

import pytest

from cococap.registry import get_registry
from cococap.services import combat
from tests.test_hub import all_text, buttons, click, find_button, hub


async def start(nav, inter, label="Fight", index=0):
    button = [b for b in buttons(nav) if b.label == label][index]
    inter.response.edit_message.reset_mock()
    await button.callback(inter)


async def test_lobby_shows_stats_skills_and_locks_fights_above_your_level(db):
    nav, _ = await hub("fight")
    text = all_text(nav)
    assert "Slash" in text and "A lone zombie" in text and "Combat level 3" in text
    fights = [b for b in buttons(nav) if b.label == "Fight"]
    assert [b.disabled for b in fights] == [False, True, True, True]


async def test_a_locked_fight_cannot_be_started(db):
    nav, inter = await hub("fight")
    with pytest.raises(combat.CombatError, match="yet"):  # a stale button, clicked anyway (the hub shows the message)
        await nav.screen._starter("graveyard_horde")(inter)
    assert nav.screen.battle is None


async def test_starting_a_fight_shows_the_battle_and_locks_navigation(db):
    nav, inter = await hub("fight")
    await start(nav, inter)
    screen = nav.screen
    text = all_text(nav)
    assert screen.battle is not None and screen.locked
    assert "Zombie" in text and "Turn order" in text and "Slash" in [b.label for b in buttons(nav)]


async def test_with_several_enemies_a_skill_asks_for_a_target_and_can_be_cancelled(db):
    nav, inter = await hub("fight")
    nav.screen.encounter = "graveyard_pair"
    nav.screen.battle = combat.new_battle(await combat.build_player(nav.user), "graveyard_pair")
    await nav.refresh(inter)
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
    sword = await nav.user.give_instance("shiningsilver")  # five skills: the widest kit
    await nav.user.equip("combat", sword.id)
    nav.screen.battle = combat.new_battle(await combat.build_player(nav.user), "gravewarden")
    nav.screen.encounter = "gravewarden"
    await nav.refresh(inter)
    text = all_text(nav)
    assert "Gravewarden" in text and "Next: **Death Knell**" in text
    rows = [r for r in nav.walk_children() if r.__class__.__name__ == "ActionRow"]
    assert all(len(r.children) <= 5 for r in rows)
    assert {"Slash", "Brace", "Flee"} <= {b.label for b in buttons(nav)}


async def test_the_boss_fight_is_locked_until_level_20(db):
    nav, _ = await hub("fight")
    fights = [(b.disabled) for b in buttons(nav) if b.label == "Fight"]
    assert fights == [False, True, True, True] and "Combat level 20" in all_text(nav)
