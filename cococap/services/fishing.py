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
from cococap.services import areas, shop, stars
from cococap.services.equipment import EffectiveStats, equipped_stats
from cococap.services.loot import roll_drop, roll_table
from cococap.services import pets
from cococap.services.party import xp_multiplier
from cococap.user import InsufficientFunds, User

LEFT, RIGHT = "◄", "►"  # (not ◀ ▶: Discord draws those as blue emoji in some places and as plain text in others)
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


def water_level(registry: Registry, water_id: str) -> int:
    """The fishing level a water opens at: its location's level (areas.location_levels), never written on the water."""
    return next(loc.min_level for loc in registry.locations.get("fishing", []) if loc.id == water_id)


async def open_waters(user: User, registry: Registry | None = None) -> list[WaterRules]:
    """The waters you can fish right now: open by level AND by area (areas.open_location_list), shallowest first."""
    reg = registry or get_registry()
    ids = {loc.id for loc in await areas.open_location_list(user, "fishing", reg)}
    return [w for w in reg.fishing.waters if w.id in ids]


async def require_water(user: User, water_id: str, registry: Registry | None = None) -> WaterRules:
    for water in await open_waters(user, registry):
        if water.id == water_id:
            return water
    raise FishingError("You haven't opened that water yet.")


def quest_pool(registry: Registry) -> list[Item]:
    """The fish quests and community goals may ask for: only those from the first waters (the ones opened by the level
    that unlocks quests), so everybody who has quests can actually finish them."""
    rules = registry.fishing
    open_at = rules.quests.min_level
    ids = {f for w in rules.waters if water_level(registry, w.id) <= open_at for f in w.fish}
    return [i for i in fish_pool(registry) if i.id in ids]


def roll_fish(rng: random.Random, registry: Registry | None = None, water: WaterRules | None = None,
              rare_luck: float = 0.0, chase: dict[str, float] | None = None) -> Item:
    """What bites: from one water's fish (rarest first, the commonest as the catch-all), or from every fish.
    ``rare_luck`` (a pet's bonus) makes the rare fish (rarity 4 and up) that much more likely. ``chase`` (the radar) makes the named fish
    that many times likelier (their odds are divided by the factor)."""
    reg = registry or get_registry()
    if water is not None:
        odds = sorted(water.fish.items(), key=lambda kv: -kv[1])
        for fish_id, rate in odds:
            if reg.item(fish_id).rarity >= 4:
                rate = max(1, round(rate / (1 + rare_luck)))
            if chase and fish_id in chase:
                rate = max(1, round(rate / chase[fish_id]))
            if rng.randint(1, rate) == 1:
                return reg.item(fish_id)
        return reg.item(odds[-1][0])
    found = roll_table([i.id for i in fish_pool(reg)], reg, rng)
    return reg.item(found[0]) if found else fish_pool(reg)[-1]


def water_chances(water: WaterRules) -> dict[str, float]:
    """The real chance of each fish on one cast in this water (rarest rolled first, the commonest takes what is left), without luck."""
    odds = sorted(water.fish.items(), key=lambda kv: -kv[1])
    chances, left = {}, 1.0
    for index, (fish_id, rate) in enumerate(odds):
        p = left if index == len(odds) - 1 else left / rate
        chances[fish_id] = p
        left -= p
    return chances


def where_to_catch(fish_id: str, registry: Registry | None = None) -> list[tuple[WaterRules, float]]:
    """Every water this fish lives in with its chance per cast there, the best place first."""
    reg = registry or get_registry()
    found = [(w, water_chances(w)[fish_id]) for w in reg.fishing.waters if fish_id in w.fish]
    return sorted(found, key=lambda e: -e[1])


# ---- the rod ----------------------------------------------------------------------------------------------
def wait_seconds(power: int, rules: FishingRules, rng: random.Random, bite_speed: float = 0.0) -> float:
    """How long until something bites: shorter with a stronger rod (and a Lure enchant: ``bite_speed``)."""
    base = rng.uniform(rules.bite.wait_min, rules.bite.wait_max)
    factor = max(rules.bite.min_wait_factor, 1 / (1 + rules.bite.speedup_per_power * max(0, power - 1)))
    return base * factor * (1 - min(0.6, max(-0.5, bite_speed)))  # (a Mastery trade-off can make bites slower, up to half again)


class _Middle(random.Random):
    """A random source that always lands in the middle of a range (so `typical_wait` is the average, not a roll)."""

    def uniform(self, a, b):
        return (a + b) / 2


def typical_wait(power: int, rules: FishingRules, bite_speed: float = 0.0) -> float:
    """The middle of how long a bite takes with this rod: what the fishing page tells you to expect."""
    return wait_seconds(power, rules, _Middle(), bite_speed)


def slips_allowed(power: int, rules: FishingRules, bonus: float = 0) -> int:
    """Wrong arrows a rod forgives per fish (a Steady Line enchant adds more: ``bonus``)."""
    return min(rules.reel.max_slips, max(0, power) // rules.reel.power_per_slip) + int(bonus)


def rod_luck(power: int, rules: FishingRules) -> float:
    """How much likelier the rare fish are with this rod (0.5 = +50%)."""
    return rules.rod.luck_per_power * max(0, power - 3)


def extra_fish(power: int, rules: FishingRules, rng: random.Random) -> int:
    """How many more fish than one this catch brings: a stronger rod hauls in more, with a fractional part rolled as a chance."""
    expected = rules.rod.extra_fish_per_power * max(0, power - 3)
    whole = int(expected)
    if expected == whole:
        return whole  # (no roll: a starter rod leaves the dice alone)
    return whole + (1 if rng.random() < expected - whole else 0)


def slack_bonus(worth: int, unused: int, rules: FishingRules) -> int:
    """What a clean reel earns: every slack you did not need pays `slack_bonus` of the catch's worth (a rod that forgives more pays more)."""
    return round(worth * rules.reel.slack_bonus * max(0, unused))


def reel_pattern(rarity: int, rules: FishingRules, rng: random.Random) -> list[str]:
    return [rng.choice((LEFT, RIGHT)) for _ in range(rules.reel.base_length + rarity)]


def _other(arrow: str) -> str:
    return RIGHT if arrow == LEFT else LEFT


def _mystery_arrow(tell: str, previous: str, first: str) -> str:
    """What a fish's ❓ turns out to be, given the arrow just before it and the first arrow of the reel."""
    return {"left": LEFT, "right": RIGHT, "last": previous, "first": first, "opposite": _other(previous)}[tell]


def build_reel(fish: Item, rules: FishingRules, rng: random.Random, *, arrows: int | None = None,
               mysteries: bool = True, wild: int = 0) -> tuple[list[str], list[str]]:
    """The steps of a reel and what each one really wants. Mostly arrows; tougher fish also make you stop and press
    Reel now and then, and the toughest hide some arrows behind a ❓ that follows the fish's own hidden pattern (its
    tell). Returns (what is shown, what is actually required)."""
    r = rules.reel
    n = arrows if arrows is not None else r.base_length + fish.rarity
    actual = [rng.choice((LEFT, RIGHT)) for _ in range(n)]
    hidden: set[int] = set()
    if wild and n > 1:  # a wild boss: coin-flip ❓ that can't be learned
        for pos in sorted(rng.sample(range(1, n), min(wild, n - 1))):
            actual[pos] = rng.choice((LEFT, RIGHT))
            hidden.add(pos)
    elif mysteries and fish.reel is not None and fish.rarity >= r.mystery_from_rarity and n > 1:
        count = fish.rarity - r.mystery_from_rarity + 1
        for pos in sorted(rng.sample(range(1, n), min(count, n - 1))):
            actual[pos] = _mystery_arrow(fish.reel.tell, actual[pos - 1], actual[0])
            hidden.add(pos)
    shown = [MYSTERY if i in hidden else a for i, a in enumerate(actual)]
    if fish.rarity >= r.break_from_rarity:
        # A Reel REPLACES an arrow (any of them, first and last included) and there is no cap: each arrow has a
        # 1-in-`arrows_per_break` chance. Never a ❓ (it stays hidden) and never an arrow a ❓ is worked out from.
        protected = set(hidden)
        tell = fish.reel.tell if fish.reel is not None and not wild else None  # a wild ❓ is a coin flip: depends on nothing
        for pos in hidden:
            if tell in ("last", "opposite"):
                protected.add(pos - 1)  # the arrow just before it
            if tell == "first":
                protected.add(0)  # the first arrow of the reel
        for pos in range(n):
            if pos not in protected and rng.choice(range(r.arrows_per_break)) == 0:  # (1 in N; choice, not random(), so the tests' rigged dice stay out of it)
                shown[pos] = actual[pos] = REEL
    return shown, actual


# ---- a cast -----------------------------------------------------------------------------------------------
NOTES_KEPT = 12  # field notes kept per fish


def _remember(skill, cast: "Cast") -> None:
    """Add what this cast's ❓ steps turned out to be to your field notes for that fish."""
    if cast.reveals:
        notes = skill.notes.setdefault(cast.fish.id, [])
        notes.extend(f"{before}>{truth}|{first}" for before, truth, first in cast.reveals)
        del notes[:-NOTES_KEPT]


async def note_tells(user: User, cast: "Cast") -> None:
    """A fish got away, but you still learned what its ❓ was: write it in your field notes."""
    if cast.reveals and not cast.boss:
        await user.update_skill("fishing", lambda skill: _remember(skill, cast))


_RULES = {"left": ("always ◄", lambda before, first: LEFT), "right": ("always ►", lambda before, first: RIGHT),
          "last": ("the same as the last arrow before it", lambda before, first: before),
          "first": ("the same as the FIRST arrow of the reel", lambda before, first: first),
          "opposite": ("the opposite of the last arrow before it", lambda before, first: _other(before))}
MIN_NOTES_FOR_VERDICT = 6  # a rule can fit by chance 1 time in 2**6: this many notes before a rule counts as CONFIRMED


def _fits(rule, entry: str) -> bool:
    """Does this note ("before>truth|first"; older notes have no "|first") agree with the rule? A note without the first arrow cannot rule "first" out."""
    before, truth, first = entry[0], entry[2], (entry[4] if len(entry) > 4 else None)
    return first is None and rule is _RULES["first"][1] or rule(before, first) == truth


def notes_verdict(entries: list[str]) -> str | None:
    """What your field notes add up to. A pattern is only ever stated once it is CONFIRMED: at least ``MIN_NOTES_FOR_VERDICT`` notes and exactly
    one rule explains every one of them. None while it is still unclear (too few notes, or two rules still fit)."""
    fits = [text for text, rule in _RULES.values() if all(_fits(rule, e) for e in entries)]
    if entries and not fits:
        return "no pattern fits these notes (an old note may be mixed in)"
    if len(entries) >= MIN_NOTES_FOR_VERDICT and len(fits) == 1:
        return f"confirmed: **{fits[0]}**"
    return None


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
    modifiers: list[str] = field(default_factory=list)  # the boss's twists: mirror, reverse, shuffle, fog, wild
    decoys: list[str] = field(default_factory=list)  # what a Reel step looks like until you get to it: an ordinary arrow
    xp: int = 0  # what landing it pays (the water's, set at the cast); 0 means the default per-catch xp
    extra_fish: int = 0  # more of the same fish this rod hauls in with it (decided at the cast, so it cannot be rerolled)
    chest: bool = False  # a treasure chest instead of a fish (the fish is only a stand-in until it is hooked)
    attempts_left: int = 0  # tries at the chest's lock
    grace: float = 0.0  # quiet extra seconds to pull up the line (laggy connections)
    echo_window: float = 0.0  # a repeat of the arrow just pressed within this long is ignored
    truth: list[str] = field(default_factory=list)  # what each step really wants (differs from `pattern` only at a ❓)
    reveals: list[tuple[str, str, str]] = field(default_factory=list)  # (the arrow before, what the ❓ was, the first arrow of the reel) for each ❓ you pressed
    revealed: set[int] = field(default_factory=set)
    size: float = 0.0  # in cm, fixed when you cast like everything else
    timed_out: bool = False  # it got away because the time ran out (as opposed to a wrong arrow)
    last_press: tuple[str, float] | None = None  # (the arrow that last counted, when)
    auto_steps: int = 0  # the Angler's Auto-Reel: this many of the first plain arrows are pressed for you when you pull up the line
    bycatch: float = 0.0  # the Treasure Hunter's Bycatch: the chance a catch brings a second, different fish
    water: object = None  # the water it was cast in (bycatch comes from there)
    slips_start: int = 0  # the forgiven wrong arrows this cast began with (so a clean reel, using none, can be told)
    public: bool = False  # the boss fight was opened to everyone (not just your party)
    party_fight: int | None = None  # the number of the party boss fight this reel belongs to (everyone in it reels their own set of arrows)
    quick: bool = False  # a Double Hook "Quick cast": it can never offer another one

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

    def display(self, index: int) -> str:
        """What step `index` looks like right now. A Reel step looks like an ordinary arrow until you reach it, and then
        it turns into 🌀: be ready."""
        step = self.pattern[index]
        if step == REEL and index > self.progress and self.decoys and self.decoys[index]:
            return self.decoys[index]
        return step

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
            self._auto_reel()

    def _auto_reel(self) -> None:
        """Auto-Reel: press the first few plain arrows for the player (never a Reel break or a ❓, and never the last step)."""
        done = 0
        while done < self.auto_steps and done < len(self.pattern) - 1 and self.pattern[done] in (LEFT, RIGHT):
            done += 1
        self.progress = max(self.progress, done)

    def salvage(self, clicked_at: float) -> bool:
        """The fish was written off as too slow, but the click that pulls it up was made in time and only reached us
        late (Discord or the bot lagged). Take the fish back. Returns whether it was saved."""
        if self.timed_out and self.bite_at <= clicked_at <= self.deadline:
            self.escaped = self.timed_out = False
            self.hooked = True
            self._auto_reel()
            return True
        return False

    def press(self, arrow: str, now: float) -> str:
        """Press an arrow. Returns ``ok | echo | slip | landed | escaped``.  ("echo" = the same arrow pressed twice
        in a moment, usually because the panel was slow to show the first press: ignored. Never when a Reel step is next: that is a miss.)"""
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
        if not right and self.next_arrow != REEL and self.last_press and arrow == self.last_press[0] and 0 <= now - self.last_press[1] <= self.echo_window:
            return "echo"
        if self.pattern[self.progress] == MYSTERY and self.progress not in self.revealed:  # right or wrong, the ❓ is now known
            before = next((self.wanted(i) for i in range(self.progress - 1, -1, -1) if self.wanted(i) != REEL), LEFT)
            self.reveals.append((before, self.wanted(self.progress), self.wanted(0)))
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
              *, armed: bool = False, water: WaterRules | None = None, pet: dict[str, float] | None = None, chase: dict[str, float] | None = None,
              plain: bool = False) -> Cast:
    """Put the line in the water: pick the fish, the bite time and the arrows. While a hallucination lasts
    (``armed``), the catch may turn out to be a treasure chest instead. ``plain`` makes it a fish for certain (no chest, no boss)."""
    reg = registry or get_registry()
    rules = reg.fishing
    now = time.time() if now is None else now
    pet = pet or {}
    luck = pet.get("rare_luck", 0.0) + stats.stats.get("rare_luck", 0.0) + rod_luck(stats.power, rules)
    fish = roll_fish(rng, reg, water, luck, chase) if chase else roll_fish(rng, reg, water, luck)
    if pet.get("rare_reroll") and fish.rarity < pets.RARE_FROM and rng.random() < pet["rare_reroll"]:  # a Fox: a free second cast of the dice, kept if it is rare
        again = roll_fish(rng, reg, water, luck, chase) if chase else roll_fish(rng, reg, water, luck)
        fish = again if again.rarity >= pets.RARE_FROM else fish
    bite_at = now + wait_seconds(stats.power, rules, rng, stats.stats.get("bite_speed", 0.0) + pet.get("bite_speed", 0.0)) * (
        water.wait_multiplier if water else 1.0)
    pattern, truth = build_reel(fish, rules, rng)
    decoys = [rng.choice((LEFT, RIGHT)) if step == REEL else "" for step in pattern]
    cast = Cast(
        fish=fish,
        bite_at=bite_at,
        expires_at=bite_at + rules.bite.window,
        pattern=pattern,
        truth=truth,
        decoys=decoys,
        slips_left=slips_allowed(stats.power, rules, stats.stats.get("slips", 0)),
        slips_start=slips_allowed(stats.power, rules, stats.stats.get("slips", 0)),
        grace=rules.bite.grace,
        echo_window=rules.reel.echo_window,
        size=roll_size(fish, rng),
        extra_fish=extra_fish(stats.power, rules, rng),
        xp=water.xp if water else 0,
        auto_steps=int(stats.stats.get("auto_reel", 0)),
        bycatch=stats.stats.get("bycatch", 0.0),
        water=water,
    )
    if plain:
        pass
    elif armed and rng.randint(1, max(1, round(rules.treasure.chest_odds / (1 + pet.get("treasure_luck", 0.0) + stats.stats.get("treasure_luck", 0.0))))) == 1:
        cast.chest, cast.attempts_left = True, rules.treasure.attempts
    elif rng.randint(1, max(1, round(rules.boss.odds / (1 + stats.stats.get("boss_luck", 0.0))))) == 1:
        make_boss(cast, rng.choice(rules.boss.bosses).name, rules, rng)
    return cast


def roll_double_hook(stats: EffectiveStats | None, rng: random.Random, rules: FishingRules) -> float | None:
    """Double Hook: after a plain landing, does a second line already bite? Returns how many seconds the "Quick cast" offer lasts, or None.
    The chance is the ``double_hook`` stat (rod enchant + Mastery) plus the config's base, capped; with no stat and no base it is never offered."""
    chance = min(rules.double_hook.cap, rules.double_hook.base_chance + (stats.stats.get("double_hook", 0.0) if stats else 0.0))
    if chance <= 0 or rng.random() >= chance:
        return None
    return rules.double_hook.window_seconds


def quick_cast(stats: EffectiveStats, rng: random.Random, now: float, water: WaterRules | None, registry: Registry | None = None,
               pet: dict[str, float] | None = None) -> Cast:
    """The Quick cast a Double Hook offered: your same rod in the same water, already biting (``bite_at`` is now), a plain fish (never a chest or a boss),
    and it can't offer another. From here it is an ordinary cast: hook it, reel it, land it."""
    reg = registry or get_registry()
    cast = cast_line(stats, rng, now, reg, water=water, pet=pet, plain=True)
    cast.bite_at, cast.expires_at, cast.quick = now, now + reg.fishing.bite.window, True
    return cast


def make_boss(cast: "Cast", boss_name: str, rules: FishingRules, rng: random.Random) -> None:
    """Turn a cast into a fight with the named boss: its own long reel (a different one for everyone who fights it) and its twists."""
    entry = next(b for b in rules.boss.bosses if b.name == boss_name)
    cast.boss, cast.modifiers = entry.name, list(entry.modifiers)
    cast.pattern, cast.truth = build_reel(cast.fish, rules, rng, arrows=rules.boss.length, mysteries=False,
                                          wild=rules.boss.wild_mysteries if "wild" in entry.modifiers else 0)
    cast.decoys = [rng.choice((LEFT, RIGHT)) if step == REEL else "" for step in cast.pattern]
    if "mirror" in entry.modifiers:  # press the OPPOSITE of what is shown
        cast.truth = [_other(t) if t in (LEFT, RIGHT) else t for t in cast.truth]


def join_boss_cast(stats: EffectiveStats, rng: random.Random, now: float, boss_name: str, registry: Registry | None = None,
                   pet: dict[str, float] | None = None) -> Cast:
    """Your own line in a party fight: already on, already hooked, with YOUR set of arrows to reel and your rod's slack."""
    reg = registry or get_registry()
    cast = cast_line(stats, rng, now, reg, armed=False, pet=pet)
    cast.chest, cast.attempts_left = False, 0
    make_boss(cast, boss_name, reg.fishing, rng)
    cast.hooked = True
    cast._auto_reel()
    return cast


# ---- operations on a player (these persist) ---------------------------------------------------------------
async def rod_stats(user: User, registry: Registry | None = None) -> EffectiveStats:
    stats = await equipped_stats(user, "fishing", registry)
    if stats is None:
        raise FishingError("You need a rod. Claim your free Starter Rod on the Tools page.")
    return stats


HOT_STREAK_MAX = 5  # clean reels in a row that count


async def lose_streak(user: User) -> None:
    """A fish got away: the streak starts over."""
    if (await user.skill("fishing")).streak:
        await user.update_skill("fishing", lambda skill: setattr(skill, "streak", 0))


def salvage_loot(rng: random.Random, registry: Registry) -> Counter:
    """One roll of the treasure chest's loot table (no bits, no lock to pick): what Salvage brings up."""
    found: Counter = Counter()
    for row in registry.fishing.treasure.loot:
        if rng.random() < row.chance:
            found[row.item] += rng.randint(row.min, row.max)
    return found


# ---- the radar --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RadarView:
    level: int
    on: bool
    targets: tuple[str, ...]
    multiplier: float  # 1.0 with no radar
    slots: int
    batteries: int
    unlocked: bool
    next_cost: object = None  # the RadarLevel you could buy next, or None at the top


def radar_chances(water: WaterRules, targets, multiplier: float, registry: Registry, rare_luck: float = 0.0) -> dict[str, float]:
    """The real chance of each target on one cast in `water` with the radar (the rest of the water as it is)."""
    chase = {t: multiplier for t in targets if t in water.fish}
    odds = sorted(water.fish.items(), key=lambda kv: -kv[1])
    chances, left = {}, 1.0
    for index, (fish_id, rate) in enumerate(odds):
        if registry.item(fish_id).rarity >= 4:
            rate = max(1, round(rate / (1 + rare_luck)))
        if fish_id in chase:
            rate = max(1, round(rate / chase[fish_id]))
        p = left if index == len(odds) - 1 else left / rate
        chances[fish_id] = p
        left -= p
    return {t: chances[t] for t in chase}


async def radar(user: User, registry: Registry | None = None) -> RadarView:
    reg = registry or get_registry()
    rules = reg.fishing.radar
    skill = await user.skill("fishing")
    level = max(0, min(skill.radar.level, len(rules.levels)))
    tier = rules.levels[level - 1] if level else None
    batteries = await user.item_quantity(rules.battery)
    unlocked = User.xp_to_level(skill.xp) >= rules.unlock_level
    return RadarView(level, skill.radar.on and level > 0, tuple(skill.radar.targets[: tier.slots if tier else 0]), tier.multiplier if tier else 1.0,
                     tier.slots if tier else 0, batteries, unlocked, rules.levels[level] if level < len(rules.levels) else None)


async def upgrade_radar(user: User, registry: Registry | None = None) -> int:
    """Buy the next radar level (bits and fish, all or nothing). Returns the new level."""
    reg = registry or get_registry()
    view = await radar(user, reg)
    if not view.unlocked:
        raise FishingError(f"The radar opens at fishing level {reg.fishing.radar.unlock_level}.")
    cost = view.next_cost
    if cost is None:
        raise FishingError("Your radar is already the best there is.")
    taken: dict[str, int] = {}
    paid = 0
    try:
        if cost.bits:
            await user.remove_bits(cost.bits)
            paid = cost.bits
        for item_id, quantity in cost.items.items():
            await user.remove_item(item_id, quantity)
            taken[item_id] = quantity
    except (InsufficientFunds, ValueError):
        if paid:
            await user.add_bits(paid)
        for item_id, quantity in taken.items():
            await user.add_item(item_id, quantity)
        raise FishingError("You do not have everything it needs.") from None
    await user.update_skill("fishing", lambda skill: setattr(skill.radar, "level", view.level + 1))
    return view.level + 1


async def set_radar(user: User, *, on: bool | None = None, targets: list[str] | None = None, registry: Registry | None = None) -> None:
    """Switch the radar on or off, and/or choose what it chases (up to your slots; fish that exist and can be caught)."""
    reg = registry or get_registry()
    view = await radar(user, reg)
    if not view.level:
        raise FishingError("You have no radar yet.")
    if targets is not None:
        known = {f for w in reg.fishing.waters for f in w.fish}
        chosen = list(dict.fromkeys(t for t in targets if t in known))[: view.slots]

        def pick(skill) -> None:
            skill.radar.targets = chosen

        await user.update_skill("fishing", pick)
    if on is not None:
        await user.update_skill("fishing", lambda skill: setattr(skill.radar, "on", on))


async def use_radar(user: User, water: WaterRules, registry: Registry | None = None) -> dict[str, float]:
    """Called when you cast: if the radar is on and one of its targets lives in this water, use a battery and return {fish: multiplier}. Otherwise nothing."""
    reg = registry or get_registry()
    view = await radar(user, reg)
    if not (view.on and view.unlocked):
        return {}
    chase = {t: view.multiplier for t in view.targets if t in water.fish}
    if not chase:
        return {}
    try:
        await user.remove_item(reg.fishing.radar.battery, 1)
    except ValueError:
        return {}  # out of batteries: it just does not help
    await user.inc_stat("radar_scans")  # one battery = one scan
    return chase


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
    reveals: tuple[tuple[str, str, str], ...] = ()  # what each ❓ in the reel turned out to be
    extra_fish: int = 0  # more of the same fish that came up with it
    size: float = 0.0
    personal_best: bool = False  # your biggest of this fish so far (including your first one)
    server_record: bool = False  # the biggest ever caught on the server
    record_bits: int = 0
    record_holder: str | None = None  # who held the server record before you
    slack_left: int = 0  # forgiven wrong arrows you did not need
    slack_bits: int = 0  # ...and what they paid
    bycatch: Item | None = None  # a second, different fish the Treasure Hunter's rod brought up
    streak_bits: int = 0  # what the Angler's Hot Streak added (clean reels in a row)


def catch_extras(rng: random.Random, registry: Registry) -> Counter:
    """Materials that come up with a catch (fishing items that aren't fish but have a drop table)."""
    found: Counter = Counter()
    for item in registry.items_for_skill("fishing"):
        if item.category in ("material", "pet_food") and (quantity := roll_drop(item, rng)):
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
    multiplier = await xp_multiplier(user.id, reg, "fishing")
    xp = round((cast.xp or rules.xp_per_catch) * multiplier)  # not the fish's rarity, not the rod: tools never change xp
    await user.add_item(cast.fish.id, 1 + cast.extra_fish)
    bycatch = None
    if cast.bycatch and (rng or random.Random()).random() < cast.bycatch:  # the Treasure Hunter's Bycatch: a second, different fish in the net
        for _ in range(8):
            found = roll_fish(rng or random.Random(), reg, cast.water, 0.0)
            if found.id != cast.fish.id:
                bycatch = found
                break
    if bycatch is not None:
        await user.add_item(bycatch.id, 1)
    extras = catch_extras(rng or random.Random(), reg)
    if cast.water is not None:  # starred materials: the deeper the water (its place in the list), the likelier a better star
        location = next(i for i, w in enumerate(rules.waters) if w.id == cast.water.id) + 1
        extras = stars.apply(extras, stars.progress(location, len(rules.waters)), rng or random.Random(), reg)
    for item_id, quantity in extras.items():
        await user.add_item(item_id, quantity)
    finished: list[Quest] = []
    pet = await pets.bonuses(user, reg)
    seen: list[str] = []
    best: list[bool] = []
    counts_for_community: list[bool] = []
    dice = rng or random.Random()

    mastery_stats = await equipped_stats(user, "fishing", reg)
    salvage_every = int(mastery_stats.stats.get("salvage", 0)) if mastery_stats else 0
    salvaged: list[bool] = []
    before: list[int] = []
    hot_streak = mastery_stats.stats.get("hot_streak", 0.0) if mastery_stats else 0.0

    streak: dict[str, int] = {}  # the clean-reel run before and after this catch (for the longest-run stat)

    def grant(skill) -> None:
        skill.xp += xp
        skill.stats.fish_caught += 1
        streak["before"] = skill.streak
        before.append(min(HOT_STREAK_MAX, skill.streak))  # (the streak this catch rides on)
        skill.streak = skill.streak + 1 if cast.slips_left >= cast.slips_start else 0  # (a clean reel keeps the Hot Streak going; any slip ends it)
        streak["after"] = skill.streak
        if salvage_every and skill.stats.fish_caught % salvage_every == 0:
            salvaged.append(True)
        skill.stats.caught[cast.fish.id] = skill.stats.caught.get(cast.fish.id, 0) + 1 + cast.extra_fish
        if bycatch is not None:
            skill.stats.caught[bycatch.id] = skill.stats.caught.get(bycatch.id, 0) + 1
        _remember(skill, cast)
        if cast.size > 0 and cast.size > skill.records.get(cast.fish.id, 0):
            skill.records[cast.fish.id] = cast.size
            skill.xp += cast.fish.rarity * rules.records.personal_xp_per_rarity
            best.append(True)
        t = rules.treasure
        if skill.treasure.armed_until <= now and dice.randint(1, max(1, round(t.hallucination_odds / (1 + pet.get("treasure_luck", 0.0))))) == 1:
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
    if streak:  # the longest clean-reel run ever; a player from before this stat starts from the run they were on
        await user.stat_best("longest_fishing_streak", streak["after"], seed=streak["before"])
    if salvaged:  # Salvage: every Nth fish also brings up a chest's loot
        haul = salvage_loot(rng or random.Random(), reg)
        for item_id, quantity in haul.items():
            await user.add_item(item_id, quantity)
        extras = extras + haul
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
    slack_bits = slack_bonus(cast.fish.sell_price * (1 + cast.extra_fish), cast.slips_left, rules)
    streak_bits = round(cast.fish.sell_price * (1 + cast.extra_fish) * hot_streak * before[0]) if hot_streak and before else 0  # Hot Streak: clean reels in a row pay more
    if slack_bits + streak_bits:
        await user.add_bits(slack_bits + streak_bits)
    return Catch(cast.fish, xp, tuple(finished), quest_bits, extras, seen[0] if seen else None,
                 tuple(cast.reveals), cast.extra_fish, cast.size, bool(best), server_record, record_bits, holder, cast.slips_left, slack_bits, bycatch, streak_bits)


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
    multiplier = await xp_multiplier(user.id, reg, "fishing")
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
    multiplier = await xp_multiplier(user.id, reg, "fishing")
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

    multiplier = await xp_multiplier(user.id, reg, "fishing")

    def try_lock(skill) -> None:
        code = skill.treasure.code
        if code and attempt == code:
            skill.treasure = TreasureState()  # the numbers are used up
            skill.stats.treasures_found += 1
            _, needed = User.xp_for_next_level(skill.xp)  # what finishing your current level takes
            outcome["xp"] = round(max(t.xp, needed * t.xp_level_fraction) * multiplier)
            skill.xp += outcome["xp"]
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
        return ChestAttempt(True, cast.attempts_left, bits=bits, xp=outcome["xp"], items=items)
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
    slack_left: int = 0
    slack_bits: int = 0


def roll_boss_reward(registry: Registry, rng: random.Random) -> tuple[int, Counter]:
    """A boss's bits and loot (the xp is a fixed amount, paid with the player's bonuses)."""
    b = registry.fishing.boss
    bits = rng.randint(b.bits_min, b.bits_max)
    items: Counter = Counter()
    for row in b.loot:
        if rng.random() < row.chance:
            items[row.item] += rng.randint(row.min, row.max)
    return bits, items


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
    bits, items = roll_boss_reward(reg, rng)
    rod = await equipped_stats(user, "fishing", reg)
    if rod and rod.stats.get("chum", 0.0) > 0:  # Chum Slick: the boss pays again
        more_bits, more_items = roll_boss_reward(reg, rng)
        bits, items = bits + round(more_bits * rod.stats["chum"]), items + Counter({i: round(q * rod.stats["chum"]) for i, q in more_items.items()})
    xp = round(b.xp * await xp_multiplier(user.id, reg, "fishing"))

    def win(skill) -> None:
        skill.xp += xp
        skill.stats.bosses_beaten += 1
        skill.stats.bosses[cast.boss] = skill.stats.bosses.get(cast.boss, 0) + 1

    await user.update_skill("fishing", win)
    for item_id, quantity in items.items():
        await user.add_item(item_id, quantity)
    slack_bits = slack_bonus(bits, cast.slips_left, reg.fishing)
    if bits + slack_bits:
        await user.add_bits(bits + slack_bits)
    return BossReward(cast.boss, bits, xp, items, cast.slips_left, slack_bits)
