"""Fishing rules: cast, wait for a bite, reel the fish in.

A **cast** is a plain object held by the screen (like a mining run or a private tree). Everything about it is decided
when the line goes in (which fish, when it bites, which arrows to press), so reopening the panel can't re-roll it.
Time is passed in, not read, so tests can move the clock. Nothing is paid until the fish is landed, once.

All randomness comes from an injected ``random.Random``.
"""

import random
import time
from collections import Counter
from dataclasses import dataclass, field

from cococap.constants import Rarities
from cococap.errors import GameRuleError
from cococap.registry import Item, Registry, get_registry
from cococap.registry.models import FishingRules, QuestTemplate
from cococap.services import shop
from cococap.services.equipment import EffectiveStats, equipped_stats
from cococap.services.loot import roll_table
from cococap.services.party import xp_multiplier
from cococap.user import User

LEFT, RIGHT = "◀", "▶"


class FishingError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


# ---- the fish ---------------------------------------------------------------------------------------------
def fish_pool(registry: Registry) -> list[Item]:
    """Every fish that can bite, rarest first (so the first that "drops" wins and the common catch-all is last)."""
    fish = [i for i in registry.items.values() if i.skill == "fishing" and i.category == "material" and i.drop]
    return sorted(fish, key=lambda i: (-i.drop.rate, -i.rarity, i.id))


def roll_fish(rng: random.Random, registry: Registry | None = None) -> Item:
    reg = registry or get_registry()
    found = roll_table([i.id for i in fish_pool(reg)], reg, rng)
    return reg.item(found[0]) if found else fish_pool(reg)[-1]


# ---- the rod ----------------------------------------------------------------------------------------------
def wait_seconds(power: int, rules: FishingRules, rng: random.Random) -> float:
    """How long until something bites: shorter with a stronger rod, never below the floor."""
    base = rng.uniform(rules.bite.wait_min, rules.bite.wait_max)
    factor = max(rules.bite.min_wait_factor, 1 / (1 + rules.bite.speedup_per_power * max(0, power - 1)))
    return base * factor


def slips_allowed(power: int, rules: FishingRules) -> int:
    """Wrong arrows a rod forgives per fish."""
    return max(0, power) // rules.reel.power_per_slip


def reel_pattern(rarity: int, rules: FishingRules, rng: random.Random) -> list[str]:
    return [rng.choice((LEFT, RIGHT)) for _ in range(rules.reel.base_length + rarity)]


# ---- a cast -----------------------------------------------------------------------------------------------
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

    def status(self, now: float) -> str:
        """waiting | bite | reeling | landed | escaped.  ("bite" = it's on, pull up the line!)"""
        if self.escaped:
            return "escaped"
        if self.progress >= len(self.pattern):
            return "landed"
        if self.hooked:
            return "reeling"
        if now < self.bite_at:
            return "waiting"
        if now > self.expires_at:
            self.escaped = True  # nobody pulled up the line in time
            return "escaped"
        return "bite"

    @property
    def next_arrow(self) -> str | None:
        return self.pattern[self.progress] if self.progress < len(self.pattern) else None

    def hook(self, now: float) -> None:
        """Pull up the line when it bites. Reeling can't start before this, so the game never starts by itself."""
        status = self.status(now)
        if status == "waiting":
            raise FishingError("Nothing is biting yet.")
        if status == "escaped":
            raise FishingError("The fish got away.")
        if status == "bite":
            self.hooked = True

    def press(self, arrow: str, now: float) -> str:
        """Press an arrow. Returns ``ok | slip | landed | escaped``."""
        status = self.status(now)
        if status in ("waiting", "bite"):
            raise FishingError("Nothing is biting yet." if status == "waiting" else "Pull up the line first!")
        if status == "escaped":
            raise FishingError("That fish is already gone.")
        if status == "landed":
            raise FishingError("You already landed that one.")
        if arrow == self.next_arrow:
            self.progress += 1
            return "landed" if self.progress >= len(self.pattern) else "ok"
        if self.slips_left > 0:
            self.slips_left -= 1
            return "slip"
        self.escaped = True
        return "escaped"


def cast_line(stats: EffectiveStats, rng: random.Random, now: float | None = None, registry: Registry | None = None) -> Cast:
    """Put the line in the water: pick the fish, the bite time and the arrows."""
    reg = registry or get_registry()
    rules = reg.fishing
    now = time.time() if now is None else now
    fish = roll_fish(rng, reg)
    bite_at = now + wait_seconds(stats.power, rules, rng)
    return Cast(
        fish=fish,
        bite_at=bite_at,
        expires_at=bite_at + rules.bite.window,
        pattern=reel_pattern(fish.rarity, rules, rng),
        slips_left=slips_allowed(stats.power, rules),
    )


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
    kind: str  # daily | weekly
    index: int
    template: QuestTemplate
    progress: int = 0
    done: bool = False

    @property
    def text(self) -> str:
        t = self.template
        what = "fish" if t.min_rarity == 1 else f"{Rarities.from_value(t.min_rarity).rarity_name} or better fish"
        return f"Catch {t.count} {what}"


def _chosen(kind: str, user_id: int, period: int, rules: FishingRules) -> list[QuestTemplate]:
    rng = random.Random(f"fishing-quests:{kind}:{user_id}:{period}")
    if kind == "daily":
        return rng.sample(rules.quests.daily, rules.quests.daily_count)
    return [rng.choice(rules.quests.weekly)]


def _period(kind: str, now: float) -> int:
    return day_of(now) if kind == "daily" else week_of(now)


def quests_unlocked(level: int, rules: FishingRules) -> bool:
    return level >= rules.quests.min_level


def _quests_of(kind: str, user_id: int, saved, now: float, rules: FishingRules) -> list[Quest]:
    period = _period(kind, now)
    templates = _chosen(kind, user_id, period, rules)
    same = saved.period == period and len(saved.progress) == len(templates)
    return [
        Quest(kind, i, t, saved.progress[i] if same else 0, saved.done[i] if same else False)
        for i, t in enumerate(templates)
    ]


async def quests(user: User, now: float | None = None, registry: Registry | None = None) -> list[Quest]:
    """This player's quests right now (empty until fishing level 3). Daily ones first."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    skill = await user.skill("fishing")
    if not quests_unlocked(User.xp_to_level(skill.xp), reg.fishing):
        return []
    return _quests_of("daily", user.id, skill.daily, now, reg.fishing) + _quests_of("weekly", user.id, skill.weekly, now, reg.fishing)


@dataclass(frozen=True)
class Catch:
    fish: Item
    xp: int
    finished: tuple[Quest, ...] = ()  # quests this catch completed (already paid)
    quest_bits: int = 0


async def land(user: User, cast: Cast, registry: Registry | None = None, now: float | None = None) -> Catch:
    """Keep a fish that has been fully reeled in: item, xp, stats and quest progress. Pays once per cast."""
    reg = registry or get_registry()
    rules = reg.fishing
    now = time.time() if now is None else now
    if cast.progress < len(cast.pattern) or cast.escaped:
        raise FishingError("That fish isn't landed.")
    if cast.settled:
        raise FishingError("You already took that fish.")
    cast.settled = True
    multiplier = await xp_multiplier(user.id, reg)
    xp = round(cast.fish.rarity * rules.xp_per_rarity * multiplier)
    await user.add_item(cast.fish.id, 1)
    finished: list[Quest] = []

    def grant(skill) -> None:
        skill.xp += xp
        skill.stats.fish_caught += 1
        if not quests_unlocked(User.xp_to_level(skill.xp - xp), rules):  # unlocked before this catch, not by it
            return
        for kind in ("daily", "weekly"):
            saved = getattr(skill, kind)
            current = _quests_of(kind, user.id, saved, now, rules)
            progress = [q.progress for q in current]
            done = [q.done for q in current]
            for q in current:
                if not q.done and cast.fish.rarity >= q.template.min_rarity:
                    progress[q.index] += 1
                    if progress[q.index] >= q.template.count:
                        done[q.index] = True
                        finished.append(Quest(kind, q.index, q.template, progress[q.index], True))
            setattr(skill, kind, saved.__class__(period=_period(kind, now), progress=progress, done=done))
        skill.xp += round(sum(q.template.xp for q in finished) * multiplier)
        skill.stats.quests_completed += len(finished)

    await user.update_skill("fishing", grant)
    quest_bits = sum(q.template.bits for q in finished)
    if quest_bits:
        await user.add_bits(quest_bits)
    return Catch(cast.fish, xp, tuple(finished), quest_bits)


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
