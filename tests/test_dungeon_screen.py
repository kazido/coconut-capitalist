"""The Dungeons tab, the map screen and the fight screen in dungeon mode."""

import random

from cococap.registry import get_registry
from cococap.services import dungeon
from cococap.services.party import Party
from cococap.user import User
from tests.test_hub import all_text, buttons, click, find_button, hub

T = get_registry().combat.dungeons[1]


async def _enter(db_user_id=1):
    """Open the Dungeons tab with a key and click Enter."""
    dungeon.clear()
    nav, inter = await hub("combat", user_id=db_user_id, tab="dungeons")
    await nav.user.add_item(T.key, 1)
    await nav.refresh(inter)
    await click(nav, inter, "Enter")
    return nav, inter


async def test_dungeons_tab_lists_every_tier(db):
    dungeon.clear()
    nav, _ = await hub("combat", tab="dungeons")
    text = all_text(nav)
    assert all(f"T{n}" in text for n in range(1, 9))


async def test_enter_opens_the_map(db):
    nav, _ = await _enter()
    assert nav.screen.id == "dungeon" and nav.screen.locked
    text = all_text(nav)
    assert "🧑" in text and "⬛" in text
    assert dungeon.run_of(nav.user.id) is not None


async def test_enter_without_a_key_is_blocked_and_member_cannot_lead(db):
    dungeon.clear()
    nav, inter = await hub("combat", tab="dungeons")
    assert find_button(nav, "Enter").disabled
    party = await Party.create(2)
    await party.add_member(1)
    await nav.user.add_item(T.key, 1)
    await nav.refresh(inter)
    await click(nav, inter, "Enter")
    assert nav.screen.id == "combat" and "leader" in all_text(nav)


async def test_an_arrow_moves_and_a_reward_tile_pays_a_note(db):
    nav, inter = await _enter()
    run = dungeon.run_of(nav.user.id)
    run.grid[0][1] = "empty"
    await click(nav, inter, emoji="➡️")
    assert run.member(nav.user.id).pos == (1, 0)
    run.grid[1][1] = "buff"
    await click(nav, inter, emoji="⬇️")
    assert nav.screen.id == "dungeon" and "stronger" in all_text(nav)


async def test_stepping_on_an_enemy_opens_the_fight_as_my_unit(db):
    nav, inter = await _enter()
    run = dungeon.run_of(nav.user.id)
    run.grid[0][1] = "enemy"
    await click(nav, inter, emoji="➡️")
    screen = nav.screen
    assert screen.id == "fight" and screen.run is run and screen.me_id == "p1"
    assert screen.battle is run.member(nav.user.id).battle
    assert "Flee" not in [b.label for b in buttons(nav)]


async def test_boss_fight_second_player_waits_for_their_turn(db):
    dungeon.clear()
    users = [await User.get(1), await User.get(2)]
    await users[0].add_item(T.key, 1)
    run = await dungeon.enter(users, 1, rng=random.Random(3))
    nav1, inter1 = await hub("dungeon", user_id=1)
    nav2, inter2 = await hub("dungeon", user_id=2)
    run.grid[0][1] = "boss"
    await click(nav1, inter1, emoji="➡️")
    assert nav1.screen.id == "fight" and run.boss_battle is not None
    await nav2.refresh(inter2)
    await click(nav2, inter2, "Boss fight")
    assert nav2.screen.me_id == "p2"
    first, second = (nav1, nav2) if run.boss_battle.active.id == "p1" else (nav2, nav1)
    await first.refresh(inter1)
    await second.refresh(inter2)
    assert "Waiting" in all_text(second) and "Waiting" not in all_text(first)
