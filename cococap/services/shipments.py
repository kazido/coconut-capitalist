"""Shipments: fill a crate with materials from several skills and ship it for xp and bits.

* **Personal shipments.** You always have a few (two themed on one skill's materials, one mixed from different skills). Which materials and how many comes from
  a seed (you, and how many you have shipped), so nobody rerolls by looking again. "Fill" moves what you hold toward the crate (the items leave your pack and stay
  in it); once every material is in, "Ship" pays xp and bits and gives you a new crate. A crate never expires, so nothing you put in is lost.
* **The community shipment.** One a week, much bigger, that the whole server fills together. Whoever gave at least a small share is paid when it is finished, once:
  bits worth more than what they gave, and xp.

Money and materials change in one step or not at all. Everything random comes from a seeded generator.
"""

import datetime
import random
import time
from collections import Counter
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.registry import Item, Registry, get_registry
from cococap.services import community
from cococap.services.party import xp_multiplier
from cococap.user import User

SKILLS = ("mining", "farming", "foraging", "fishing")
MAX_QUANTITY = 150  # the most of any one material a personal shipment asks for (a community one asks for more)
COMMUNITY_MAX_QUANTITY = 3000


class ShipmentError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


# ---- what can be asked for ---------------------------------------------------------------------------------------------
def pool(skill: str, level: int, registry: Registry, budget: int, cheapest: int = 0) -> list[Item]:
    """The materials of `skill` a shipment may ask for at this level: sellable finds and crops, nothing rarer than the level allows, nothing so dear that
    one is more than `budget` bits, and nothing so cheap that you would be asked for a thousand (`cheapest`)."""
    cap = 5 + registry.shipments.personal.rate_per_level * level
    consumables = {w.item for w in registry.foraging.rotate.wedges}  # (wedges are for using, not for shipping)
    items = []
    for item in registry.items.values():
        if item.skill != skill or item.sell_price <= 0 or item.is_instance or item.id in consumables or not cheapest <= item.sell_price <= budget:
            continue
        if item.category == "crop" or (item.drop is not None and item.category in ("material", "fish") and item.drop.rate <= cap):
            items.append(item)
    return sorted(items, key=lambda i: i.id)


@dataclass(frozen=True)
class Shipment:
    theme: str  # a skill, or "mixed"
    need: dict[str, int]
    have: dict[str, int] = field(default_factory=dict)

    def done(self) -> bool:
        return all(self.have.get(i, 0) >= q for i, q in self.need.items())


def worth(need: dict[str, int], registry: Registry) -> int:
    return sum(registry.item(i).sell_price * q for i, q in need.items())


def make_shipment(rng: random.Random, theme: str, levels: dict[str, int], registry: Registry | None = None) -> Shipment:
    """A new crate: `kinds` different materials, worth about the same in total whatever they are."""
    reg = registry or get_registry()
    p = reg.shipments.personal
    basis = levels[theme] if theme in levels else round(sum(levels.values()) / len(levels))
    total = p.value_base + p.value_per_level * basis
    per_kind = total / p.kinds
    others = [s for s in SKILLS if s != theme]
    if theme == "mixed":
        skills = [SKILLS[i] for i in rng.sample(range(len(SKILLS)), min(p.kinds, len(SKILLS)))]
        skills += [rng.choice(SKILLS) for _ in range(p.kinds - len(skills))]
    else:
        skills = [theme] * p.theme_kinds + [rng.choice(others) for _ in range(p.kinds - p.theme_kinds)]
    need: dict[str, int] = {}
    for skill in skills:
        options = [i for i in pool(skill, levels.get(skill, basis), reg, round(per_kind * 3), round(per_kind / MAX_QUANTITY)) if i.id not in need]
        if not options:  # (a low level with little to choose from: allow cheaper things first, and only then rarer ones, rather than ask for nothing)
            options = [i for i in pool(skill, levels.get(skill, basis), reg, round(per_kind * 3)) if i.id not in need]
        if not options:
            options = [i for i in pool(skill, 100, reg, round(per_kind * 3)) if i.id not in need]
        item = rng.choice(options)
        need[item.id] = max(1, round(per_kind / item.sell_price))
    return Shipment(theme, need)


def reward(ship: Shipment, registry: Registry) -> tuple[int, dict[str, int]]:
    """(bits, xp by skill) for shipping this crate."""
    p = registry.shipments.personal
    value = worth(ship.need, registry)
    by_skill: Counter = Counter()
    for item_id, qty in ship.need.items():
        item = registry.item(item_id)
        by_skill[item.skill] += item.sell_price * qty
    xp = {skill: round(v * p.xp_per_bit) for skill, v in by_skill.items()}
    return round(value * p.bits_factor), xp


# ---- your shipments (kept in the community store under your id: no migration) ------------------------------------------
def _key(user_id: int) -> str:
    return f"shipments:{user_id}"


DEFAULT = {"made": 0, "slots": []}
THEMES = ("themed", "themed", "mixed")


async def _levels(user: User) -> dict[str, int]:
    return {skill: User.xp_to_level((await user.skill(skill)).xp) for skill in SKILLS}


def _theme_for(slot: int, user_id: int, serial: int) -> str:
    """Slot 0 and 1 are themed (two different skills), the last is mixed."""
    if slot >= 2 or slot >= len(THEMES) or THEMES[slot] == "mixed":
        return "mixed"
    rng = random.Random(f"theme:{user_id}:{serial // 3}")
    first, second = rng.sample(SKILLS, 2)
    return first if slot == 0 else second


def _fill_slots(data: dict, user_id: int, levels: dict[str, int], reg: Registry) -> None:
    slots = reg.shipments.personal.slots
    while len(data["slots"]) < slots:
        index = len(data["slots"])
        data["made"] += 1
        theme = _theme_for(index, user_id, data["made"])
        ship = make_shipment(random.Random(f"shipment:{user_id}:{data['made']}"), theme, levels, reg)
        data["slots"].append({"theme": theme, "need": ship.need, "have": {}})


def _view(data: dict) -> list[Shipment]:
    return [Shipment(s["theme"], dict(s["need"]), dict(s["have"])) for s in data["slots"]]


async def mine(user: User, registry: Registry | None = None) -> list[Shipment]:
    """Your shipments (the first look makes them)."""
    reg = registry or get_registry()
    levels = await _levels(user)

    def look(data: dict) -> list[Shipment]:
        _fill_slots(data, user.id, levels, reg)
        return _view(data)

    return await community.update(_key(user.id), DEFAULT, look)


async def fill(user: User, index: int, registry: Registry | None = None) -> dict[str, int]:
    """Put what you hold toward a crate. Returns what went in (the items leave your pack, atomically with the crate)."""
    reg = registry or get_registry()
    await mine(user, reg)
    owned = await user.items()
    moved: dict[str, int] = {}

    def put(data: dict) -> None:
        if not 0 <= index < len(data["slots"]):
            raise ShipmentError("There is no such shipment.")
        slot = data["slots"][index]
        for item_id, need in slot["need"].items():
            take = min(owned.get(item_id, 0), need - slot["have"].get(item_id, 0))
            if take > 0:
                moved[item_id] = take
        if not moved:
            raise ShipmentError("You have nothing it still needs.")
        for item_id, qty in moved.items():
            slot["have"][item_id] = slot["have"].get(item_id, 0) + qty

    await community.update(_key(user.id), DEFAULT, put)
    taken: dict[str, int] = {}
    try:
        for item_id, qty in moved.items():
            await user.remove_item(item_id, qty)
            taken[item_id] = qty
    except ValueError:
        for item_id, qty in taken.items():  # the pack changed under us: put back what was taken, and take the crate's share out again
            await user.add_item(item_id, qty)

        def undo(data: dict) -> None:
            for item_id, qty in moved.items():
                data["slots"][index]["have"][item_id] = max(0, data["slots"][index]["have"].get(item_id, 0) - qty)

        await community.update(_key(user.id), DEFAULT, undo)
        raise ShipmentError("Your pack changed; try again.") from None
    return moved


@dataclass(frozen=True)
class Shipped:
    theme: str
    bits: int
    xp: dict[str, int]


async def ship(user: User, index: int, registry: Registry | None = None) -> Shipped:
    """Ship a full crate: bits and xp, and a new crate in its place. Once only."""
    reg = registry or get_registry()
    levels = await _levels(user)
    outcome: dict = {}

    def send(data: dict) -> None:
        if not 0 <= index < len(data["slots"]):
            raise ShipmentError("There is no such shipment.")
        slot = data["slots"][index]
        crate = Shipment(slot["theme"], dict(slot["need"]), dict(slot["have"]))
        if not crate.done():
            raise ShipmentError("It is not full yet.")
        outcome["crate"] = crate
        # (the new crate takes the old one's place, so the themed ones stay first and the mixed one last)
        data["made"] += 1
        theme = _theme_for(index, user.id, data["made"])
        fresh = make_shipment(random.Random(f"shipment:{user.id}:{data['made']}"), theme, levels, reg)
        data["slots"][index] = {"theme": theme, "need": fresh.need, "have": {}}

    await community.update(_key(user.id), DEFAULT, send)
    crate = outcome["crate"]
    bits, xp = reward(crate, reg)
    await user.add_bits(bits)
    paid: dict[str, int] = {}
    for skill, amount in xp.items():
        amount = round(amount * await xp_multiplier(user.id, reg, skill))
        if amount:
            await user.add_xp(skill, amount)
        paid[skill] = amount
    await user.inc_stat("shipments_shipped")
    return Shipped(crate.theme, bits, paid)


# ---- the community shipment ------------------------------------------------------------------------------------------
COMMUNITY_KEY = "shipment_community"
COMMUNITY_DEFAULT = {"week": -1, "need": {}, "have": {}, "given": {}, "gave": {}, "done": False, "pending": {}}
WEEK = 7 * 86400


def week_of(now: float) -> int:
    """Weeks since a Monday (UTC)."""
    return int((now // 86400 + 3) // 7)  # day 0 (1970-01-01) was a Thursday


def make_community(week: int, registry: Registry) -> dict[str, int]:
    c = registry.shipments.community
    rng = random.Random(f"community-shipment:{week}")
    need: dict[str, int] = {}
    per_kind = c.value / c.kinds
    for n in range(c.kinds):
        skill = SKILLS[n % len(SKILLS)]
        options = [i for i in pool(skill, 100, registry, round(per_kind * 3), round(per_kind / COMMUNITY_MAX_QUANTITY)) if i.id not in need]
        item = rng.choice(options)
        need[item.id] = max(1, round(per_kind / item.sell_price))
    return need


@dataclass(frozen=True)
class CommunityView:
    week: int
    need: dict[str, int]
    have: dict[str, int]
    done: bool
    yours: int  # the worth of what you have given
    closes_at: float

    @property
    def fraction(self) -> float:
        total = sum(self.need.values())
        return sum(min(self.have.get(i, 0), q) for i, q in self.need.items()) / total if total else 0.0


def _roll(data: dict, now: float, reg: Registry) -> None:
    week = week_of(now)
    if data["week"] != week:
        pending = data["pending"]
        data.clear()
        data.update({**COMMUNITY_DEFAULT, "pending": pending, "week": week, "need": make_community(week, reg)})


def _community_view(data: dict, user_id: int, now: float) -> CommunityView:
    return CommunityView(data["week"], dict(data["need"]), dict(data["have"]), data["done"], data["given"].get(str(user_id), 0), (week_of(now) + 1) * WEEK - 3 * 86400)


async def community_now(user: User, now: float | None = None, registry: Registry | None = None) -> CommunityView:
    reg = registry or get_registry()
    now = time.time() if now is None else now

    def look(data: dict) -> CommunityView:
        _roll(data, now, reg)
        return _community_view(data, user.id, now)

    return await community.update(COMMUNITY_KEY, COMMUNITY_DEFAULT, look)


async def donate(user: User, now: float | None = None, registry: Registry | None = None) -> dict[str, int]:
    """Give the community shipment everything you hold that it still needs. When that fills it, everyone who gave enough is owed a payout (collected on their next look)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    c = reg.shipments.community
    owned = await user.items()
    gave: dict[str, int] = {}

    def give(data: dict) -> None:
        _roll(data, now, reg)
        if data["done"]:
            raise ShipmentError("This week's shipment is already full. A new one starts on Monday.")
        for item_id, need in data["need"].items():
            take = min(owned.get(item_id, 0), need - data["have"].get(item_id, 0))
            if take > 0:
                gave[item_id] = take
        if not gave:
            raise ShipmentError("You have nothing it still needs.")
        value = 0
        for item_id, qty in gave.items():
            data["have"][item_id] = data["have"].get(item_id, 0) + qty
            value += reg.item(item_id).sell_price * qty
            skill = reg.item(item_id).skill
            data["gave"].setdefault(str(user.id), {})[skill] = data["gave"].get(str(user.id), {}).get(skill, 0) + reg.item(item_id).sell_price * qty
        data["given"][str(user.id)] = data["given"].get(str(user.id), 0) + value
        if all(data["have"].get(i, 0) >= q for i, q in data["need"].items()):
            data["done"] = True
            total = sum(data["given"].values())
            for uid, amount in data["given"].items():
                if total and amount / total >= c.min_share:
                    top = max(data["gave"][uid].items(), key=lambda kv: kv[1])[0]
                    data["pending"].setdefault(uid, []).append({"bits": round(amount * c.bits_factor), "xp": c.xp, "skill": top, "week": data["week"]})

    await community.update(COMMUNITY_KEY, COMMUNITY_DEFAULT, give)
    for item_id, qty in gave.items():
        await user.remove_item(item_id, qty)
    return gave


@dataclass(frozen=True)
class CommunityPayout:
    bits: int
    xp: int
    skill: str


async def claim_community(user: User, now: float | None = None, registry: Registry | None = None) -> list[CommunityPayout]:
    """Collect what a finished community shipment owes you (once each)."""
    reg = registry or get_registry()

    def take(data: dict) -> list[dict]:
        return data["pending"].pop(str(user.id), [])

    owed = await community.update(COMMUNITY_KEY, COMMUNITY_DEFAULT, take)
    paid = []
    for entry in owed:
        xp = round(entry["xp"] * await xp_multiplier(user.id, reg, entry["skill"]))
        await user.add_bits(entry["bits"])
        await user.add_xp(entry["skill"], xp)
        paid.append(CommunityPayout(entry["bits"], xp, entry["skill"]))
    return paid
