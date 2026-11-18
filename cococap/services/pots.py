"""Crab pots: an AFK part of fishing.

A pot sits in a water you have opened, loaded with bait. While you are away it catches **rare fish and better** (not
the common ones), one per interval, using one bait per catch, until it holds as many as it can or the bait runs out.
You collect the fish later. It is deliberately a side dish: a basic pot earns very little next to fishing yourself, and
it only adds up with the best bait, a top-level pot and pets that buff pots.

Nothing is scheduled. How many catches are waiting is worked out from the clock when you look (``ready``), and the fish are
rolled from a seed made of (player, pot, when this batch began), so they are the same however often you look, and collecting
is one transaction that moves ``since`` forward (so a second click gets nothing).
"""

import random
import time
from collections import Counter
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.models.skills.fishing import Pot
from cococap.registry import Item, Registry, get_registry
from cococap.registry.models import FishingRules, PotLevel
from cococap.services import areas, payment, pets
from cococap.services.party import xp_multiplier
from cococap.user import User


class PotError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def level_rules(pot: Pot, rules: FishingRules) -> PotLevel:
    return rules.pots.levels[min(pot.level, len(rules.pots.levels)) - 1]


def slots_for(fishing_level: int, rules: FishingRules) -> int:
    """How many pots a player of this fishing level may own."""
    return sum(fishing_level >= needed for needed in rules.pots.slot_levels)


async def _level(user: User) -> int:
    return User.xp_to_level((await user.skill("fishing")).xp)


def interval_seconds(pot: Pot, registry: Registry, pet: dict[str, float] | None = None) -> float:
    """Seconds between catches: the pot's level, the bait's speed and a pet's help."""
    rules = registry.fishing
    bait = registry.item(pot.bait).bait if pot.bait else None
    speed = (bait.speed if bait else 1.0) * (1 + (pet or {}).get("pot_speed", 0.0))
    return level_rules(pot, rules).interval_minutes * 60 / speed


def ready(pot: Pot, now: float, registry: Registry, pet: dict[str, float] | None = None) -> int:
    """Catches waiting: one per interval since the batch began, never more than the pot holds or the bait left."""
    if not pot.bait or pot.bait_left <= 0 or pot.since <= 0:
        return 0
    waiting = int(max(0.0, now - pot.since) // interval_seconds(pot, registry, pet))
    return max(0, min(waiting, pot.bait_left, level_rules(pot, registry.fishing).capacity))


def roll_catch(water_id: str, bait: Item | None, rng: random.Random, registry: Registry, pet: dict[str, float] | None = None) -> Item:
    """One pot catch: a fish of `min_rarity` or better from the pot's water. Likelier the more common it is in that water,
    except that bait luck (and a Crab pet) makes the rare ones (rarity 4+) that many times likelier."""
    rules = registry.fishing
    water = next(w for w in rules.waters if w.id == water_id)
    luck = (bait.bait.luck if bait and bait.bait else 1.0) * (1 + (pet or {}).get("pot_luck", 0.0))
    pool = [(registry.item(fish_id), rate) for fish_id, rate in water.fish.items() if registry.item(fish_id).rarity >= rules.pots.min_rarity]
    if not pool:
        raise PotError("Nothing worth catching lives there.")
    weights = [(luck if fish.rarity >= 4 else 1.0) / rate for fish, rate in pool]
    return rng.choices([fish for fish, _ in pool], weights=weights)[0]


# ---- looking after pots --------------------------------------------------------------------------------------
async def craft(user: User, now: float | None = None, registry: Registry | None = None) -> Pot:
    """Craft a new level-1 pot (bits and materials), if your fishing level lets you own another."""
    reg = registry or get_registry()
    rules = reg.fishing
    level = await _level(user)
    if level < rules.pots.min_level:
        raise PotError(f"Crab pots open to anglers of fishing level {rules.pots.min_level}.")
    pots = (await user.skill("fishing")).pots
    if len(pots) >= slots_for(level, rules):
        nxt = next((n for n in rules.pots.slot_levels if n > level), None)
        raise PotError("You have all the pots you can look after" + (f" until fishing level {nxt}." if nxt else "."))
    await _pay(user, rules.pots.craft_bits, rules.pots.craft_items, reg)
    water = (await areas.open_location_list(user, "fishing", reg))[-1].id  # the newest water you can fish
    pot = Pot(level=1, water=water)

    def add(skill) -> None:
        skill.pots.append(pot)

    await user.update_skill("fishing", add)
    return pot


async def _pay(user: User, bits: int, items: dict[str, int], reg: Registry) -> None:
    """Take bits and materials together, or nothing: say what is missing."""
    await payment.pay(user, bits, items, reg, PotError)


async def upgrade(user: User, index: int, registry: Registry | None = None) -> Pot:
    reg = registry or get_registry()
    rules = reg.fishing
    pot = _get(await user.skill("fishing"), index)
    if pot.level >= len(rules.pots.levels):
        raise PotError("That pot is already at its best.")
    cost = rules.pots.levels[pot.level]
    await _pay(user, cost.upgrade_bits, cost.upgrade_items, reg)
    outcome: dict = {}

    def raise_level(skill) -> None:
        target = _get(skill, index)
        if target.level == pot.level:  # (a second click finds it already upgraded)
            target.level += 1
            outcome["ok"] = True

    done = await user.update_skill("fishing", raise_level)
    if not outcome:
        await user.add_bits(cost.upgrade_bits)  # someone clicked twice: give this payment back
        for item_id, quantity in cost.upgrade_items.items():
            await user.add_item(item_id, quantity)
        raise PotError("That pot was already upgraded.")
    return done.pots[index]


def _get(skill, index: int) -> Pot:
    if not 0 <= index < len(skill.pots):
        raise PotError("You don't have that pot.")
    return skill.pots[index]


async def set_water(user: User, index: int, water_id: str, now: float | None = None, registry: Registry | None = None) -> None:
    reg = registry or get_registry()
    now = time.time() if now is None else now
    if water_id not in {loc.id for loc in await areas.open_location_list(user, "fishing", reg)}:
        raise PotError("You haven't opened that water yet.")
    pot = _get(await user.skill("fishing"), index)
    if ready(pot, now, reg, await pets.bonuses(user, reg)):
        raise PotError("Collect what is waiting first, then move the pot.")

    def move(skill) -> None:
        _get(skill, index).water = water_id

    await user.update_skill("fishing", move)


async def load_bait(user: User, index: int, bait_id: str, quantity: int, now: float | None = None,
                    registry: Registry | None = None) -> tuple[int, int]:
    """Put bait in a pot (up to what it holds). Different bait replaces the old (the leftovers come back to you).
    Returns (loaded, returned)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    bait = reg.find_item(bait_id)
    if bait is None or bait.bait is None:
        raise PotError("That isn't bait.")
    if quantity < 1:
        raise PotError("Load at least one.")
    skill = await user.skill("fishing")
    pot = _get(skill, index)
    capacity = level_rules(pot, reg.fishing).capacity
    keeping = pot.bait_left if pot.bait == bait_id else 0
    room = capacity - keeping
    if room <= 0:
        raise PotError("That pot is already full of that bait.")
    take = min(quantity, room, await user.item_quantity(bait_id))
    if take <= 0:
        raise PotError(f"You don't have any {bait.name}.")
    try:
        await user.remove_item(bait_id, take)
    except ValueError:
        raise PotError(f"You don't have any {bait.name}.") from None
    outcome: dict = {"returned": 0, "returned_item": ""}

    def put(sk) -> None:
        target = _get(sk, index)
        if target.bait and target.bait != bait_id and target.bait_left > 0:
            outcome["returned"], outcome["returned_item"] = target.bait_left, target.bait
            target.bait_left = 0
        if target.bait_left <= 0:
            target.since = now  # the clock starts with the first bait
        target.bait = bait_id
        target.bait_left += take

    await user.update_skill("fishing", put)
    if outcome["returned"]:
        await user.add_item(outcome["returned_item"], outcome["returned"])
    return take, outcome["returned"]


@dataclass(frozen=True)
class Haul:
    fish: Counter
    xp: int
    catches: int


async def collect(user: User, index: int, now: float | None = None, registry: Registry | None = None) -> Haul:
    """Take the fish that have been caught. One transaction: bait is used and the clock moves on, so a second click
    gets nothing. The fish go in your bag and pay a little fishing xp."""
    reg = registry or get_registry()
    rules = reg.fishing
    now = time.time() if now is None else now
    pet = await pets.bonuses(user, reg)
    caught: list[Item] = []

    def take(skill) -> None:
        pot = _get(skill, index)
        n = ready(pot, now, reg, pet)
        if n <= 0:
            return
        bait = reg.item(pot.bait)
        seed = f"pot:{user.id}:{index}:{pot.since}"
        rng = random.Random(seed)
        caught.extend(roll_catch(pot.water, bait, rng, reg, pet) for _ in range(n))
        step = interval_seconds(pot, reg, pet)
        pot.bait_left -= n
        # carry the unfinished part of the interval forward, unless the pot was full and the extra time was wasted
        waiting = int(max(0.0, now - pot.since) // step)
        pot.since = pot.since + n * step if waiting <= n else now
        if pot.bait_left <= 0:
            pot.bait_left, pot.since = 0, 0.0

    await user.update_skill("fishing", take)
    if caught:
        await user.inc_stat("crab_pot_hauls")  # one pot emptied with fish in it
    found = Counter(f.id for f in caught)
    for fish_id, quantity in found.items():
        await user.add_item(fish_id, quantity)
    xp = round(sum(f.rarity for f in caught) * rules.xp_per_rarity * rules.pots.xp_factor * await xp_multiplier(user.id, reg, "fishing"))
    if xp:
        await user.update_skill("fishing", lambda s: setattr(s, "xp", s.xp + xp))
    return Haul(found, xp, len(caught))


async def collect_all(user: User, now: float | None = None, registry: Registry | None = None) -> Haul:
    total, xp, catches = Counter(), 0, 0
    for index in range(len((await user.skill("fishing")).pots)):
        haul = await collect(user, index, now, registry)
        total += haul.fish
        xp += haul.xp
        catches += haul.catches
    return Haul(total, xp, catches)


def time_to_next(pot: Pot, now: float, registry: Registry, pet: dict[str, float] | None = None) -> float | None:
    """Seconds until this pot's next catch (None if it has stopped: no bait, or full)."""
    if not pot.bait or pot.bait_left <= 0 or pot.since <= 0:
        return None
    if ready(pot, now, registry, pet) >= min(pot.bait_left, level_rules(pot, registry.fishing).capacity):
        return None
    step = interval_seconds(pot, registry, pet)
    return step - ((now - pot.since) % step)


def hourly_value(pot: Pot, registry: Registry, pet: dict[str, float] | None = None) -> float:
    """What this pot is worth per hour (bits, in the fish it would catch). For tests and for showing off in the UI."""
    bait = registry.item(pot.bait) if pot.bait else registry.item("bait_worm")
    water = next(w for w in registry.fishing.waters if w.id == pot.water)
    luck = bait.bait.luck * (1 + (pet or {}).get("pot_luck", 0.0))
    pool = [(registry.item(i), r) for i, r in water.fish.items() if registry.item(i).rarity >= registry.fishing.pots.min_rarity]
    weights = [(luck if f.rarity >= 4 else 1.0) / r for f, r in pool]
    average = sum(f.sell_price * w for (f, _), w in zip(pool, weights, strict=True)) / sum(weights)
    return average * 3600 / interval_seconds(pot, registry, pet)


