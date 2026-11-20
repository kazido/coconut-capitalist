"""Tiered dungeons: a party spends one key, walks a hidden grid, fights what it steps on, then fights the boss together.

Runs live in memory like trade windows. shortcut: a bot restart loses every run (and its key); save runs when hosting is built.
Rules only (no discord). The screen redraws members when `Run.version` changes; every change below bumps it.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import DungeonTier
from cococap.services import combat, loot
from cococap.user import User

MAX_PARTY = 4
MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


class DungeonError(GameRuleError):
    pass


@dataclass
class Member:
    user_id: int
    name: str
    unit_id: str  # this member's unit id in every battle of the run ("p1".."p4")
    pos: tuple[int, int] = (0, 0)
    hp: int = 0  # carried between fights; 0 = full (set at the first fight)
    boosts: dict[str, int] = field(default_factory=dict)  # stat -> percent, from buff tiles, for the rest of the run
    battle: combat.Battle | None = None  # a solo fight in progress: the member is busy (frozen on the others' maps)
    out: bool = False  # lost a fight or left: their run is over (they keep what they found)
    items: dict[str, int] = field(default_factory=dict)  # what they found this run (already paid out)
    bits: int = 0
    xp: int = 0

    @property
    def busy(self) -> bool:
        return self.battle is not None


@dataclass
class Run:
    tier: DungeonTier
    grid: list[list[str]]  # [y][x] tile kind: reward, buff, enemy, empty, boss
    members: list[Member]
    rng: random.Random
    revealed: set[tuple[int, int]] = field(default_factory=set)
    boss_battle: combat.Battle | None = None
    outcome: str | None = None  # None while running, then "win" (boss slain) or "loss" (boss won / everyone out)
    version: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def size(self) -> int:
        return len(self.grid)

    def member(self, user_id: int) -> Member:
        for m in self.members:
            if m.user_id == user_id:
                return m
        raise DungeonError("You are not in this dungeon.")

    def active(self) -> list[Member]:
        return [m for m in self.members if not m.out]

    def tile(self, pos: tuple[int, int]) -> str:
        return self.grid[pos[1]][pos[0]]

    def _reveal(self, pos: tuple[int, int]) -> None:
        x, y = pos
        for dx, dy in ((0, 0), *MOVES.values()):
            if 0 <= x + dx < self.size and 0 <= y + dy < self.size:
                self.revealed.add((x + dx, y + dy))


_runs: dict[int, Run] = {}  # every member (in or out, until the run ends) -> their run


def run_of(user_id: int) -> Run | None:
    return _runs.get(user_id)


def clear() -> None:
    _runs.clear()


def _generate(tier: DungeonTier, rng: random.Random) -> list[list[str]]:
    """Start (top-left) is empty, the boss waits bottom-right, every other tile is drawn from the tier's weights."""
    kinds, weights = zip(*tier.tiles.items(), strict=True)
    grid = [[rng.choices(kinds, weights)[0] for _ in range(tier.size)] for _ in range(tier.size)]
    grid[0][0] = "empty"
    grid[-1][-1] = "boss"
    return grid


async def _level(user: User) -> int:
    return User.xp_to_level((await user.skill("combat")).xp)


async def enter(users: list[User], tier: int, registry: Registry | None = None, rng: random.Random | None = None) -> Run:
    """Open a run for a party (the first user is the leader and pays the key). Everyone must be free and have the level."""
    reg = registry or get_registry()
    t = reg.combat.dungeons.get(tier)
    if t is None:
        raise DungeonError("That dungeon tier doesn't exist.")
    if not 1 <= len(users) <= MAX_PARTY or len({u.id for u in users}) != len(users):
        raise DungeonError(f"A dungeon takes 1 to {MAX_PARTY} different players.")
    for u in users:
        if u.id in _runs:
            raise DungeonError(f"{u.name} is already in a dungeon.")
        if await _level(u) < t.min_level:
            raise DungeonError(f"{u.name} needs combat level {t.min_level} for a tier {tier} dungeon.")
    try:
        await users[0].remove_item(t.key, 1)
    except ValueError:
        raise DungeonError(f"You need a {reg.item(t.key).name} to go in.") from None
    rng = rng or random.Random()
    run = Run(t, _generate(t, rng), [Member(u.id, u.name, f"p{i + 1}") for i, u in enumerate(users)], rng)
    run._reveal((0, 0))
    for u in users:
        _runs[u.id] = run
    return run


async def _unit(run: Run, member: Member, user: User, reg: Registry) -> combat.Unit:
    """The member's fighter for the next fight: fresh kit and meter, but the run's hp and boosts."""
    unit = await combat.build_player(user, reg, member.unit_id)
    for stat, percent in member.boosts.items():
        setattr(unit, stat, round(getattr(unit, stat) * (100 + percent) / 100))
    unit.hp = min(member.hp, unit.max_hp) if member.hp else unit.max_hp
    return unit


def _roll_foes(run: Run) -> list[str]:
    t = run.tier
    return [run.rng.choice(t.enemies) for _ in range(run.rng.randint(1, t.max_foes))]


def _end_if_empty(run: Run) -> None:
    if not run.active() and run.outcome is None:
        run.outcome = "loss"
    if run.outcome:
        for m in run.members:
            _runs.pop(m.user_id, None)


async def move(run: Run, user: User, direction: str, registry: Registry | None = None) -> str:
    """Step one tile and resolve it. Returns what happened: "moved", "reward", "buff", "fight" (member.battle is set) or "boss"
    (run.boss_battle is set for everyone)."""
    reg = registry or get_registry()
    async with run.lock:
        m = run.member(user.id)
        if run.outcome or m.out:
            raise DungeonError("Your run is over.")
        if m.busy or run.boss_battle:
            raise DungeonError("Finish the fight first.")
        if direction not in MOVES:
            raise DungeonError("You can't go that way.")
        dx, dy = MOVES[direction]
        pos = (m.pos[0] + dx, m.pos[1] + dy)
        if not (0 <= pos[0] < run.size and 0 <= pos[1] < run.size):
            raise DungeonError("A wall blocks the way.")
        kind = run.tile(pos)
        if kind == "boss":
            waiting = [o.name for o in run.active() if o.busy]
            if waiting:
                raise DungeonError(f"The boss waits until everyone is free (still fighting: {', '.join(waiting)}).")
        m.pos = pos
        run._reveal(pos)
        run.version += 1
        if kind == "boss":
            await _start_boss(run, reg)
            return "boss"
        if kind == "empty":
            return "moved"
        run.grid[pos[1]][pos[0]] = "empty"  # the first member to step here takes it
        if kind == "reward":
            await _reward(run, m, user, reg)
        elif kind == "buff":
            await _buff(run, m, user, reg)
        else:
            m.battle = combat.battle_with(await _unit(run, m, user, reg), _roll_foes(run), reg, run.rng)
            return "fight"
        return kind


async def _reward(run: Run, m: Member, user: User, reg: Registry) -> None:
    for _ in range(run.tier.loot_rolls):
        drop = loot.roll_drop_table(reg.drop_tables[run.tier.loot], run.rng)
        if drop.item_id:
            await user.add_item(drop.item_id, drop.quantity)
            m.items[drop.item_id] = m.items.get(drop.item_id, 0) + drop.quantity
        if drop.bits:
            await user.credit("purse", drop.bits)
            m.bits += drop.bits


async def _buff(run: Run, m: Member, user: User, reg: Registry) -> None:
    buff = run.rng.choice(reg.combat.dungeon_buffs)
    if buff.stat == "hp":
        if m.hp:  # 0 already means full
            full = (await combat.build_player(user, reg, m.unit_id)).max_hp  # boosts never touch max hp
            m.hp = min(full, m.hp + full * buff.percent // 100)
    else:
        m.boosts[buff.stat] = m.boosts.get(buff.stat, 0) + buff.percent


async def _start_boss(run: Run, reg: Registry) -> None:
    units = [await _unit(run, m, await User.get(m.user_id), reg) for m in run.active()]
    boss = combat.enemy_unit(reg.enemies[run.tier.boss], "e1")
    run.boss_battle = combat.Battle(reg.combat, [*units, boss], run.rng)
    run.boss_battle.start()


async def finish_fight(run: Run, user: User, registry: Registry | None = None) -> combat.Settlement:
    """After a member's solo fight ends: pay it, carry hp over, free them (or end their run on a loss)."""
    reg = registry or get_registry()
    async with run.lock:
        m = run.member(user.id)
        battle = m.battle
        if battle is None or battle.outcome is None:
            raise DungeonError("That fight isn't over.")
        result = await combat.settle(user, battle, reg, run.rng)
        _tally(m, result)
        m.battle = None
        m.hp = battle.unit(m.unit_id).hp
        m.out = battle.outcome != "win"
        run.version += 1
        _end_if_empty(run)
        return result


async def finish_boss(run: Run, registry: Registry | None = None) -> dict[int, combat.Settlement]:
    """After the boss fight ends: every member who fought is paid (a loss pays nothing) and the run ends for everyone."""
    reg = registry or get_registry()
    async with run.lock:
        battle = run.boss_battle
        if battle is None or battle.outcome is None:
            raise DungeonError("The boss fight isn't over.")
        results = {}
        for m in run.active():
            results[m.user_id] = await combat.settle(await User.get(m.user_id), battle, reg, run.rng)
            _tally(m, results[m.user_id])
        run.outcome = battle.outcome
        run.version += 1
        _end_if_empty(run)
        return results


def _tally(m: Member, result: combat.Settlement) -> None:
    m.xp += result.xp
    m.bits += result.bits
    for item_id, qty in result.items.items():
        m.items[item_id] = m.items.get(item_id, 0) + qty


async def leave(run: Run, user: User) -> None:
    """Walk out: the member keeps what they found. Not allowed mid-fight."""
    async with run.lock:
        m = run.member(user.id)
        if m.busy or (run.boss_battle and not run.outcome and not m.out):
            raise DungeonError("Finish the fight first.")
        m.out = True
        _runs.pop(user.id, None)
        run.version += 1
        _end_if_empty(run)
