"""Tiered dungeons (services/dungeon.py): entry keys, the hidden grid, party fights and the boss."""

import random

import pytest

from cococap.registry import get_registry
from cococap.services import dungeon
from cococap.services.dungeon import DungeonError
from cococap.user import User

REG = get_registry()
TIER = 1
T = REG.combat.dungeons[TIER]


def _win(battle, cap=300):
    """Drop every foe to 1 hp, then let the players swing until the fight ends."""
    for u in battle.living("enemy"):
        u.hp = 1
    for _ in range(cap):
        if battle.outcome:
            return
        actor = battle.active
        battle.play(actor.skills[0], battle.living("enemy")[0].id, actor.id)
    raise AssertionError("fight did not end")


async def _party(*ids, key=True):
    users = [await User.get(i) for i in ids]
    if key:
        await users[0].add_item(T.key, 1)
    return users


def test_registry_has_eight_tiers_with_keys_and_known_foes():
    assert sorted(REG.combat.dungeons) == list(range(1, 9))
    for tier, t in REG.combat.dungeons.items():
        assert t.tier == tier
        assert REG.item(t.key).name
        assert t.boss in REG.enemies
        assert all(e in REG.enemies for e in t.enemies)


async def test_enter_spends_one_key_from_the_leader_only(db):
    dungeon.clear()
    leader, mate = await _party(1, 2)
    await mate.add_item(T.key, 1)
    run = await dungeon.enter([leader, mate], TIER, rng=random.Random(1))
    assert await leader.item_quantity(T.key) == 0
    assert await mate.item_quantity(T.key) == 1
    assert len(run.members) == 2
    assert run.size == T.size and len(run.grid) == T.size and all(len(r) == T.size for r in run.grid)
    assert run.tile((0, 0)) == "empty" and run.tile((T.size - 1, T.size - 1)) == "boss"
    assert (0, 0) in run.revealed


async def test_enter_refuses_without_key_or_when_busy_or_duplicated(db):
    dungeon.clear()
    (solo,) = await _party(1, key=False)
    with pytest.raises(DungeonError):
        await dungeon.enter([solo], TIER, rng=random.Random(1))

    (keyed,) = await _party(2)
    await dungeon.enter([keyed], TIER, rng=random.Random(1))
    await keyed.add_item(T.key, 1)
    with pytest.raises(DungeonError):
        await dungeon.enter([keyed], TIER, rng=random.Random(1))  # already in a run
    with pytest.raises(DungeonError):
        await dungeon.enter([keyed, keyed], TIER, rng=random.Random(1))  # same player twice


async def test_move_walls_empty_reward_and_buff_tiles(db):
    dungeon.clear()
    (user,) = await _party(1)
    run = await dungeon.enter([user], TIER, rng=random.Random(2))
    with pytest.raises(DungeonError):
        await dungeon.move(run, user, "up")  # wall above the top-left corner
    run.grid[0][1] = "empty"
    v = run.version
    assert await dungeon.move(run, user, "right") == "moved"
    assert run.version > v

    m = run.member(user.id)
    run.grid[0][2] = "reward"
    before_bits = user.balance("purse")
    assert await dungeon.move(run, user, "right") == "reward"
    assert run.tile((2, 0)) == "empty"
    for item_id, qty in m.items.items():
        assert await user.item_quantity(item_id) >= qty
    assert m.bits == user.balance("purse") - before_bits

    run.grid[0][3] = "buff"
    assert await dungeon.move(run, user, "right") == "buff"
    assert run.tile((3, 0)) == "empty"
    buff_stats = {b.stat for b in REG.combat.dungeon_buffs if b.stat != "hp"}
    assert set(m.boosts) <= buff_stats


async def test_two_players_move_separately_and_busy_blocks(db):
    dungeon.clear()
    p1, p2 = await _party(1, 2)
    run = await dungeon.enter([p1, p2], TIER, rng=random.Random(3))
    run.grid[0][1] = "enemy"  # right of the start
    run.grid[1][0] = "empty"  # below the start
    run.grid[1][1] = "boss"

    assert await dungeon.move(run, p1, "right") == "fight"
    m1, m2 = run.member(p1.id), run.member(p2.id)
    assert m1.busy and not m2.busy
    with pytest.raises(DungeonError):
        await dungeon.move(run, p1, "down")  # busy: frozen until the fight is over

    assert await dungeon.move(run, p2, "down") == "moved"
    with pytest.raises(DungeonError):
        await dungeon.move(run, p2, "right")  # the boss waits for player 1


async def test_win_carries_hp_then_boss_fight_settles_both(db):
    dungeon.clear()
    p1, p2 = await _party(1, 2)
    run = await dungeon.enter([p1, p2], TIER, rng=random.Random(4))
    run.grid[0][1] = "enemy"
    run.grid[1][1] = "boss"
    assert await dungeon.move(run, p1, "right") == "fight"
    m1 = run.member(p1.id)
    solo = m1.battle
    _win(solo)
    await dungeon.finish_fight(run, p1)
    assert not m1.busy
    assert m1.hp == solo.unit("p1").hp

    assert await dungeon.move(run, p1, "down") == "boss"
    assert run.boss_battle is not None
    assert {u.id for u in run.boss_battle.units if u.side == "player"} == {"p1", "p2"}
    assert any(u.boss for u in run.boss_battle.units if u.side == "enemy")

    xp_before = {u.id: (await u.skill("combat")).xp for u in (p1, p2)}
    _win(run.boss_battle)
    await dungeon.finish_boss(run)
    assert run.outcome == "win"
    for u in (p1, p2):
        assert (await u.skill("combat")).xp > xp_before[u.id]
        assert dungeon.run_of(u.id) is None


async def test_solo_loss_marks_out_and_all_out_is_a_loss(db):
    dungeon.clear()
    p1, p2 = await _party(1, 2)
    run = await dungeon.enter([p1, p2], TIER, rng=random.Random(5))
    run.grid[0][1] = "enemy"
    run.grid[1][0] = "empty"
    run.grid[1][1] = "enemy"

    await dungeon.move(run, p1, "right")
    m1 = run.member(p1.id)
    m1.battle.outcome = "loss"
    await dungeon.finish_fight(run, p1)
    assert m1.out and not m1.busy
    assert run.outcome is None  # the other member plays on

    await dungeon.move(run, p2, "down")
    await dungeon.move(run, p2, "right")
    m2 = run.member(p2.id)
    m2.battle.outcome = "loss"
    await dungeon.finish_fight(run, p2)
    assert run.outcome == "loss"
    assert dungeon.run_of(p1.id) is None and dungeon.run_of(p2.id) is None


async def test_boss_loss_ends_the_run_for_everyone(db):
    dungeon.clear()
    p1, p2 = await _party(1, 2)
    run = await dungeon.enter([p1, p2], TIER, rng=random.Random(6))
    run.grid[0][1] = "boss"
    assert await dungeon.move(run, p1, "right") == "boss"
    run.boss_battle.outcome = "loss"
    await dungeon.finish_boss(run)
    assert run.outcome == "loss"
    assert dungeon.run_of(p1.id) is None and dungeon.run_of(p2.id) is None


async def test_leave_refused_mid_fight_otherwise_frees_the_player(db):
    dungeon.clear()
    p1, p2 = await _party(1, 2)
    run = await dungeon.enter([p1, p2], TIER, rng=random.Random(7))
    run.grid[0][1] = "enemy"
    await dungeon.move(run, p1, "right")
    with pytest.raises(DungeonError):
        await dungeon.leave(run, p1)

    await dungeon.leave(run, p2)
    assert run.member(p2.id).out
    assert dungeon.run_of(p2.id) is None
    assert dungeon.run_of(p1.id) is run
