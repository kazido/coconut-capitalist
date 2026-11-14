"""Fishing rules: cast, wait for a bite, reel the fish in.

A **cast** is a plain object held by the screen (like a mining run or a private tree). Everything about it is decided
when the line goes in (which fish, when it bites, which arrows to press), so reopening the panel can't re-roll it.
Time is passed in, not read, so tests can move the clock. Nothing is paid until the fish is landed, once.

All randomness comes from an injected ``random.Random``.
"""

import random
import time
from collections import Counter
from dataclasses import dataclass, field, replace

from cococap.constants import Rarities
from cococap.errors import GameRuleError
from cococap.models.skills.fishing import TreasureState
from cococap.registry import Item, Registry, get_registry
from cococap.registry.models import FishingRules, WaterRules
from cococap.services import shop
from cococap.services.equipment import EffectiveStats, equipped_stats
from cococap.services.loot import roll_drop, roll_table
from cococap.services.party import xp_multiplier
from cococap.user import User

LEFT, RIGHT = "◀", "▶"
REEL, MYSTERY = "🌀", "❓"  # a step that wants the Reel button; an arrow hidden until you press it


class FishingError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


# ---- the fish ---------------------------------------------------------------------------------------------
def fish_pool(registry: Registry) -> list[Item]:
    """Every fish that can bite, rarest first (so the first that "drops" wins and the common catch-all is last)."""
    fish = [i for i in registry.items.values() if i.skill == "fishing" and i.category == "fish" and i.drop]
    return sorted(fish, key=lambda i: (-i.drop.rate, -i.rarity, i.id))


def water_by_id(registry: Registry, water_id: str) -> WaterRules:
    return next(w for w in registry.fishing.waters if w.id == water_id)


def unlocked_waters(level: int, rules: FishingRules) -> list[WaterRules]:
    return [w for w in rules.waters if level >= w.min_level]


def require_water(level: int, water_id: str, rules: FishingRules) -> WaterRules:
    water = next((w for w in rules.waters if w.id == water_id), None)
    if water is None:
        raise FishingError("There is no such water.")
    if level < water.min_level:
        raise FishingError(f"{water.name} opens at fishing level {water.min_level}.")
    return water


def quest_pool(registry: Registry) -> list[Item]:
    """The fish quests and community goals may ask for: only those from the first waters (the ones opened by the level
    that unlocks quests), so everybody who has quests can actually finish them."""
    rules = registry.fishing
    open_at = rules.quests.min_level
    ids = {f for w in rules.waters if w.min_level <= open_at for f in w.fish}
    return [i for i in fish_pool(registry) if i.id in ids]


def roll_fish(rng: random.Random, registry: Registry | None = None, water: WaterRules | None = None) -> Item:
    """What bites: from one water's fish (rarest first, the commonest as the catch-all), or from every fish."""
    reg = registry or get_registry()
    if water is not None:
        odds = sorted(water.fish.items(), key=lambda kv: -kv[1])
        for fish_id, rate in odds:
            if rng.randint(1, rate) == 1:
                return reg.item(fish_id)
        return reg.item(odds[-1][0])
    found = roll_table([i.id for i in fish_pool(reg)], reg, rng)
    return reg.item(found[0]) if found else fish_pool(reg)[-1]


# ---- the rod ----------------------------------------------------------------------------------------------
def wait_seconds(power: int, rules: FishingRules, rng: random.Random, bite_speed: float = 0.0) -> float:
    """How long until something bites: shorter with a stronger rod (and a Lure enchant: ``bite_speed``)."""
    base = rng.uniform(rules.bite.wait_min, rules.bite.wait_max)
    factor = max(rules.bite.min_wait_factor, 1 / (1 + rules.bite.speedup_per_power * max(0, power - 1)))
    return base * factor * (1 - min(0.6, max(0.0, bite_speed)))


def slips_allowed(power: int, rules: FishingRules, bonus: float = 0) -> int:
    """Wrong arrows a rod forgives per fish (a Steady Line enchant adds more: ``bonus``)."""
    return max(0, power) // rules.reel.power_per_slip + int(bonus)


def reel_pattern(rarity: int, rules: FishingRules, rng: random.Random) -> list[str]:
    return [rng.choice((LEFT, RIGHT)) for _ in range(rules.reel.base_length + rarity)]


def _other(arrow: str) -> str:
    return RIGHT if arrow == LEFT else LEFT


def _mystery_arrow(tell: str, previous: str, rng: random.Random) -> str:
    """What a fish's ❓ turns out to be, given the arrow before it."""
    return {"left": LEFT, "right": RIGHT, "same": previous, "opposite": _other(previous)}.get(tell) or rng.choice((LEFT, RIGHT))


def build_reel(fish: Item, rules: FishingRules, rng: random.Random, *, arrows: int | None = None,
               mysteries: bool = True) -> tuple[list[str], list[str]]:
    """The steps of a reel and what each one really wants. Mostly arrows; tougher fish also make you stop and press
    Reel now and then, and the toughest hide some arrows behind a ❓ that follows the fish's own hidden pattern (its
    tell). Returns (what is shown, what is actually required)."""
    r = rules.reel
    n = arrows if arrows is not None else r.base_length + fish.rarity
    actual = [rng.choice((LEFT, RIGHT)) for _ in range(n)]
    hidden: set[int] = set()
    if mysteries and fish.reel is not None and fish.rarity >= r.mystery_from_rarity and n > 1:
        count = fish.rarity - r.mystery_from_rarity + 1
        if fish.reel.tell == "random":
            count = min(count, r.max_random_mysteries)
        for pos in sorted(rng.sample(range(1, n), min(count, n - 1))):
            actual[pos] = _mystery_arrow(fish.reel.tell, actual[pos - 1], rng)
            hidden.add(pos)
    shown = [MYSTERY if i in hidden else a for i, a in enumerate(actual)]
    breaks = n // r.arrows_per_break if fish.rarity >= r.break_from_rarity else 0
    for gap in sorted(rng.sample(range(1, n), min(breaks, n - 1)), reverse=True):
        shown.insert(gap, REEL)
        actual.insert(gap, REEL)
    return shown, actual


# ---- a cast -----------------------------------------------------------------------------------------------
NOTES_KEPT = 12  # field notes kept per fish


def _remember(skill, cast: "Cast") -> None:
    """Add what this cast's ❓ steps turned out to be to your field notes for that fish."""
    if cast.reveals:
        notes = skill.notes.setdefault(cast.fish.id, [])
        notes.extend(f"{before}>{truth}" for before, truth in cast.reveals)
        del notes[:-NOTES_KEPT]


async def note_tells(user: User, cast: "Cast") -> None:
    """A fish got away, but you still learned what its ❓ was: write it in your field notes."""
    if cast.reveals and not cast.boss:
        await user.update_skill("fishing", lambda skill: _remember(skill, cast))


def read_notes(notes: list[str]) -> str:
    """Field notes as a short line: "after ◀ it was ▶ (twice), after ▶ it was ▶"."""
    from collections import Counter as _Counter

    seen = _Counter(notes)
    return ", ".join(f"after {pair[0]} → {pair[2]}" + (f" ×{n}" if n > 1 else "") for pair, n in seen.items())


@dataclass
class Cast:
    fish: Item
    bite_at: float
    expires_at: float  # the fish gets away if you haven't pulled up the line by now
    pattern: list[str]
    slips_left: int
    hooked: bool = False
    progress: int = 0
    escaped: bool = False
    settled: bool = False
    boss: str = ""  # the boss's name, if what bit was a boss rather than a fish
    chest: bool = False  # a treasure chest instead of a fish (the fish is only a stand-in until it is hooked)
    attempts_left: int = 0  # tries at the chest's lock
    grace: float = 0.0  # quiet extra seconds to pull up the line (laggy connections)
    echo_window: float = 0.0  # a repeat of the arrow just pressed within this long is ignored
    truth: list[str] = field(default_factory=list)  # what each step really wants (differs from `pattern` only at a ❓)
    reveals: list[tuple[str, str]] = field(default_factory=list)  # (the arrow before, what the ❓ was) for each ❓ you pressed
    revealed: set[int] = field(default_factory=set)
    size: float = 0.0  # in cm, fixed when you cast like everything else
    timed_out: bool = False  # it got away because the time ran out (as opposed to a wrong arrow)
    last_press: tuple[str, float] | None = None  # (the arrow that last counted, when)

    @property
    def deadline(self) -> float:
        return self.expires_at + self.grace

    def status(self, now: float) -> str:
        """waiting | bite | reeling | chest | landed | escaped.  ("bite" = it's on, pull up the line!)"""
        if self.escaped:
            return "escaped"
        if self.chest and self.hooked:
            return "chest" if not self.settled else "landed"
        if self.progress >= len(self.pattern):
            return "landed"
        if self.hooked:
            return "reeling"
        if now < self.bite_at:
            return "waiting"
        if now > self.deadline:
            self.escaped = self.timed_out = True  # nobody pulled up the line in time
            return "escaped"
        return "bite"

    def wanted(self, index: int) -> str:
        """What step `index` really needs (a ❓ is secretly an arrow)."""
        return self.truth[index] if self.truth else self.pattern[index]

    @property
    def next_arrow(self) -> str | None:
        """What the next press has to be (the truth behind a ❓, which the player can't see)."""
        return self.wanted(self.progress) if self.progress < len(self.pattern) else None

    def hook(self, now: float) -> None:
        """Pull up the line when it bites. Reeling can't start before this, so the game never starts by itself."""
        status = self.status(now)
        if status == "waiting":
            raise FishingError("Nothing is biting yet.")
        if status == "escaped":
            raise FishingError("The fish got away.")
        if status == "bite":
            self.hooked = True

    def salvage(self, clicked_at: float) -> bool:
        """The fish was written off as too slow, but the click that pulls it up was made in time and only reached us
        late (Discord or the bot lagged). Take the fish back. Returns whether it was saved."""
        if self.timed_out and self.bite_at <= clicked_at <= self.deadline:
            self.escaped = self.timed_out = False
            self.hooked = True
            return True
        return False

    def press(self, arrow: str, now: float) -> str:
        """Press an arrow. Returns ``ok | echo | slip | landed | escaped``.  ("echo" = the same arrow pressed twice
        in a moment, usually because the panel was slow to show the first press: ignored.)"""
        status = self.status(now)
        if status in ("waiting", "bite"):
            raise FishingError("Nothing is biting yet." if status == "waiting" else "Pull up the line first!")
        if status == "chest":
            raise FishingError("That's a chest, not a fish. Enter the numbers!")
        if status == "escaped":
            raise FishingError("That fish is already gone.")
        if status == "landed":
            raise FishingError("You already landed that one.")
        right = arrow == self.next_arrow
        if not right and self.last_press and arrow == self.last_press[0] and 0 <= now - self.last_press[1] <= self.echo_window:
            return "echo"
        if self.pattern[self.progress] == MYSTERY and self.progress not in self.revealed:  # right or wrong, the ❓ is now known
            before = next((self.wanted(i) for i in range(self.progress - 1, -1, -1) if self.wanted(i) != REEL), LEFT)
            self.reveals.append((before, self.wanted(self.progress)))
            self.revealed.add(self.progress)
        if right:
            self.progress += 1
            self.last_press = (arrow, now)
            return "landed" if self.progress >= len(self.pattern) else "ok"
        if self.slips_left > 0:
            self.slips_left -= 1
            return "slip"
        self.escaped = True
        return "escaped"


def roll_size(fish: Item, rng: random.Random) -> float:
    """A fish's size in cm: most catches are smallish, the odd one is a giant."""
    size = fish.size
    return round(size.min + (size.max - size.min) * rng.random() ** 2, 1)


def cast_line(stats: EffectiveStats, rng: random.Random, now: float | None = None, registry: Registry | None = None,
              *, armed: bool = False, water: WaterRules | None = None) -> Cast:
    """Put the line in the water: pick the fish, the bite time and the arrows. While a hallucination lasts
    (``armed``), the catch may turn out to be a treasure chest instead."""
    reg = registry or get_registry()
    rules = reg.fishing
    now = time.time() if now is None else now
    fish = roll_fish(rng, reg, water)
    bite_at = now + wait_seconds(stats.power, rules, rng, stats.stats.get("bite_speed", 0.0)) * (
        water.wait_multiplier if water else 1.0)
    pattern, truth = build_reel(fish, rules, rng)
    cast = Cast(
        fish=fish,
        bite_at=bite_at,
        expires_at=bite_at + rules.bite.window,
        pattern=pattern,
        truth=truth,
        slips_left=slips_allowed(stats.power, rules, stats.stats.get("slips", 0)),
        grace=rules.bite.grace,
        echo_window=rules.reel.echo_window,
        size=roll_size(fish, rng),
    )
    if armed and rng.randint(1, rules.treasure.chest_odds) == 1:
        cast.chest, cast.attempts_left = True, rules.treasure.attempts
    elif rng.randint(1, rules.boss.odds) == 1:
        cast.boss = rng.choice(rules.boss.names)
        cast.pattern, cast.truth = build_reel(fish, rules, rng, arrows=rules.boss.length, mysteries=False)
    return cast


# ---- operations on a player (these persist) ---------------------------------------------------------------
async def rod_stats(user: User, registry: Registry | None = None) -> EffectiveStats:
    stats = await equipped_stats(user, "fishing", registry)
    if stats is None:
        raise FishingError("You need a rod. Buy a Starter Rod in the shop (it's equipped for you).")
    return stats


# ---- quests -----------------------------------------------------------------------------------------------
DAY = 86_400


def day_of(now: float) -> int:
    return int(now // DAY)


def week_of(now: float) -> int:
    """Weeks run Monday to Sunday (UTC). Day 0 was a Thursday, hence the +3."""
    return (day_of(now) + 3) // 7


@dataclass(frozen=True)
class Quest:
    """"Catch `count` of this fish." What it asks for and pays is fixed by the clock and the player."""

    kind: str  # daily | weekly
    index: int
    fish: Item
    count: int
    bits: int
    xp: int
    progress: int = 0
    done: bool = False

    @property
    def text(self) -> str:
        return f"Catch {self.count} {self.fish.display}"


def _chosen(kind: str, user_id: int, period: int, reg: Registry) -> list[tuple[Item, int, int, int]]:
    """(fish, count, bits, xp) for each quest slot: a fish of the slot's rarity (a different one per slot where
    possible) and a count in the slot's range. Same for the whole period, different for each player."""
    rules = reg.fishing.quests
    rng = random.Random(f"fishing-quests:{kind}:{user_id}:{period}")
    slots = rules.daily if kind == "daily" else rules.weekly
    multiplier = rules.daily_bits_multiplier if kind == "daily" else rules.weekly_bits_multiplier
    pool, taken, chosen = quest_pool(reg), set(), []
    for slot in slots:
        options = [i for i in pool if i.rarity == slot.rarity]
        fresh = [i for i in options if i.id not in taken] or options
        fish = rng.choice(sorted(fresh, key=lambda i: i.id))
        taken.add(fish.id)
        count = rng.randint(slot.min_count, slot.max_count)
        chosen.append((fish, count, round(fish.sell_price * count * multiplier), fish.rarity * count * rules.xp_per_rarity))
    return chosen


def _period(kind: str, now: float) -> int:
    return day_of(now) if kind == "daily" else week_of(now)


def quests_unlocked(level: int, rules: FishingRules) -> bool:
    return level >= rules.quests.min_level


def _quests_of(kind: str, user_id: int, saved, now: float, reg: Registry) -> list[Quest]:
    period = _period(kind, now)
    chosen = _chosen(kind, user_id, period, reg)
    same = saved.period == period and len(saved.progress) == len(chosen)
    return [
        Quest(kind, i, fish, count, bits, xp, saved.progress[i] if same else 0, saved.done[i] if same else False)
        for i, (fish, count, bits, xp) in enumerate(chosen)
    ]


async def quests(user: User, now: float | None = None, registry: Registry | None = None) -> list[Quest]:
    """This player's quests right now (empty until fishing level 3). Daily ones first."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    skill = await user.skill("fishing")
    if not quests_unlocked(User.xp_to_level(skill.xp), reg.fishing):
        return []
    return _quests_of("daily", user.id, skill.daily, now, reg) + _quests_of("weekly", user.id, skill.weekly, now, reg)


@dataclass(frozen=True)
class Catch:
    fish: Item
    xp: int
    finished: tuple[Quest, ...] = ()  # quests this catch completed (already paid)
    quest_bits: int = 0
    extras: Counter = field(default_factory=Counter)  # things that came up with the fish (coral shards...)
    hallucination: str | None = None  # the numbers you saw, if this catch made you hallucinate
    reveals: tuple[tuple[str, str], ...] = ()  # what each ❓ in the reel turned out to be
    size: float = 0.0
    personal_best: bool = False  # your biggest of this fish so far (including your first one)
    server_record: bool = False  # the biggest ever caught on the server
    record_bits: int = 0
    record_holder: str | None = None  # who held the server record before you


def catch_extras(rng: random.Random, registry: Registry) -> Counter:
    """Materials that come up with a catch (fishing items that aren't fish but have a drop table)."""
    found: Counter = Counter()
    for item in registry.items_for_skill("fishing"):
        if item.category == "material" and (quantity := roll_drop(item, rng)):
            found[item.id] += quantity
    return found


async def land(user: User, cast: Cast, registry: Registry | None = None, now: float | None = None,
               rng: random.Random | None = None) -> Catch:
    """Keep a fish that has been fully reeled in: item, xp, stats and quest progress. Pays once per cast."""
    reg = registry or get_registry()
    rules = reg.fishing
    now = time.time() if now is None else now
    if cast.boss:
        raise FishingError("That's a boss, not a fish.")
    if cast.progress < len(cast.pattern) or cast.escaped:
        raise FishingError("That fish isn't landed.")
    if cast.settled:
        raise FishingError("You already took that fish.")
    cast.settled = True
    multiplier = await xp_multiplier(user.id, reg)
    xp = round(cast.fish.rarity * rules.xp_per_rarity * multiplier)
    await user.add_item(cast.fish.id, 1)
    extras = catch_extras(rng or random.Random(), reg)
    for item_id, quantity in extras.items():
        await user.add_item(item_id, quantity)
    finished: list[Quest] = []
    seen: list[str] = []
    best: list[bool] = []
    counts_for_community: list[bool] = []
    dice = rng or random.Random()

    def grant(skill) -> None:
        skill.xp += xp
        skill.stats.fish_caught += 1
        _remember(skill, cast)
        if cast.size > 0 and cast.size > skill.records.get(cast.fish.id, 0):
            skill.records[cast.fish.id] = cast.size
            skill.xp += cast.fish.rarity * rules.records.personal_xp_per_rarity
            best.append(True)
        t = rules.treasure
        if skill.treasure.armed_until <= now and dice.randint(1, t.hallucination_odds) == 1:
            code = "".join(dice.choice("0123456789") for _ in range(t.code_length))
            skill.treasure = TreasureState(code=code, armed_until=now + t.armed_minutes * 60)
            seen.append(code)
        if not quests_unlocked(User.xp_to_level(skill.xp - xp), rules):  # unlocked before this catch, not by it
            return
        counts_for_community.append(True)
        for kind in ("daily", "weekly"):
            saved = getattr(skill, kind)
            current = _quests_of(kind, user.id, saved, now, reg)
            progress = [q.progress for q in current]
            done = [q.done for q in current]
            for q in current:
                if not q.done and cast.fish.id == q.fish.id:
                    progress[q.index] += 1
                    if progress[q.index] >= q.count:
                        done[q.index] = True
                        finished.append(replace(q, progress=progress[q.index], done=True))
            setattr(skill, kind, saved.__class__(period=_period(kind, now), progress=progress, done=done))
        skill.xp += round(sum(q.xp for q in finished) * multiplier)
        skill.stats.quests_completed += len(finished)

    await user.update_skill("fishing", grant)
    if counts_for_community:
        from cococap.services import fishing_community  # (it builds on this module)

        await fishing_community.record_catch(user, cast.fish, now, reg)
    quest_bits = sum(q.bits for q in finished)
    if quest_bits:
        await user.add_bits(quest_bits)
    server_record, holder, record_bits = False, None, 0
    if best:
        server_record, holder = await _claim_server_record(user, cast.fish, cast.size)
        if server_record:
            record_bits = round(cast.fish.sell_price * rules.records.server_bits_multiplier)
            await user.add_bits(record_bits)
    return Catch(cast.fish, xp, tuple(finished), quest_bits, extras, seen[0] if seen else None,
                 tuple(cast.reveals), cast.size, bool(best), server_record, record_bits, holder)


RECORDS_KEY = "fishing_records"


async def _claim_server_record(user: User, fish: Item, size: float) -> tuple[bool, str | None]:
    """Is this the biggest of its kind ever caught here? Returns (yes?, who held it before)."""
    from cococap.services import community

    outcome: dict = {}

    def claim(records: dict) -> None:
        held = records.get(fish.id)
        outcome["holder"] = held["name"] if held else None
        if held is None or size > held["size"]:
            records[fish.id] = {"size": size, "uid": user.id, "name": user.name}
            outcome["won"] = True

    await community.update(RECORDS_KEY, {}, claim)
    return bool(outcome.get("won")), outcome["holder"]


async def server_records() -> dict[str, dict]:
    from cococap.services import community

    return await community.read(RECORDS_KEY, {})


@dataclass(frozen=True)
class FishStock:
    items: Counter = field(default_factory=Counter)
    worth: int = 0

    @property
    def count(self) -> int:
        return sum(self.items.values())


async def stock(user: User, registry: Registry | None = None) -> FishStock:
    """The fish in the player's inventory and what they would sell for."""
    reg = registry or get_registry()
    owned = await user.items()
    fish = Counter({i.id: owned[i.id] for i in fish_pool(reg) if owned.get(i.id)})
    return FishStock(fish, sum(reg.item(i).sell_price * q for i, q in fish.items()))


async def sell_all(user: User, registry: Registry | None = None) -> int:
    """Sell every fish in the inventory. Returns the bits received."""
    reg = registry or get_registry()
    total = 0
    for item_id, quantity in (await stock(user, reg)).items.items():
        total += await shop.sell(user, item_id, quantity, reg)
    return total


# ---- the personal collection book -------------------------------------------------------------------------
@dataclass(frozen=True)
class BookEntry:
    fish: Item
    given: int
    need: int

    @property
    def done(self) -> bool:
        return self.given >= self.need


@dataclass(frozen=True)
class BookView:
    level: int
    entries: tuple[BookEntry, ...]

    @property
    def complete(self) -> bool:
        return all(e.done for e in self.entries)


def book_fish(registry: Registry) -> list[Item]:
    """The fish the personal book holds, commonest first."""
    rules = registry.fishing.book
    return sorted((i for i in fish_pool(registry) if i.rarity <= rules.max_rarity), key=lambda i: (i.rarity, i.name))


def book_need(level: int, rarity: int, rules: FishingRules) -> int:
    """How many of a fish of this rarity the book wants at this level: common fish grow fastest."""
    step = rules.book.need_step_by_rarity[rarity - 1]
    return rules.book.need_base + int((level - 1) * step)


def book_unlocked(level: int, rules: FishingRules) -> bool:
    return level >= rules.book.min_level


async def book(user: User, registry: Registry | None = None) -> BookView:
    reg = registry or get_registry()
    saved = (await user.skill("fishing")).book
    return BookView(saved.level, tuple(
        BookEntry(i, saved.given.get(i.id, 0), book_need(saved.level, i.rarity, reg.fishing)) for i in book_fish(reg)))


@dataclass(frozen=True)
class TurnedIn:
    fish: Item
    quantity: int
    bits: int
    xp: int


async def _require_book(user: User, reg: Registry) -> None:
    level = User.xp_to_level((await user.skill("fishing")).xp)
    if not book_unlocked(level, reg.fishing):
        raise FishingError(f"The collection book opens at fishing level {reg.fishing.book.min_level}.")


async def turn_in(user: User, fish_id: str, registry: Registry | None = None) -> TurnedIn:
    """Hand in as many of this fish as the book still needs (and you have). Pays a bonus per fish."""
    reg = registry or get_registry()
    rules = reg.fishing
    await _require_book(user, reg)
    fish = next((i for i in book_fish(reg) if i.id == fish_id), None)
    if fish is None:
        raise FishingError("The book has no page for that.")
    view = await book(user, reg)
    entry = next(e for e in view.entries if e.fish.id == fish_id)
    take = min(await user.item_quantity(fish_id), entry.need - entry.given)
    if entry.done:
        raise FishingError(f"Your book already has all the {fish.name} it needs.")
    if take <= 0:
        raise FishingError(f"You don't have any {fish.name}.")
    try:
        await user.remove_item(fish_id, take)
    except ValueError:
        raise FishingError(f"You don't have any {fish.name}.") from None
    multiplier = await xp_multiplier(user.id, reg)
    credited = 0

    def give(skill) -> None:
        nonlocal credited
        have = skill.book.given.get(fish_id, 0)
        credited = max(0, min(take, book_need(skill.book.level, fish.rarity, rules) - have))  # a second click may have filled it
        skill.book.given[fish_id] = have + credited
        skill.xp += round(credited * fish.rarity * rules.book.xp_per_rarity * multiplier)

    await user.update_skill("fishing", give)
    if credited < take:
        await user.add_item(fish_id, take - credited)  # the book didn't need them after all
    if credited == 0:
        raise FishingError(f"Your book already has all the {fish.name} it needs.")
    bits = round(fish.sell_price * rules.book.bits_per_sell * credited)
    if bits:
        await user.add_bits(bits)
    return TurnedIn(fish, credited, bits, round(credited * fish.rarity * rules.book.xp_per_rarity * multiplier))


@dataclass(frozen=True)
class BookReward:
    new_level: int
    bits: int
    xp: int


async def complete_book(user: User, registry: Registry | None = None) -> BookReward:
    """Finish a full book: it pays, goes up a level and starts over (each entry needs more fish)."""
    reg = registry or get_registry()
    rules = reg.fishing
    await _require_book(user, reg)
    multiplier = await xp_multiplier(user.id, reg)
    outcome: dict = {}

    def finish(skill) -> None:
        level = skill.book.level
        if not all(skill.book.given.get(i.id, 0) >= book_need(level, i.rarity, rules) for i in book_fish(reg)):
            outcome["error"] = "Your book isn't full yet."
        elif level >= rules.book.max_level:
            outcome["error"] = "Your book is already at its highest level."
        else:
            outcome["xp"] = round(rules.book.completion_xp * level * multiplier)
            outcome["bits"] = rules.book.completion_bits * level
            skill.book.level, skill.book.given = level + 1, {}
            skill.xp += outcome["xp"]
            outcome["level"] = level + 1

    await user.update_skill("fishing", finish)
    if "error" in outcome:
        raise FishingError(outcome["error"])
    await user.add_bits(outcome["bits"])
    return BookReward(outcome["level"], outcome["bits"], outcome["xp"])


# ---- treasure ---------------------------------------------------------------------------------------------
async def chests_possible(user: User, now: float | None = None) -> bool:
    """Is a hallucination still working on you (so a cast might bring up a chest)?"""
    now = time.time() if now is None else now
    return (await user.skill("fishing")).treasure.armed_until > now


@dataclass(frozen=True)
class ChestAttempt:
    opened: bool
    attempts_left: int
    sunk: bool = False  # out of tries (or the numbers were gone): the chest is lost
    bits: int = 0
    xp: int = 0
    items: Counter = field(default_factory=Counter)


def _digits(guess: str) -> str:
    return "".join(ch for ch in guess if ch.isdigit())


async def open_chest(user: User, cast: Cast, guess: str, rng: random.Random | None = None, now: float | None = None,
                     registry: Registry | None = None) -> ChestAttempt:
    """Try the four numbers on a chest's lock. The right ones open it (once) and pay out; too many wrong tries sink it."""
    reg = registry or get_registry()
    t = reg.fishing.treasure
    now = time.time() if now is None else now
    rng = rng or random.Random()
    if cast.status(now) != "chest":
        raise FishingError("There is no chest to open.")
    attempt = _digits(guess)
    outcome: dict = {}

    def try_lock(skill) -> None:
        code = skill.treasure.code
        if code and attempt == code:
            skill.treasure = TreasureState()  # the numbers are used up
            skill.stats.treasures_found += 1
            skill.xp += t.xp
            outcome["ok"] = True
        elif not code:
            outcome["gone"] = True

    await user.update_skill("fishing", try_lock)
    if outcome.get("ok"):
        cast.settled = True
        bits = rng.randint(t.bits_min, t.bits_max)
        items: Counter = Counter()
        for row in t.loot:
            if rng.random() < row.chance:
                items[row.item] += rng.randint(row.min, row.max)
        for item_id, quantity in items.items():
            await user.add_item(item_id, quantity)
        if bits:
            await user.add_bits(bits)
        return ChestAttempt(True, cast.attempts_left, bits=bits, xp=t.xp, items=items)
    cast.attempts_left = 0 if outcome.get("gone") else cast.attempts_left - 1
    if cast.attempts_left <= 0:
        cast.escaped = True
        await user.update_skill("fishing", lambda s: setattr(s, "treasure", TreasureState()))  # the spell is broken
        return ChestAttempt(False, 0, sunk=True)
    return ChestAttempt(False, cast.attempts_left)


# ---- bosses ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class BossReward:
    name: str
    bits: int
    xp: int
    items: Counter


async def defeat_boss(user: User, cast: Cast, rng: random.Random | None = None, registry: Registry | None = None) -> BossReward:
    """Pay out a boss that has been reeled all the way in (once). There is no fish: just bits, xp and loot."""
    reg = registry or get_registry()
    b = reg.fishing.boss
    rng = rng or random.Random()
    if not cast.boss:
        raise FishingError("That isn't a boss.")
    if cast.progress < len(cast.pattern) or cast.escaped:
        raise FishingError("That boss isn't beaten.")
    if cast.settled:
        raise FishingError("You already collected that.")
    cast.settled = True
    bits = rng.randint(b.bits_min, b.bits_max)
    items: Counter = Counter()
    for row in b.loot:
        if rng.random() < row.chance:
            items[row.item] += rng.randint(row.min, row.max)
    xp = round(b.xp * await xp_multiplier(user.id, reg))

    def win(skill) -> None:
        skill.xp += xp
        skill.stats.bosses_beaten += 1

    await user.update_skill("fishing", win)
    for item_id, quantity in items.items():
        await user.add_item(item_id, quantity)
    if bits:
        await user.add_bits(bits)
    return BossReward(cast.boss, bits, xp, items)
