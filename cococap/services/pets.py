"""Pets: collect them from Familiar Orbs, feed them crops, and the active one helps you everywhere.

* A pet species has one or more **bonuses** (``stat`` + value, in ``configs/pets.toml``). The game looks the stats up with
  ``bonuses(user)``: fishing asks for ``bite_speed``, mining for ``danger_reduction``, the Work button for ``work_bonus``...
* A bonus is its configured value x **stars** (a duplicate adds one) x **level** (fed crops; a fresh pet does half of it).
* A **Spirit** item, given to a pet, adds +15% xp in its skill while that pet is active.
* One pet is active at a time. Everything that changes the pet house goes through ``User.update_pethouse`` (one transaction).
"""

import math
import random
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.models.pethouse import OwnedPet, Pethouse
from cococap.registry import Item, Pet, Registry, get_registry
from cococap.user import User

ORB = "familiar_orb"

# Every stat the rest of the game looks up (a test checks that pets cover all of them and use no others).
KNOWN_STATS = frozenset({
    "work_bonus",  # economy: the Work wage
    "bite_speed", "rare_luck", "treasure_luck", "pot_speed", "pot_luck",  # fishing and crab pots
    "danger_reduction", "ore_yield",  # mining
    "good_chop",  # foraging
    "grow_chance", "crop_yield",  # farming
    "xp_all",  # every skill's xp (and xp_<skill> for a Spirit)
})


class PetError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def pet_level(xp: int, registry: Registry | None = None) -> int:
    rules = (registry or get_registry()).economy.pets
    return min(rules.max_level, 1 + int(math.sqrt(max(0, xp) / rules.xp_scale)))


def level_xp(level: int, registry: Registry | None = None) -> int:
    """The xp a pet needs to be this level."""
    return (level - 1) ** 2 * (registry or get_registry()).economy.pets.xp_scale


def strength(owned: OwnedPet, registry: Registry | None = None) -> float:
    """How much of its full bonus a pet gives right now: more with stars and with level."""
    rules = (registry or get_registry()).economy.pets
    level = pet_level(owned.xp, registry)
    return (1 + rules.star_bonus * (owned.stars - 1)) * (rules.level_floor + (1 - rules.level_floor) * level / rules.max_level)


def effects(pet: Pet, owned: OwnedPet, registry: Registry | None = None) -> dict[str, float]:
    """What this pet is worth right now: {stat: amount} (a Spirit adds xp in its skill)."""
    reg = registry or get_registry()
    scale = strength(owned, reg)
    found: dict[str, float] = {}
    for bonus in pet.bonuses:
        found[bonus.stat] = found.get(bonus.stat, 0.0) + bonus.value * scale
    for skill in owned.spirits:
        found[f"xp_{skill}"] = found.get(f"xp_{skill}", 0.0) + reg.economy.pets.spirit_bonus
    return found


def describe(pet: Pet, owned: OwnedPet, registry: Registry | None = None) -> list[str]:
    """The pet's bonuses as the player reads them, at its current strength."""
    reg = registry or get_registry()
    scale = strength(owned, reg)
    lines = [bonus.text.format(v=bonus.value * scale) for bonus in pet.bonuses]
    lines += [f"+{reg.economy.pets.spirit_bonus:.0%} {skill} xp (Spirit)" for skill in owned.spirits]
    return lines


async def bonuses(user: User, registry: Registry | None = None) -> dict[str, float]:
    """Everything your active pet is giving you right now, as {stat: amount}. Empty with no active pet."""
    reg = registry or get_registry()
    house = user.pethouse
    owned = house.pets.get(house.active) if house.active else None
    pet = reg.pets.get(house.active) if house.active else None
    return effects(pet, owned, reg) if pet and owned else {}


async def xp_bonus(user: User, skill: str | None, registry: Registry | None = None) -> float:
    """The extra skill xp (0.05 = +5%) your pet gives for `skill`: its all-skill bonus plus a Spirit for that skill."""
    found = await bonuses(user, registry)
    return found.get("xp_all", 0.0) + (found.get(f"xp_{skill}", 0.0) if skill else 0.0)


# ---- getting pets -------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class OrbResult:
    pet: Pet
    is_new: bool
    stars: int
    maxed: bool  # you had it at full stars: it gave xp instead


def roll_pet(rng: random.Random, registry: Registry) -> Pet:
    weights = registry.economy.pets.orb_weights
    pets = sorted(registry.pets.values(), key=lambda p: p.id)
    total_by_rarity = {r: sum(1 for p in pets if p.rarity == r) for r in weights}
    # each rarity has its weight, shared among the species of that rarity
    return rng.choices(pets, weights=[weights.get(p.rarity, 0) / max(1, total_by_rarity.get(p.rarity, 1)) for p in pets])[0]


async def open_orb(user: User, rng: random.Random, registry: Registry | None = None) -> OrbResult:
    """Spend a Familiar Orb: a random pet, or another star for one you have."""
    reg = registry or get_registry()
    rules = reg.economy.pets
    try:
        await user.remove_item(ORB, 1)
    except ValueError:
        raise PetError("You don't have a Familiar Orb.") from None
    pet = roll_pet(rng, reg)
    outcome: dict = {}

    def add(house: Pethouse) -> None:
        owned = house.pets.get(pet.id)
        if owned is None:
            house.pets[pet.id] = OwnedPet()
            outcome.update(new=True, stars=1, maxed=False)
            if house.active is None:
                house.active = pet.id  # your first pet gets to work straight away
        elif owned.stars < rules.max_stars:
            owned.stars += 1
            outcome.update(new=False, stars=owned.stars, maxed=False)
        else:
            owned.xp += rules.maxed_xp
            outcome.update(new=False, stars=owned.stars, maxed=True)

    try:
        await user.update_pethouse(add)
    except Exception:
        await user.add_item(ORB, 1)  # the pet never arrived: the orb isn't wasted
        raise
    return OrbResult(pet, outcome["new"], outcome["stars"], outcome["maxed"])


# ---- looking after them -------------------------------------------------------------------------------------
async def set_active(user: User, pet_id: str, registry: Registry | None = None) -> Pet:
    reg = registry or get_registry()
    outcome: dict = {}

    def pick(house: Pethouse) -> None:
        if pet_id in house.pets:
            house.active = pet_id
            outcome["ok"] = True

    await user.update_pethouse(pick)
    if not outcome:
        raise PetError("You don't have that pet.")
    return reg.pets[pet_id]


@dataclass(frozen=True)
class Fed:
    pet: Pet
    quantity: int
    xp: int
    level_before: int
    level_after: int


def crop_pet_xp(item: Item) -> int:
    return item.crop.pet_xp if item.crop else 0


async def feed(user: User, crop_id: str, quantity: int, registry: Registry | None = None) -> Fed:
    """Give your active pet crops: each is worth its crop's pet xp."""
    reg = registry or get_registry()
    crop = reg.find_item(crop_id)
    if crop is None or crop.crop is None:
        raise PetError("Pets eat crops.")
    await user.refresh()
    house = user.pethouse
    if not house.active or house.active not in house.pets:
        raise PetError("You need an active pet to feed.")
    if quantity < 1:
        raise PetError("Feed at least one.")
    worth = crop_pet_xp(crop)
    if worth <= 0:
        raise PetError(f"A {crop.name} isn't worth anything to a pet.")
    if await user.item_quantity(crop_id) < quantity:
        raise PetError(f"You don't have {quantity:,} {crop.name}.")
    try:
        await user.remove_item(crop_id, quantity)
    except ValueError:
        raise PetError(f"You don't have {quantity:,} {crop.name}.") from None
    outcome: dict = {}

    def eat(house: Pethouse) -> None:
        owned = house.pets.get(house.active) if house.active else None
        if owned is None:
            return
        outcome.update(pet=house.active, before=pet_level(owned.xp, reg))
        owned.xp += worth * quantity
        outcome["after"] = pet_level(owned.xp, reg)

    await user.update_pethouse(eat)
    if not outcome:  # the active pet vanished in the meantime
        await user.add_item(crop_id, quantity)
        raise PetError("You need an active pet to feed.")
    return Fed(reg.pets[outcome["pet"]], quantity, worth * quantity, outcome["before"], outcome["after"])


async def give_spirit(user: User, spirit_id: str, registry: Registry | None = None) -> tuple[Pet, str]:
    """Give a Spirit item to your active pet: +xp in that skill whenever it is active. One per skill per pet."""
    reg = registry or get_registry()
    spirit = reg.find_item(spirit_id)
    if spirit is None or spirit.category != "pet_item" or not spirit.skill:
        raise PetError("That isn't a Spirit.")
    await user.refresh()
    house = user.pethouse
    if not house.active or house.active not in house.pets:
        raise PetError("You need an active pet to give it to.")
    if spirit.skill in house.pets[house.active].spirits:
        raise PetError(f"Your {reg.pets[house.active].name} already carries the {spirit.skill} Spirit.")
    try:
        await user.remove_item(spirit_id, 1)
    except ValueError:
        raise PetError(f"You don't have a {spirit.name}.") from None
    outcome: dict = {}

    def take(house: Pethouse) -> None:
        owned = house.pets.get(house.active) if house.active else None
        if owned is not None and spirit.skill not in owned.spirits:
            owned.spirits.append(spirit.skill)
            outcome["pet"] = house.active

    await user.update_pethouse(take)
    if not outcome:
        await user.add_item(spirit_id, 1)
        raise PetError("That Spirit can't be given right now.")
    return reg.pets[outcome["pet"]], spirit.skill
