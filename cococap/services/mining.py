"""Mining rules: the mine itself, wyrmholes, the scarab, the reactor and the magnet meter.

Two kinds of code live here:

* **Pure state machines** (`MineSession`, `WyrmholeSession`, `ScarabChallenge`): they hold the state
  of one run and advance it with plain method calls. No Discord, no database. A Discord button just
  calls one method and redraws.
* **Async operations** (`start_mine`, `dig_row`, `claim_lodes`, ...): load the player's data, apply
  the rules, persist through `User`. These are the only parts that touch the database.

All randomness comes from an injected ``random.Random``.
"""

import logging
import random
import time
from collections import Counter
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.models.skills.mining import Mining
from cococap.registry import Registry, get_registry
from cococap.registry.loader import BOMB_ITEM
from cococap.registry.models import MiningRules, RiskLabel
from cococap.services.equipment import equipped_stats
from cococap.services.loot import roll_table
from cococap.services import pets
from cococap.services.party import xp_multiplier
from cococap.user import User

log = logging.getLogger(__name__)

Cell = tuple[str, int] | None  # (item_id, quantity), or None for an empty node


class MiningError(GameRuleError):
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


# ---- the descent ------------------------------------------------------------------------------
@dataclass
class DigResult:
    found: Counter[str]
    collapsed: bool = False
    wyrmhole: bool = False
    bombed: bool = False
    lost: Counter[str] = field(default_factory=Counter)  # what a collapse took from the haul
    vented: int = 0  # cooling vents dug (each bled pressure)
    caches: int = 0  # supply caches dug (each gave braces)
    vault: Counter[str] = field(default_factory=Counter)  # what the vault gave, if this dig reached the floor


@dataclass
class DugRow:
    depth: int
    cells: list[Cell]  # one per column
    dug: tuple[int, ...]  # which columns were dug
    kinds: list[str] = field(default_factory=list)  # the row's signs as it looked from above


# What a cell looks like from above. "ore" is a plain cell: it shows its ore (or that it is empty).
SIGNS = ("ore", "rich", "vent", "cache", "hole")


class MineRun:
    """One trip down the mine, as a pure state machine.

    The shaft has ``descent.floor`` rows. Each ``dig`` mines the cells under the cursors and descends one
    row. Cells are hidden: only **rich** lodes (a mystery that rolls the next tier's table) and **wyrmholes** show
    from above. Underneath, a cell may be ore, nothing, a **vent** (no loot, cools the tunnel) or a **cache** (+braces).
    Richer ore is harder, so digging it adds more **pressure**; pressure sets the collapse chance, which
    is always shown. ``brace`` lowers pressure, ``bomb`` clears a whole row, ``leave`` banks and ends.
    Digging the last row opens the vault.

    Nothing here touches the database: ``settle_run`` banks the result.
    """

    def __init__(
        self,
        rules: MiningRules,
        registry: Registry,
        rng: random.Random,
        *,
        cursors: list[int],
        growth_factor: float = 1.0,
        yield_factor: float = 1.0,
        braces: int = 1,
        bombs: int = 0,
        magnet: bool = False,
        wyrmhole_odds_value: int | None = None,
        rich_bonus: float = 0.0,
        vault_gem_bonus: float = 0.0,
    ):
        self.rules, self.registry, self.rng = rules, registry, rng
        self.cursors = list(cursors)
        self.growth_factor, self.yield_factor = growth_factor, yield_factor
        self.braces, self.bombs, self.magnet = braces, bombs, magnet
        self.rich_bonus, self.vault_gem_bonus = rich_bonus, vault_gem_bonus  # Mastery: more rich lodes, more vault gems
        self.bombs_used = 0
        self.xp_awarded = 0
        self.last_risk = self.last_pressure = 0.0
        self.wyrmhole_odds = wyrmhole_odds_value or rules.wyrmhole.odds
        self.depth = 0  # rows dug so far == the index of the row you're about to dig
        self.danger = 0.0  # pressure, 0-100
        self.haul: Counter[str] = Counter()
        self.lodes = 0  # cells dug
        self.outcome: str | None = None  # "left" | "collapse" | "wyrmhole" | "floor"
        self.settled = False
        self.history: list[DugRow] = []
        self._rows: dict[int, list[Cell]] = {}
        self._holes: dict[int, set[int]] = {}
        self._kinds: dict[int, list[str]] = {}

    @property
    def floor(self) -> int:
        return self.rules.descent.floor

    # ---- the rows ahead -------------------------------------------------------------------------
    def tier(self, depth: int) -> int:
        return min(depth // self.rules.descent.rows_per_tier, len(self.rules.depth_tables) - 1)

    def _quantity_factor(self, depth: int) -> float:
        return self.yield_factor * (1 + self.rules.descent.depth_bonus_per_row * depth)

    def row(self, depth: int) -> list[Cell]:
        """The cells of row `depth` (rolled the first time they're needed, then fixed)."""
        if depth not in self._rows:
            table = self.rules.depth_tables[self.tier(depth)]
            cells: list[Cell] = []
            for _ in range(self.rules.columns):
                rolled = roll_table(table, self.registry, self.rng)
                cells.append((rolled[0], max(1, round(rolled[1] * self._quantity_factor(depth)))) if rolled else None)
            self._rows[depth] = cells
            self._holes[depth] = {
                col
                for col in range(self.rules.columns)
                if depth >= self.rules.wyrmhole.min_depth and self.rng.randint(1, self.wyrmhole_odds) == 1
            }
            self._kinds[depth] = self._roll_kinds(depth)
        return self._rows[depth]

    def _rich_cell(self, depth: int) -> Cell:
        """A rich lode: the next tier's table, and more of it. Never empty."""
        d = self.rules.descent
        table = self.rules.depth_tables[min(self.tier(depth) + 1, len(self.rules.depth_tables) - 1)]
        for _ in range(12):
            rolled = roll_table(table, self.registry, self.rng)
            if rolled:
                break
        else:  # (astronomically rare) fall back to the commonest item of the tier
            item = self.registry.item(table[-1])
            rolled = (item.id, item.drop.min if item.drop else 1)
        return rolled[0], max(1, round(rolled[1] * d.rich_multiplier * self._quantity_factor(depth)))

    def _roll_kinds(self, depth: int) -> list[str]:
        d = self.rules.descent
        cells, kinds = self._rows[depth], []
        for col in range(self.rules.columns):
            kind = "ore"
            if col not in self._holes[depth]:
                if depth >= 1 and self.rng.random() < d.vent_chance:
                    kind, cells[col] = "vent", None
                elif depth >= d.cache_min_depth and self.rng.random() < d.cache_chance:
                    kind, cells[col] = "cache", None
                elif self.rng.random() < d.rich_chance + self.rich_bonus:
                    kind, cells[col] = "rich", self._rich_cell(depth)
            kinds.append(kind)
        return kinds

    def signs(self, depth: int) -> list[str]:
        """What each cell of row `depth` is from above: ore, rich, vent, cache or hole."""
        self.row(depth)
        return ["hole" if col in self._holes[depth] else self._kinds[depth][col] for col in range(self.rules.columns)]

    def wyrmholes_ahead(self) -> set[int]:
        self.row(self.depth)
        return self._holes[self.depth]

    def best_columns(self) -> frozenset[int]:
        """With a charged magnet: the column(s) of the next row worth the most."""
        if not self.magnet:
            return frozenset()
        cells, holes = self.row(self.depth), self._holes[self.depth]
        worth = [0 if (col in holes or not cell) else self.registry.item(cell[0]).sell_price * cell[1] for col, cell in enumerate(cells)]
        top = max(worth)
        return frozenset(i for i, w in enumerate(worth) if top > 0 and w == top)

    # ---- pressure and risk ----------------------------------------------------------------------
    def hardness(self, cell: Cell) -> float:
        d = self.rules.descent
        return d.empty_hardness if cell is None else d.hardness.get(cell[0], d.default_hardness)

    @property
    def risk(self) -> float:
        """The chance that the next dig collapses the mine: a smooth curve of the pressure."""
        d = self.rules.descent
        excess = max(0.0, self.danger - d.safe_pressure) / (100 - d.safe_pressure)
        return d.max_risk * excess**d.risk_exponent

    @property
    def warning(self) -> RiskLabel:
        current = self.rules.descent.warnings[0]
        for label in self.rules.descent.warnings:
            if self.risk >= label.from_risk:
                current = label
        return current

    # ---- actions ----------------------------------------------------------------------------------
    @property
    def finished(self) -> bool:
        return self.outcome is not None

    def _require_live(self) -> None:
        if self.finished:
            raise MiningError("This mine is finished.")

    def move(self, step: int) -> None:
        """Slide every cursor left (-1) or right (+1), wrapping around the edges."""
        self.cursors = [(c + step) % self.rules.columns for c in self.cursors]

    def _mine(self, columns: list[int]) -> tuple[Counter[str], int, int, float]:
        """Dig `columns` of the current row. Returns (found, vents, caches, hardness)."""
        d = self.rules.descent
        cells, kinds = self.row(self.depth), self._kinds[self.depth]
        found: Counter[str] = Counter()
        vents = caches = 0
        hardness = 0.0
        for col in columns:
            if kinds[col] == "vent":
                vents += 1
            elif kinds[col] == "cache":
                caches += 1
                self.braces += d.cache_braces
            if cells[col]:
                found[cells[col][0]] += cells[col][1]
            hardness += self.hardness(cells[col])
        self.haul.update(found)
        self.lodes += len(columns)
        self.history.append(DugRow(self.depth, list(cells), tuple(columns), self.signs(self.depth)))
        return found, vents, caches, hardness

    def _descend(self, pressure: float, vents: int) -> Counter[str]:
        """Apply the pressure change, move down a row and, at the bottom, open the vault."""
        d = self.rules.descent
        gain = pressure * self.growth_factor
        self.danger = min(100.0, max(0.0, self.danger + gain - vents * d.vent_relief))
        self.depth += 1
        if self.depth < d.floor:
            return Counter()
        self.outcome = "floor"
        vault: Counter[str] = Counter(d.vault_ore)
        if self.rng.random() < d.vault_gem_chance * (1 + self.vault_gem_bonus):
            vault[self.rng.choice(self.rules.reactor.core_gems)] += 1
        self.haul.update(vault)
        return vault

    def dig(self) -> DigResult:
        self._require_live()
        d = self.rules.descent
        self.row(self.depth)
        if any(col in self._holes[self.depth] for col in self.cursors):
            self.outcome = "wyrmhole"  # you broke into a wyrmhole: the mine ends and the haul is yours
            return DigResult(Counter(), wyrmhole=True)
        self.last_risk, self.last_pressure = self.risk, self.danger  # kept for the log when something goes wrong
        if self.rng.random() < self.risk:
            lost: Counter[str] = Counter()
            for item_id, quantity in list(self.haul.items()):
                keep = int(quantity * (1 - d.collapse_loss))
                lost[item_id] = quantity - keep
                if keep:
                    self.haul[item_id] = keep
                else:
                    del self.haul[item_id]
            self.outcome = "collapse"
            return DigResult(Counter(), collapsed=True, lost=+lost)
        found, vents, caches, hardness = self._mine(sorted(set(self.cursors)))
        vault = self._descend(d.creak + hardness, vents)
        return DigResult(found, vented=vents, caches=caches, vault=vault)

    def bomb(self) -> DigResult:
        """Blow the whole row (except wyrmholes): every cell, one flat pressure hit, no collapse check."""
        self._require_live()
        d = self.rules.descent
        if self.bombs <= 0:
            raise MiningError("You have no bombs left.")
        self.row(self.depth)
        self.bombs -= 1
        self.bombs_used += 1
        columns = [c for c in range(self.rules.columns) if c not in self._holes[self.depth]]
        found, vents, caches, _ = self._mine(columns)
        vault = self._descend(d.creak + d.bomb_pressure, vents)
        return DigResult(found, bombed=True, vented=vents, caches=caches, vault=vault)

    def brace(self) -> None:
        """Shore up the tunnel: lower the pressure (uses a brace, skips a dig)."""
        self._require_live()
        if self.braces <= 0:
            raise MiningError("You're out of braces.")
        self.braces -= 1
        self.danger = max(0.0, self.danger - self.rules.descent.brace_amount)

    def leave(self) -> None:
        """Climb out with everything you're carrying."""
        self._require_live()
        self.outcome = "left"


@dataclass(frozen=True)
class RunSummary:
    outcome: str
    haul: Counter
    xp: int
    lodes: int
    depth: int


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


async def start_run(user: User, rng: random.Random, registry: Registry | None = None) -> MineRun:
    """Begin a mine. A full magnet is spent here; the pickaxe, reactor and gems shape the run."""
    reg = registry or get_registry()
    rules = reg.mining
    d = rules.descent
    tool = await equipped_stats(user, "mining", reg)
    if tool is None:
        raise MiningError("You need a pickaxe. Buy a Rookie Pickaxe in the shop (it's equipped for you).")
    mining, _ = await _mining_state(user)
    magnet = mining.magnet_meter >= rules.magnet.capacity
    if magnet:
        await user.update_skill("mining", lambda m: setattr(m, "magnet_meter", 0))
    pet = await pets.bonuses(user, reg)
    power = tool.power
    reduction = d.reactor_reduction * (mining.reactor.level - 1) + tool.stats.get("danger_reduction", 0) + pet.get("danger_reduction", 0)
    bombs = min(await user.item_quantity(BOMB_ITEM), d.bombs_per_run)
    return MineRun(
        rules,
        reg,
        rng,
        cursors=_start_cursors(columns_dug(mining.reactor.level, rules), rules.columns),
        bombs=bombs,
        growth_factor=1 - min(d.max_reduction, reduction),
        yield_factor=(1 + d.power_yield_bonus * max(0, power - d.power_base)) * (1 + pet.get("ore_yield", 0.0) + tool.stats.get("ore_yield", 0.0)),
        braces=d.braces_base + (mining.reactor.level - 1) // d.braces_per_reactor_levels + int(tool.stats.get("braces", 0)),
        magnet=magnet,
        wyrmhole_odds_value=wyrmhole_odds(gems_placed(mining), rules),
        rich_bonus=tool.stats.get("rich_chance", 0.0),
        vault_gem_bonus=tool.stats.get("vault_gem", 0.0),
    )


async def use_bomb(user: User, run: MineRun) -> DigResult:
    """Spend one bomb from the inventory (atomically) and blow the row. Refunded if the run refuses."""
    if run.finished or run.bombs <= 0:
        run.bomb()  # raises the right MiningError without touching the inventory
    try:
        await user.remove_item(BOMB_ITEM, 1)
    except ValueError:
        run.bombs = 0
        raise MiningError("You don't have a bomb.") from None
    try:
        return run.bomb()
    except Exception:
        await user.add_item(BOMB_ITEM, 1)
        raise


def _start_cursors(count: int, columns: int) -> list[int]:
    """Cursors start in the middle and fan out."""
    middle_out = sorted(range(columns), key=lambda c: abs(c - columns // 2))
    return middle_out[:count]


async def settle_run(user: User, run: MineRun, registry: Registry | None = None) -> RunSummary:
    """Bank a finished run: items, xp and stats. Idempotent (runs once per run)."""
    rules = (registry or get_registry()).mining
    if not run.finished:
        raise MiningError("The mine isn't finished.")
    if run.settled:
        return RunSummary(run.outcome, Counter(run.haul), run.xp_awarded, run.lodes, run.depth)
    run.settled = True
    xp = round(rules.xp_per_column * run.lodes * await xp_multiplier(user.id, registry, "mining"))
    run.xp_awarded = xp
    summary = RunSummary(run.outcome, Counter(run.haul), xp, run.lodes, run.depth)
    log.info("mine over: %s at row %d/%d, pressure %.1f, risk on the last dig %.2f%%, %d lodes",
             run.outcome, run.depth, run.floor, run.last_pressure, run.last_risk * 100, run.lodes)
    for item_id, quantity in (await pets.roll_food("mining", run.lodes, run.rng, registry)).items():
        run.haul[item_id] += quantity  # pet food turns up in the rock too
        summary.haul[item_id] += quantity
    for item_id, quantity in run.haul.items():
        await user.add_item(item_id, quantity)

    def record(m: Mining) -> None:
        m.xp += xp
        m.stats.lodes_mined += run.lodes

    await user.update_skill("mining", record)
    return summary


async def abandon_run(user: User, run: MineRun, registry: Registry | None = None) -> None:
    """The player walked away mid-run (timeout): climb out safely with what they have."""
    if not run.finished:
        run.leave()
    await settle_run(user, run, registry)


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
        claimed["depth"] = min(m.reactor.level - 1, len(rules.depth_tables) - 1)
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
