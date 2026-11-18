"""Shipments: fill a crate with materials from several skills and ship it for xp and bits.

* **Personal shipments.** A basic crate per skill (unlocks at that skill's level 10) and a harder one later, each mostly that skill's materials with a few from others. Which materials and how many comes from
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
from cococap.services import activity, community, pets
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
    theme: str  # the skill whose materials it mostly asks for
    need: dict[str, int]
    have: dict[str, int] = field(default_factory=dict)
    tier: str = "basic"  # "basic" or "hard"

    @property
    def id(self) -> str:
        return f"{self.theme}:{self.tier}"

    def done(self) -> bool:
        return all(self.have.get(i, 0) >= q for i, q in self.need.items())


def worth(need: dict[str, int], registry: Registry) -> int:
    return sum(registry.item(i).sell_price * q for i, q in need.items())


def slot_ids(registry: Registry) -> list[tuple[str, str]]:
    """Every (skill, tier) a player can eventually have a crate for, in page order."""
    return [(skill, tier) for skill in SKILLS for tier in registry.shipments.personal.tiers]


def unlock_level(tier: str, registry: Registry) -> int:
    return registry.shipments.personal.tiers[tier].unlock_level


def make_shipment(rng: random.Random, theme: str, levels: dict[str, int], registry: Registry | None = None, tier: str = "basic") -> Shipment:
    """A new crate for one skill at one tier: `kinds` different materials (mostly the skill's own), worth about the same in total whatever they are.
    The value grows with that skill's level, so a player at the unlock level can finish it."""
    reg = registry or get_registry()
    p = reg.shipments.personal
    t = p.tiers[tier]
    total = t.value_base + t.value_per_level * levels[theme]
    foreign_kinds = t.kinds - t.theme_kinds
    # The home skill is the bulk: its kinds share (1 - foreign_share) of the value, the other skills' kinds only a small, varied slice.
    home_value = total * (1 - p.foreign_share) / t.theme_kinds
    foreign_value = total * p.foreign_share / foreign_kinds
    others = [s for s in SKILLS if s != theme]
    need: dict[str, int] = {}

    def add(skill: str, per_kind: float, cheapest: int, most: int = 10**9) -> None:
        level = levels.get(skill, 1)
        options = [i for i in pool(skill, level, reg, round(per_kind * 3), cheapest) if i.id not in need]
        if not options:  # (a low level with little to choose from: allow cheaper things first, and only then rarer ones, rather than ask for nothing)
            options = [i for i in pool(skill, level, reg, round(per_kind * 3)) if i.id not in need]
        if not options:
            options = [i for i in pool(skill, 100, reg, round(per_kind * 3)) if i.id not in need]
        item = rng.choice(options)
        need[item.id] = min(most, max(1, round(per_kind / item.sell_price)))  # (a cap, so even the cheapest fallback is never a pile)

    for _ in range(t.theme_kinds):
        add(theme, home_value, round(home_value / MAX_QUANTITY))
    for skill in rng.sample(others, min(foreign_kinds, len(others))) + [rng.choice(others) for _ in range(max(0, foreign_kinds - len(others)))]:
        add(skill, foreign_value, round(foreign_value / p.foreign_max_quantity), p.foreign_max_quantity)  # (a different skill each time, so it is not always the same ore)
    return Shipment(theme, need, tier=tier)


def reward(ship: Shipment, registry: Registry) -> tuple[int, dict[str, int]]:
    """(bits, xp by skill) for shipping this crate."""
    t = registry.shipments.personal.tiers[ship.tier]
    value = worth(ship.need, registry)
    by_skill: Counter = Counter()
    for item_id, qty in ship.need.items():
        item = registry.item(item_id)
        by_skill[item.skill] += item.sell_price * qty
    xp = {skill: round(v * t.xp_per_bit) for skill, v in by_skill.items()}
    return round(value * t.bits_factor), xp


# ---- your shipments (kept in the community store under your id: no migration) ------------------------------------------
def _key(user_id: int) -> str:
    return f"shipments:{user_id}"


DEFAULT = {"made": 0, "slots": []}


async def _levels(user: User) -> dict[str, int]:
    return {skill: User.xp_to_level((await user.skill(skill)).xp) for skill in SKILLS}


def _new_slot(data: dict, user_id: int, skill: str, tier: str, levels: dict[str, int], reg: Registry) -> dict:
    data["made"] += 1
    ship = make_shipment(random.Random(f"shipment:{user_id}:{skill}:{tier}:{data['made']}"), skill, levels, reg, tier)
    return {"id": ship.id, "theme": skill, "tier": tier, "need": ship.need, "have": {}}


def _fill_slots(data: dict, user_id: int, levels: dict[str, int], reg: Registry) -> None:
    """Make a crate for every (skill, tier) the player has reached the level for and has none of yet."""
    have = {s["id"] for s in data["slots"]}
    for skill, tier in slot_ids(reg):
        if f"{skill}:{tier}" not in have and levels[skill] >= unlock_level(tier, reg):
            data["slots"].append(_new_slot(data, user_id, skill, tier, levels, reg))


def _view(data: dict, reg: Registry) -> list[Shipment]:
    by_id = {s["id"]: s for s in data["slots"]}
    out = []
    for skill, tier in slot_ids(reg):
        if (s := by_id.get(f"{skill}:{tier}")) is not None:
            out.append(Shipment(s["theme"], dict(s["need"]), dict(s["have"]), s["tier"]))
    return out


async def _migrate(user: User) -> None:
    """Crates from the old layout (three crates by theme, no ids) are cleared and anything already put in is handed back."""
    def clear(data: dict) -> dict[str, int]:
        if all("id" in s for s in data["slots"]):
            return {}
        refund: dict[str, int] = {}
        for slot in data["slots"]:
            if "id" not in slot:
                for item_id, qty in slot.get("have", {}).items():
                    refund[item_id] = refund.get(item_id, 0) + qty
        data["slots"] = [s for s in data["slots"] if "id" in s]
        return refund

    for item_id, qty in (await community.update(_key(user.id), DEFAULT, clear)).items():
        await user.add_item(item_id, qty)


async def mine(user: User, registry: Registry | None = None) -> list[Shipment]:
    """Your shipments: a basic and a harder one per skill, each once the skill is high enough (the first look makes them)."""
    reg = registry or get_registry()
    await _migrate(user)
    levels = await _levels(user)

    def look(data: dict) -> list[Shipment]:
        _fill_slots(data, user.id, levels, reg)
        return _view(data, reg)

    return await community.update(_key(user.id), DEFAULT, look)


async def locked(user: User, registry: Registry | None = None) -> list[tuple[str, str, int]]:
    """(skill, tier, level needed) for the crates you have not unlocked yet."""
    reg = registry or get_registry()
    levels = await _levels(user)
    return [(s, t, unlock_level(t, reg)) for s, t in slot_ids(reg) if levels[s] < unlock_level(t, reg)]


async def fill(user: User, slot_id: str, registry: Registry | None = None) -> dict[str, int]:
    """Put what you hold toward a crate. Returns what went in (the items leave your pack, atomically with the crate)."""
    reg = registry or get_registry()
    await mine(user, reg)
    owned = await user.items()
    moved: dict[str, int] = {}

    def slot_of(data: dict) -> dict:
        slot = next((s for s in data["slots"] if s["id"] == slot_id), None)
        if slot is None:
            raise ShipmentError("There is no such shipment.")
        return slot

    def put(data: dict) -> None:
        slot = slot_of(data)
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
            slot = slot_of(data)
            for item_id, qty in moved.items():
                slot["have"][item_id] = max(0, slot["have"].get(item_id, 0) - qty)

        await community.update(_key(user.id), DEFAULT, undo)
        raise ShipmentError("Your pack changed; try again.") from None
    return moved


@dataclass(frozen=True)
class Shipped:
    theme: str
    bits: int
    xp: dict[str, int]


async def ship(user: User, slot_id: str, registry: Registry | None = None) -> Shipped:
    """Ship a full crate: bits and xp, and a new crate in its place. Once only."""
    reg = registry or get_registry()
    await mine(user, reg)
    levels = await _levels(user)
    outcome: dict = {}

    def send(data: dict) -> None:
        index = next((n for n, s in enumerate(data["slots"]) if s["id"] == slot_id), None)
        if index is None:
            raise ShipmentError("There is no such shipment.")
        slot = data["slots"][index]
        crate = Shipment(slot["theme"], dict(slot["need"]), dict(slot["have"]), slot["tier"])
        if not crate.done():
            raise ShipmentError("It is not full yet.")
        outcome["crate"] = crate
        data["slots"][index] = _new_slot(data, user.id, slot["theme"], slot["tier"], levels, reg)  # (a new crate takes its place)

    await community.update(_key(user.id), DEFAULT, send)
    crate = outcome["crate"]
    bits, xp = reward(crate, reg)
    bits = await pets.payout(user, bits, reg)  # (a Raven pays a few % more)
    await user.add_bits(bits)
    paid: dict[str, int] = {}
    for skill, amount in xp.items():
        amount = round(amount * await xp_multiplier(user.id, reg, skill))
        if amount:
            await user.add_xp(skill, amount)
        paid[skill] = amount
    await user.inc_stat("shipments_shipped")
    await user.inc_stat(f"shipped_{crate.theme}")  # for the Shipments stats page (per skill, from this update on)
    await user.inc_stat("shipment_bits", bits)
    return Shipped(crate.theme, bits, paid)


# ---- the community shipment ------------------------------------------------------------------------------------------
COMMUNITY_KEY = "shipment_community"
COMMUNITY_DEFAULT = {"players": 0, "value": 0, "week": -1, "need": {}, "have": {}, "given": {}, "gave": {}, "done": False, "pending": {}}
WEEK = 7 * 86400


def week_of(now: float) -> int:
    """Weeks since a Monday (UTC)."""
    return int((now // 86400 + 3) // 7)  # day 0 (1970-01-01) was a Thursday


def community_target(players: int, level: float, registry: Registry) -> int:
    """The bits' worth the server must put in this week: each recently active player (at least `min_players`) is asked for a share that grows with their average level."""
    c = registry.shipments.community
    return round(max(players, c.min_players) * (c.value_per_player + c.value_per_level * level))


def make_community(week: int, registry: Registry, value: int | None = None, level: float = 100) -> dict[str, int]:
    c = registry.shipments.community
    rng = random.Random(f"community-shipment:{week}")
    need: dict[str, int] = {}
    per_kind = (value if value is not None else community_target(c.min_players, level, registry)) / c.kinds
    floor = round(per_kind / COMMUNITY_MAX_QUANTITY)
    for n in range(c.kinds):
        skill = SKILLS[n % len(SKILLS)]
        options = [i for i in pool(skill, max(1, round(level)), registry, round(per_kind * 3), floor) if i.id not in need]
        options = options or [i for i in pool(skill, 100, registry, round(per_kind * 3), floor) if i.id not in need]  # (a young server may have nothing common enough in a skill: then anything goes)
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
    players: int = 0  # how many active players this week's goal was sized for
    value: int = 0  # the bits' worth it asks for

    @property
    def fraction(self) -> float:
        total = sum(self.need.values())
        return sum(min(self.have.get(i, 0), q) for i, q in self.need.items()) / total if total else 0.0


def _roll(data: dict, now: float, reg: Registry, crowd: tuple[int, float]) -> None:
    """Start a new week's shipment when the week has changed. `crowd` is (recently active players, their average level), counted when the week starts."""
    week = week_of(now)
    if data["week"] != week:
        pending = data["pending"]
        players, level = crowd
        level = max(1.0, level)
        value = community_target(players, level, reg)
        data.clear()
        data.update({**COMMUNITY_DEFAULT, "pending": pending, "week": week, "players": max(players, reg.shipments.community.min_players), "value": value,
                     "need": make_community(week, reg, value, level)})


def _community_view(data: dict, user_id: int, now: float) -> CommunityView:
    return CommunityView(data["week"], dict(data["need"]), dict(data["have"]), data["done"], data["given"].get(str(user_id), 0), (week_of(now) + 1) * WEEK - 3 * 86400, data.get("players", 0), data.get("value", 0))


async def _crowd(now: float, reg: Registry) -> tuple[int, float]:
    """(recently active players, their average level), counted only when this week's shipment has not started yet."""
    if (await community.read(COMMUNITY_KEY, COMMUNITY_DEFAULT))["week"] == week_of(now):
        return 0, 0.0
    return await activity.recent_players(SKILLS, reg.shipments.community.active_days, now)


async def community_now(user: User, now: float | None = None, registry: Registry | None = None) -> CommunityView:
    reg = registry or get_registry()
    now = time.time() if now is None else now
    crowd = await _crowd(now, reg)

    def look(data: dict) -> CommunityView:
        _roll(data, now, reg, crowd)
        return _community_view(data, user.id, now)

    return await community.update(COMMUNITY_KEY, COMMUNITY_DEFAULT, look)


async def donate(user: User, now: float | None = None, registry: Registry | None = None) -> dict[str, int]:
    """Give the community shipment everything you hold that it still needs. When that fills it, everyone who gave enough is owed a payout (collected on their next look)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    c = reg.shipments.community
    owned = await user.items()
    crowd = await _crowd(now, reg)
    gave: dict[str, int] = {}

    def give(data: dict) -> None:
        _roll(data, now, reg, crowd)
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
        bits = await pets.payout(user, entry["bits"], reg)
        await user.add_bits(bits)
        await user.add_xp(entry["skill"], xp)
        paid.append(CommunityPayout(bits, xp, entry["skill"]))
    return paid
