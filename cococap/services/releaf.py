"""The Releaf Foundation: ONE meter for the whole server, and a temporary server-wide Bloom when it fills.

Players give rare foraging drops (rarity `min_rarity` or more; the item is gone, a real loss) and each one adds points to the shared meter. At the goal a
**Bloom** starts for `bloom_hours`: everybody's foraging xp and every drop chance of every tree (private, community, party) get a bonus, whether they gave or
not. Then the meter empties and giving reopens. Giving is CLOSED while the meter is full / a Bloom is running, so nothing is ever wasted, and one player can
give at most `max_share` of the goal per cycle, so it takes several people. There is no personal reward (only a donor list), so it is never a must-do.

The shared state is one JSON document (`services/community.py`, key "releaf"), changed in one serialized transaction, so two people giving at the same moment
can never start two Blooms or overfill the meter.
"""

import math
import time
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import ReleafRules
from cococap.services import community
from cococap.user import User

KEY = "releaf"
HOUR = 3600
KEEP_BLOOMS = 6  # past Bloom windows kept, so a community tree that finished during one can still be paid with it
DEFAULT: dict = {"meter": 0, "given": {}, "lifetime": {}, "bloom_started": 0.0, "bloom_until": 0.0, "blooms": [], "cycles": 0}


class ReleafError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def _tick(data: dict, now: float, rules: ReleafRules) -> None:
    """Close a Bloom that has run out: the meter empties and this cycle's tallies reset (lifetime tallies stay)."""
    if data["meter"] >= rules.meter_goal and now >= data["bloom_until"]:
        data["meter"] = 0
        data["given"] = {}
        data["cycles"] += 1


def can_give(item, rules: ReleafRules) -> bool:
    """Foraging materials and the like of a high enough rarity (tools and key items are never given)."""
    return item.skill == "foraging" and item.category not in ("tool", "key_item") and rules.worth(item.rarity) > 0


def points_of(item_id: str, registry: Registry) -> int:
    item = registry.item(item_id)
    return registry.foraging.releaf.worth(item.rarity) if can_give(item, registry.foraging.releaf) else 0


def cap_points(rules: ReleafRules) -> int:
    """The most points one player can give in one cycle."""
    return max(1, math.floor(rules.meter_goal * rules.max_share))


def max_items(points: int, meter: int, yours: int, rules: ReleafRules) -> int:
    """How many items worth `points` each can still be given: the last one may top the meter off (the surplus is simply not counted),
    but your own cap is strict."""
    if points <= 0 or meter >= rules.meter_goal:
        return 0
    to_fill = math.ceil((rules.meter_goal - meter) / points)
    under_cap = (cap_points(rules) - yours) // points
    return max(0, min(to_fill, under_cap))


@dataclass(frozen=True)
class Donor:
    user_id: int
    name: str
    points: int


@dataclass(frozen=True)
class Foundation:
    """The shared state as of `now`."""

    meter: int
    goal: int
    bloom_started: float
    bloom_until: float
    bloom_active: bool
    cycles: int  # Blooms completed before this one
    top: list[Donor] = field(default_factory=list)  # this cycle's biggest givers
    givers: int = 0  # how many people gave this cycle

    @property
    def full(self) -> bool:
        return self.meter >= self.goal

    @property
    def open(self) -> bool:
        """Giving is open (the meter has room and no Bloom is running)."""
        return not self.full and not self.bloom_active


async def _names(ranked: list[tuple[str, int]]) -> list[Donor]:
    out = []
    for uid, points in ranked:
        found = await User.find(int(uid))
        out.append(Donor(int(uid), found.name if found is not None else "someone", points))
    return out


async def foundation(now: float | None = None, registry: Registry | None = None) -> Foundation:
    reg = registry or get_registry()
    rules = reg.foraging.releaf
    now = time.time() if now is None else now
    data = await community.read(KEY, DEFAULT)
    _tick(data, now, rules)
    ranked = sorted(((u, p) for u, p in data["given"].items() if p > 0), key=lambda kv: (-kv[1], kv[0]))
    return Foundation(data["meter"], rules.meter_goal, data["bloom_started"], data["bloom_until"],
                      now < data["bloom_until"] and data["meter"] >= rules.meter_goal, data["cycles"],
                      await _names(ranked[:rules.top_donors]), len(ranked))


@dataclass(frozen=True)
class Status:
    unlocked: bool
    foundation: Foundation
    yours: int  # points you gave this cycle
    lifetime: int  # points you have given in all
    cap: int  # the most you can give in a cycle
    donations: int  # how many times you have given


async def status(user: User, now: float | None = None, registry: Registry | None = None) -> Status:
    reg = registry or get_registry()
    rules = reg.foraging.releaf
    now = time.time() if now is None else now
    skill = await user.skill("foraging")
    data = await community.read(KEY, DEFAULT)
    _tick(data, now, rules)
    return Status(User.xp_to_level(skill.xp) >= rules.min_level, await foundation(now, reg), data["given"].get(str(user.id), 0),
                  data["lifetime"].get(str(user.id), 0), cap_points(rules), skill.stats.releaf_donations)


async def donatable(user: User, registry: Registry | None = None) -> dict[str, int]:
    """What you own that the Foundation accepts: item id -> how many you have (the rarest first is up to the screen)."""
    reg = registry or get_registry()
    rules = reg.foraging.releaf
    return {i: q for i, q in (await user.items()).items() if q > 0 and can_give(reg.item(i), rules)}


@dataclass(frozen=True)
class Donation:
    item_id: str
    given: int  # how many items went in
    returned: int  # how many you asked for that did not fit and are back in your inventory
    points: int  # points that counted
    meter: int
    goal: int
    bloom_started: bool  # this gift filled the meter


async def donate(user: User, item_id: str, quantity: int, now: float | None = None, registry: Registry | None = None) -> Donation:
    """Give `quantity` of an item. They are taken from you first; whatever the meter or your cap cannot take goes straight back."""
    reg = registry or get_registry()
    rules = reg.foraging.releaf
    now = time.time() if now is None else now
    item = reg.item(item_id)
    points = points_of(item_id, reg)
    if quantity < 1:
        raise ReleafError("Pick how many to give.")
    if points <= 0:
        raise ReleafError(f"The Foundation only takes foraging items of rarity {rules.min_rarity} or more ({item.name} is not one).")
    if User.xp_to_level((await user.skill("foraging")).xp) < rules.min_level:
        raise ReleafError(f"The Releaf Foundation opens at foraging level {rules.min_level}.")
    try:
        await user.remove_item(item_id, quantity)
    except ValueError:
        raise ReleafError(f"You don't have {quantity:,} {item.name}.") from None
    uid = str(user.id)
    outcome: dict = {}

    def give(data: dict) -> None:
        _tick(data, now, rules)
        if data["meter"] >= rules.meter_goal:
            outcome["reason"] = "closed"
            return
        yours = data["given"].get(uid, 0)
        n = min(quantity, max_items(points, data["meter"], yours, rules))
        if n <= 0:
            outcome["reason"] = "cap"
            return
        counted = min(points * n, rules.meter_goal - data["meter"])
        data["meter"] += counted
        data["given"][uid] = yours + counted
        data["lifetime"][uid] = data["lifetime"].get(uid, 0) + counted
        outcome.update(n=n, counted=counted, meter=data["meter"])
        if data["meter"] >= rules.meter_goal:  # the goal: ONE Bloom starts (the update is serialized, so a second giver finds the meter full)
            data["bloom_started"], data["bloom_until"] = now, now + rules.bloom_hours * HOUR
            data["blooms"] = (data["blooms"] + [[now, data["bloom_until"]]])[-KEEP_BLOOMS:]
            outcome["bloom"] = True

    try:
        await community.update(KEY, DEFAULT, give)
    except BaseException:
        await user.add_item(item_id, quantity)
        raise
    given = outcome.get("n", 0)
    if given < quantity:
        await user.add_item(item_id, quantity - given)  # (what did not fit comes back)
    if not given:
        if outcome["reason"] == "closed":
            raise ReleafError("The Foundation is closed while the meter is full and a Bloom is running. Your items are back with you.")
        raise ReleafError(f"You have given as much as one person can this cycle ({cap_points(rules)} points). Your items are back with you.")

    def count(skill) -> None:
        skill.stats.releaf_donations += 1

    await user.update_skill("foraging", count)
    return Donation(item_id, given, quantity - given, outcome["counted"], outcome["meter"], rules.meter_goal, bool(outcome.get("bloom")))


# ---- the Bloom's bonuses ---------------------------------------------------------------------------------------
async def windows() -> list[list[float]]:
    """The recent Bloom windows, [start, end] each (the newest last)."""
    return (await community.read(KEY, DEFAULT))["blooms"]


async def active(now: float | None = None) -> bool:
    now = time.time() if now is None else now
    return any(a <= now < b for a, b in await windows())


async def xp_bonus(registry: Registry | None = None, now: float | None = None) -> float:
    """+this on every foraging xp reward right now (0 outside a Bloom)."""
    reg = registry or get_registry()
    return reg.foraging.releaf.bloom_xp if await active(now) else 0.0


async def drop_boost(registry: Registry | None = None, now: float | None = None) -> float:
    """+this on every drop chance of a foraging tree right now (0 outside a Bloom)."""
    reg = registry or get_registry()
    return reg.foraging.releaf.bloom_drops if await active(now) else 0.0


def boost_between(blooms: list[list[float]], start: float, end: float, rules: ReleafRules) -> float:
    """The drop boost for something that ran from `start` to `end` (a community tree's hour): on if a Bloom was up at any time in it."""
    return rules.bloom_drops if any(a < end and b > start for a, b in blooms) else 0.0
