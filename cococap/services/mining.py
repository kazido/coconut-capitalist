"""Mining rules: the mine itself, wyrmholes, the scarab, the reactor and the magnet meter.

Two kinds of code live here:

* **Pure state machines** (`MineSession`, `WyrmholeSession`, `ScarabChallenge`): they hold the state
  of one run and advance it with plain method calls. No Discord, no database. A Discord button just
  calls one method and redraws.
* **Async operations** (`start_mine`, `dig_row`, `claim_lodes`, ...): load the player's data, apply
  the rules, persist through `User`. These are the only parts that touch the database.

All randomness comes from an injected ``random.Random``.
"""

import random
import time
from collections import Counter
from dataclasses import dataclass, field

from cococap.models.skills.mining import Mining
from cococap.registry import Registry, get_registry
from cococap.registry.models import MiningRules
from cococap.services.loot import roll_table
from cococap.user import User

Cell = tuple[str, int] | None  # (item_id, quantity), or None for an empty node


class MiningError(Exception):
    """A rule was broken; the message is safe to show the player."""


# ---- small pure helpers -----------------------------------------------------------------------
def columns_dug(reactor_level: int, rules: MiningRules) -> int:
    """How many columns one press of the pickaxe digs: 1, +1 every N reactor levels, max all."""
    return min(rules.columns, 1 + (reactor_level - 1) // rules.reactor.prestige_per_extra_column)


def gems_placed(mining: Mining) -> int:
    reactor = mining.reactor
    return sum(1 for core in (reactor.core_1, reactor.core_2, reactor.core_3, reactor.core_4) if core.gem_id)


def prestige_unlocked(mining: Mining, rules: MiningRules) -> bool:
    """All four slots hold their four different gems."""
    reactor = mining.reactor
    placed = {c.gem_id for c in (reactor.core_1, reactor.core_2, reactor.core_3, reactor.core_4)}
    return placed == set(rules.reactor.core_gems)


def wyrmhole_odds(placed_gems: int, rules: MiningRules) -> int:
    w = rules.wyrmhole
    return max(w.min_odds, w.odds - w.gem_bonus * placed_gems)


def pending_lodes(mining: Mining, rules: MiningRules, now: float) -> int:
    """Auto-mined lodes waiting in the reactor: `level` lodes per interval, capped."""
    last = mining.reactor.last_auto_mine
    if last <= 0:
        return 0
    intervals = int((now - last) // rules.reactor.automine_seconds)
    cap = rules.reactor.automine_cap_hours * 3600 // rules.reactor.automine_seconds
    return min(intervals, cap) * mining.reactor.level


# ---- the mine ---------------------------------------------------------------------------------
@dataclass
class RowResult:
    row: int
    found: Counter[str]
    wyrmhole: bool  # a cursor hit a wyrmhole: the mine ends and a wyrmhole mine begins
    finished: bool


@dataclass
class MineSession:
    """One trip into the mine: a rows×columns grid of pre-rolled nodes, mined a row at a time."""

    nodes: list[list[Cell]]
    wyrmholes: set[tuple[int, int]]
    cursors: list[int]  # the columns that will be dug (their number grows with the reactor)
    magnet_columns: frozenset[int] = frozenset()  # columns the magnet says are best (UI hint)
    row: int = 0
    revealed: dict[tuple[int, int], Cell] = field(default_factory=dict)
    loot: Counter = field(default_factory=Counter)
    lodes: int = 0
    entered_wyrmhole: bool = False

    @property
    def finished(self) -> bool:
        return self.entered_wyrmhole or self.row >= len(self.nodes)

    @property
    def columns(self) -> int:
        return len(self.nodes[0])

    def move(self, step: int) -> None:
        """Slide every cursor left (-1) or right (+1), wrapping around the edges."""
        self.cursors = [(c + step) % self.columns for c in self.cursors]

    def mine_row(self) -> RowResult:
        """Dig the current row at every cursor and move down one row."""
        if self.finished:
            raise MiningError("This mine is finished.")
        found: Counter[str] = Counter()
        row = self.row
        if any((row, col) in self.wyrmholes for col in self.cursors):
            # Hitting a wyrmhole ends this mine at once; nothing else in the row is collected.
            self.entered_wyrmhole = True
            return RowResult(row, found, wyrmhole=True, finished=True)
        for col in sorted(set(self.cursors)):
            cell = self.nodes[row][col]
            self.revealed[(row, col)] = cell
            self.lodes += 1
            if cell:
                found[cell[0]] += cell[1]
        self.loot.update(found)
        self.row += 1
        return RowResult(row, found, wyrmhole=False, finished=self.finished)

    def columns_dug_total(self) -> int:
        return len(set(self.cursors))


def best_columns(nodes: list[list[Cell]], registry: Registry) -> frozenset[int]:
    """The column(s) whose pre-rolled loot is worth the most (what a full magnet reveals)."""
    columns = len(nodes[0])
    worth = [0] * columns
    for row in nodes:
        for col, cell in enumerate(row):
            if cell:
                worth[col] += registry.item(cell[0]).sell_price * cell[1]
    top = max(worth)
    return frozenset(c for c, w in enumerate(worth) if w == top and top > 0)


def generate_mine(
    rules: MiningRules,
    registry: Registry,
    rng: random.Random,
    *,
    reactor_level: int = 1,
    placed_gems: int = 0,
    magnet: bool = False,
) -> MineSession:
    nodes = [
        [roll_table(rules.depth_tables[row], registry, rng) for _ in range(rules.columns)]
        for row in range(rules.rows)
    ]
    odds = wyrmhole_odds(placed_gems, rules)
    wyrmholes = {
        (row, col)
        for row in range(rules.wyrmhole.min_row, rules.rows)
        for col in range(rules.columns)
        if rng.randint(1, odds) == 1
    }
    dug = columns_dug(reactor_level, rules)
    middle_out = sorted(range(rules.columns), key=lambda c: abs(c - rules.columns // 2))
    return MineSession(
        nodes=nodes,
        wyrmholes=wyrmholes,
        cursors=middle_out[:dug],
        magnet_columns=best_columns(nodes, registry) if magnet else frozenset(),
    )


# ---- the wyrmhole -----------------------------------------------------------------------------
@dataclass
class WyrmholeSession:
    """A single row of nodes; you get to dig exactly one. Exactly one hides an implosion gem."""

    nodes: list[tuple[str, int]]
    cursor: int
    revealed: tuple[str, int] | None = None

    def move(self, step: int) -> None:
        self.cursor = (self.cursor + step) % len(self.nodes)

    def dig(self) -> tuple[str, int]:
        if self.revealed is not None:
            raise MiningError("You already dug in this wyrmhole.")
        self.revealed = self.nodes[self.cursor]
        return self.revealed

    @property
    def finished(self) -> bool:
        return self.revealed is not None


def generate_wyrmhole(rules: MiningRules, rng: random.Random) -> WyrmholeSession:
    pool = rules.wyrmhole.pool
    nodes = [(item, pool[item]) for item in (rng.choice(list(pool)) for _ in range(rules.columns))]
    nodes[rng.randrange(rules.columns)] = (rules.wyrmhole.implosion_item, 1)
    return WyrmholeSession(nodes=nodes, cursor=rules.columns // 2)


# ---- the scarab -------------------------------------------------------------------------------
@dataclass(frozen=True)
class ScarabChallenge:
    """Unscramble the word within `seconds` to be taken to the bonus level."""

    word: str
    scrambled: str
    seconds: int

    def check(self, answer: str) -> bool:
        return answer.strip().lower() == self.word.lower()


def scarab_appears(rules: MiningRules, rng: random.Random) -> bool:
    return rng.randint(1, rules.scarab.chance) == 1


def make_scarab(words: list[str], rules: MiningRules, rng: random.Random) -> ScarabChallenge:
    word = rng.choice(words)
    letters = list(word)
    for _ in range(20):  # re-shuffle until it actually differs from the word
        rng.shuffle(letters)
        if "".join(letters) != word or len(set(word)) == 1:
            break
    return ScarabChallenge(word, "".join(letters), rules.scarab.seconds)


def scarab_reward(registry: Registry, rules: MiningRules, rng: random.Random) -> Counter[str]:
    """Level-6 loot for solving the scroll."""
    item = registry.item(rules.scarab.reward_item)
    quantity = rng.randint(item.drop.min, item.drop.max) if item.drop else 1
    return Counter({item.id: quantity})


# ---- operations on a player (these persist) ----------------------------------------------------
async def _mining_state(user: User) -> tuple[Mining, int]:
    mining = await user.skill("mining")
    return mining, User.xp_to_level(mining.xp)


async def start_mine(user: User, rng: random.Random, registry: Registry | None = None) -> MineSession:
    """Begin a mine. A full magnet is spent here: this mine shows its best columns."""
    reg = registry or get_registry()
    rules = reg.mining
    mining, _ = await _mining_state(user)
    magnet = mining.magnet_meter >= rules.magnet.capacity
    if magnet:
        await user.update_skill("mining", lambda m: setattr(m, "magnet_meter", 0))
    return generate_mine(
        rules,
        reg,
        rng,
        reactor_level=mining.reactor.level,
        placed_gems=gems_placed(mining),
        magnet=magnet,
    )


async def dig_row(user: User, session: MineSession) -> RowResult:
    """Dig the session's current row and bank what was found immediately."""
    result = session.mine_row()
    for item_id, quantity in result.found.items():
        await user.add_item(item_id, quantity)
    return result


async def finish_mine(user: User, session: MineSession, registry: Registry | None = None) -> int:
    """Record a completed (or abandoned) mine. Returns the xp granted."""
    rules = (registry or get_registry()).mining
    completed = session.row >= len(session.nodes)
    xp = rules.xp_per_column * session.columns_dug_total() if completed else 0

    def record(m: Mining) -> None:
        m.xp += xp
        m.stats.lodes_mined += session.lodes

    await user.update_skill("mining", record)
    return xp


async def enter_wyrmhole(user: User, rng: random.Random, registry: Registry | None = None) -> WyrmholeSession:
    return generate_wyrmhole((registry or get_registry()).mining, rng)


async def finish_wyrmhole(user: User, session: WyrmholeSession) -> tuple[str, int]:
    item_id, quantity = session.dig()
    await user.add_item(item_id, quantity)
    await user.update_skill("mining", lambda m: setattr(m.stats, "lodes_mined", m.stats.lodes_mined + 1))
    return item_id, quantity


async def claim_scarab_reward(user: User, rng: random.Random, registry: Registry | None = None) -> Counter[str]:
    reg = registry or get_registry()
    reward = scarab_reward(reg, reg.mining, rng)
    for item_id, quantity in reward.items():
        await user.add_item(item_id, quantity)
    return reward


# ---- the reactor ------------------------------------------------------------------------------
async def reactor_status(user: User, now: float | None = None, registry: Registry | None = None):
    """Everything the reactor screen shows, as plain data."""
    rules = (registry or get_registry()).mining
    mining, level = await _mining_state(user)
    if mining.reactor.last_auto_mine <= 0:  # first visit: start the automine clock
        mining = await user.update_skill(
            "mining", lambda m: setattr(m.reactor, "last_auto_mine", now or time.time())
        )
    return {
        "mining": mining,
        "level": level,
        "pending_lodes": pending_lodes(mining, rules, now or time.time()),
        "prestige_unlocked": prestige_unlocked(mining, rules),
        "columns_dug": columns_dug(mining.reactor.level, rules),
        "gem_slots_open": level >= rules.reactor.gem_slot_level,
    }


async def place_gem(user: User, gem_id: str, registry: Registry | None = None) -> int:
    """Move a gem from the inventory into its own reactor slot. Returns the slot (1-4)."""
    rules = (registry or get_registry()).mining
    if gem_id not in rules.reactor.core_gems:
        raise MiningError("That isn't a reactor gem.")
    slot = rules.reactor.core_gems.index(gem_id) + 1  # each gem has its own slot
    mining, level = await _mining_state(user)
    if level < rules.reactor.gem_slot_level:
        raise MiningError(f"Gem slots unlock at mining level {rules.reactor.gem_slot_level}.")
    if getattr(mining.reactor, f"core_{slot}").gem_id:
        raise MiningError("That gem is already in the reactor.")

    try:
        await user.remove_item(gem_id, 1)
    except ValueError:
        raise MiningError("You don't have that gem.") from None

    def fill(m: Mining) -> None:
        getattr(m.reactor, f"core_{slot}").gem_id = gem_id

    try:
        await user.update_skill("mining", fill)
    except Exception:
        await user.add_item(gem_id, 1)  # never swallow the gem
        raise
    return slot


async def prestige(user: User, registry: Registry | None = None) -> int:
    """Spend an implosion gem to raise the reactor one level. Returns the new level."""
    rules = (registry or get_registry()).mining
    mining, _ = await _mining_state(user)
    if not prestige_unlocked(mining, rules):
        raise MiningError("Fill all four slots with their gems first.")
    if mining.reactor.level >= rules.reactor.max_prestige:
        raise MiningError("Your reactor is at its maximum level.")
    try:
        await user.remove_item(rules.wyrmhole.implosion_item, 1)
    except ValueError:
        raise MiningError("You need an implosion gem (only found in wyrmholes).") from None

    def level_up(m: Mining) -> None:
        m.reactor.level = min(rules.reactor.max_prestige, m.reactor.level + 1)

    updated = await user.update_skill("mining", level_up)
    return updated.reactor.level


async def claim_lodes(
    user: User, rng: random.Random, now: float | None = None, registry: Registry | None = None
) -> tuple[int, Counter[str]]:
    """Collect the auto-mined lodes. Returns (lodes, loot). Safe to call concurrently: the clock is
    reset inside one transaction, so a second claim sees nothing waiting."""
    reg = registry or get_registry()
    rules = reg.mining
    now = now or time.time()
    claimed = {"lodes": 0, "depth": 0}

    def take(m: Mining) -> None:
        if m.reactor.last_auto_mine <= 0:
            m.reactor.last_auto_mine = now
            return
        claimed["lodes"] = pending_lodes(m, rules, now)
        claimed["depth"] = min(m.reactor.level - 1, rules.rows - 1)
        if claimed["lodes"]:
            m.reactor.last_auto_mine = now
            m.stats.lodes_auto_mined += claimed["lodes"]

    await user.update_skill("mining", take)
    table = rules.depth_tables[claimed["depth"]]
    loot: Counter[str] = Counter()
    for _ in range(claimed["lodes"]):
        result = roll_table(table, reg, rng)
        if result:
            loot[result[0]] += result[1]
    for item_id, quantity in loot.items():
        await user.add_item(item_id, quantity)
    return claimed["lodes"], loot


# ---- the magnet -------------------------------------------------------------------------------
async def deposit_ore(
    user: User, item_id: str, quantity: int, registry: Registry | None = None
) -> tuple[int, int]:
    """Feed ore to the magnet. Only as much as fits is taken. Returns (meter, ore_used)."""
    rules = (registry or get_registry()).mining
    value = rules.magnet.values.get(item_id)
    if value is None:
        raise MiningError("The magnet only takes copper, iron and gold ore.")
    if quantity < 1:
        raise MiningError("Deposit at least one.")
    mining, level = await _mining_state(user)
    if level < rules.magnet.level:
        raise MiningError(f"The magnet unlocks at mining level {rules.magnet.level}.")
    remaining = rules.magnet.capacity - mining.magnet_meter
    if remaining <= 0:
        raise MiningError("The magnet is already full.")
    used = min(quantity, -(-remaining // value))  # ceil: don't take ore the meter can't use
    try:
        await user.remove_item(item_id, used)
    except ValueError:
        raise MiningError("You don't have that many.") from None

    def charge(m: Mining) -> None:
        m.magnet_meter = min(rules.magnet.capacity, m.magnet_meter + value * used)

    try:
        updated = await user.update_skill("mining", charge)
    except Exception:
        await user.add_item(item_id, used)
        raise
    return updated.magnet_meter, used
