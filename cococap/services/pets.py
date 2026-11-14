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
    "xp_all",  # every skill's xp
    "xp_fishing", "xp_mining", "xp_foraging", "xp_farming", "xp_combat",  # one skill's xp (a Spirit gives one of these too)
})


_STAT_SKILL = {
    "bite_speed": "fishing", "rare_luck": "fishing", "treasure_luck": "fishing", "pot_speed": "fishing", "pot_luck": "fishing",
    "danger_reduction": "mining", "ore_yield": "mining", "good_chop": "foraging", "grow_chance": "farming", "crop_yield": "farming",
}


class PetError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


def default_skill(pet: Pet) -> str:
    """The skill the pet's bonuses work in ("global" for work/all-skill bonuses). Used only to check the data in pets.toml."""
    for bonus in pet.bonuses:
        if bonus.stat in _STAT_SKILL:
            return _STAT_SKILL[bonus.stat]
        if bonus.stat.startswith("xp_") and bonus.stat != "xp_all":
            return bonus.stat[3:]
    return "global"


SKILL_EMOJI = {"global": "🌐", "mining": "⛏️", "farming": "🌽", "foraging": "🌳", "fishing": "🎣", "combat": "⚔️"}


def skill_emoji(pet: Pet) -> str:
    return SKILL_EMOJI[pet.skill]


def food_xp(item: Item, registry: Registry | None = None) -> int:
    """What one of this food is worth before any bonus (crops: their own pet xp)."""
    reg = registry or get_registry()
    if item.pet_food:
        return reg.economy.pets.food_xp[item.pet_food.tier - 1]
    return crop_pet_xp(item)


def food_skill(item: Item) -> str | None:
    return "farming" if item.crop else (item.skill if item.pet_food else None)


def food_multiplier(pet: Pet, item: Item, registry: Registry | None = None) -> float:
    """How much more this food is worth to this pet: x3 for its own skill, x2 for a pet with no skill, x1 otherwise."""
    rules = (registry or get_registry()).economy.pets
    skill = pet.skill
    if skill == "global":
        return rules.global_food_multiplier
    return rules.matched_food_multiplier if skill == food_skill(item) else 1.0


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
    top = (1 + reg.economy.pets.star_bonus * (owned.stars - 1))  # what it gives at the top level, with the stars it has
    lines = [bonus.text.format(v=bonus.value * scale) + (f" (max level: {bonus.value * top:.0%})" if scale < top - 1e-9 else "")
             for bonus in pet.bonuses]
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


def play_share(pet: Pet, skill: str, registry: Registry | None = None) -> float:
    """How much of the skill xp you earn becomes xp for this pet while it is active: its own skill pays `play_xp_share`, a global pet
    gets `play_xp_global` from every skill, and a pet that looks after a different skill gets nothing from playing."""
    rules = (registry or get_registry()).economy.pets
    if pet.skill == skill:
        return rules.play_xp_share
    return rules.play_xp_global if pet.skill == "global" else 0.0


async def grant_play_xp(user: User, skill: str, amount: int, registry: Registry | None = None) -> int:
    """Your active pet levels as you play: a share of the skill xp you just earned. Returns the pet xp it gained."""
    if amount <= 0 or not user.pethouse.active:
        return 0
    reg = registry or get_registry()

    def give(house) -> int:
        pet = reg.pets.get(house.active) if house.active else None
        owned = house.pets.get(house.active) if pet else None
        if owned is None:
            return 0
        gained = round(amount * play_share(pet, skill, reg))
        owned.xp += gained
        return gained

    return await user.update_pethouse(give)


# ---- getting pets -------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class OrbResult:
    pet: Pet
    is_new: bool
    stars: int
    maxed: bool  # you had it at full stars: it gave xp instead
    target_hit: bool = False  # it was the pet you were hunting


def target_boost(misses: int, registry: Registry) -> float:
    """How many times likelier your targeted pet is: a base boost, plus a little more for every orb that missed it."""
    rules = registry.economy.pets
    return min(rules.max_boost, rules.target_boost + rules.pity_boost * max(0, misses))


def orb_odds(registry: Registry, target: str | None = None, misses: int = 0) -> dict[str, float]:
    """The chance of each pet from one orb (they add up to 1). Each rarity has a weight shared among its species, and a
    targeted pet's share is boosted."""
    weights = registry.economy.pets.orb_weights
    pets_ = sorted(registry.pets.values(), key=lambda p: p.id)
    per_rarity = {r: sum(1 for p in pets_ if p.rarity == r) for r in weights}
    raw = {p.id: weights.get(p.rarity, 0) / max(1, per_rarity.get(p.rarity, 1)) for p in pets_}
    if target in raw:
        raw[target] *= target_boost(misses, registry)
    total = sum(raw.values())
    return {pet_id: w / total for pet_id, w in raw.items()}


def roll_pet(rng: random.Random, registry: Registry, target: str | None = None, misses: int = 0) -> Pet:
    odds = orb_odds(registry, target, misses)
    ids = sorted(odds)
    return registry.pets[rng.choices(ids, weights=[odds[i] for i in ids])[0]]


async def open_orb(user: User, rng: random.Random, registry: Registry | None = None) -> OrbResult:
    """Spend a Familiar Orb: a random pet, or another star for one you have."""
    reg = registry or get_registry()
    rules = reg.economy.pets
    try:
        await user.remove_item(ORB, 1)
    except ValueError:
        raise PetError("You don't have a Familiar Orb.") from None
    house_now = user.pethouse
    pet = roll_pet(rng, reg, house_now.target, house_now.misses)
    outcome: dict = {}

    def add(house: Pethouse) -> None:
        if house.target:  # hunting a pet: a miss makes the next orb likelier, a hit resets it
            hit = pet.id == house.target
            outcome["target_hit"] = hit
            house.misses = 0 if hit else house.misses + 1
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
        if house.target and house.target in house.pets and house.pets[house.target].stars >= rules.max_stars:
            house.target, house.misses = None, 0  # you have it at full stars: nothing left to hunt

    try:
        await user.update_pethouse(add)
    except Exception:
        await user.add_item(ORB, 1)  # the pet never arrived: the orb isn't wasted
        raise
    return OrbResult(pet, outcome["new"], outcome["stars"], outcome["maxed"], bool(outcome.get("target_hit")))


# ---- looking after them -------------------------------------------------------------------------------------
async def set_target(user: User, pet_id: str | None, registry: Registry | None = None) -> Pet | None:
    """Choose the pet you are hunting (None to stop). Orbs are likelier to give it, and likelier still for every miss."""
    reg = registry or get_registry()
    if pet_id is not None and pet_id not in reg.pets:
        raise PetError("There is no such pet.")
    if pet_id is not None:
        await user.refresh()
        owned = user.pethouse.pets.get(pet_id)
        if owned is not None and owned.stars >= reg.economy.pets.max_stars:
            raise PetError(f"Your {reg.pets[pet_id].name} already has every star.")

    def aim(house: Pethouse) -> None:
        if house.target != pet_id:
            house.misses = 0  # a new hunt starts from nothing
        house.target = pet_id

    await user.update_pethouse(aim)
    return reg.pets[pet_id] if pet_id else None


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
    multiplier: float = 1.0


def crop_pet_xp(item: Item) -> int:
    return item.crop.pet_xp if item.crop else 0


async def _pet_to_look_after(user: User, pet_id: str | None, reg: Registry) -> str:
    await user.refresh()
    house = user.pethouse
    chosen = pet_id or house.active
    if not chosen or chosen not in house.pets:
        raise PetError("You need a pet to look after." if pet_id is None else "You don't have that pet.")
    return chosen


async def feed(user: User, food_id: str, quantity: int, registry: Registry | None = None, pet_id: str | None = None) -> Fed:
    """Feed a pet (your active one unless you name another) crops or skill food. Food of the pet's skill is worth more."""
    reg = registry or get_registry()
    food = reg.find_item(food_id)
    if food is None or (food.crop is None and food.pet_food is None):
        raise PetError("Pets eat crops and the food your skills drop.")
    target = await _pet_to_look_after(user, pet_id, reg)
    if quantity < 1:
        raise PetError("Feed at least one.")
    worth = food_xp(food, reg)
    if worth <= 0:
        raise PetError(f"A {food.name} isn't worth anything to a pet.")
    if await user.item_quantity(food_id) < quantity:
        raise PetError(f"You don't have {quantity:,} {food.name}.")
    try:
        await user.remove_item(food_id, quantity)
    except ValueError:
        raise PetError(f"You don't have {quantity:,} {food.name}.") from None
    outcome: dict = {}

    def eat(house: Pethouse) -> None:
        owned = house.pets.get(target)
        if owned is None:
            return
        boost = food_multiplier(reg.pets[target], food, reg)
        gained = round(worth * quantity * boost)
        outcome.update(before=pet_level(owned.xp, reg), boost=boost, gained=gained)
        owned.xp += gained
        outcome["after"] = pet_level(owned.xp, reg)

    await user.update_pethouse(eat)
    if not outcome:  # the pet vanished in the meantime
        await user.add_item(food_id, quantity)
        raise PetError("You need a pet to look after.")
    return Fed(reg.pets[target], quantity, outcome["gained"], outcome["before"], outcome["after"], outcome["boost"])


async def roll_food(skill: str, rolls: int, rng: random.Random, registry: Registry | None = None) -> dict[str, int]:
    """The food a skill's work turns up: each of its foods is rolled `rolls` times against its own drop odds."""
    from cococap.services.loot import roll_drop

    reg = registry or get_registry()
    found: dict[str, int] = {}
    for item in reg.items_for_skill(skill):
        if item.category == "pet_food" and item.drop:
            for _ in range(max(0, rolls)):
                if quantity := roll_drop(item, rng):
                    found[item.id] = found.get(item.id, 0) + quantity
    return found


async def give_spirit(user: User, spirit_id: str, registry: Registry | None = None, pet_id: str | None = None) -> tuple[Pet, str]:
    """Give a Spirit item to a pet (your active one unless you name another): +xp in that skill whenever it is active. One per skill per pet."""
    reg = registry or get_registry()
    spirit = reg.find_item(spirit_id)
    if spirit is None or spirit.category != "pet_item" or not spirit.skill:
        raise PetError("That isn't a Spirit.")
    target = await _pet_to_look_after(user, pet_id, reg)
    if spirit.skill in user.pethouse.pets[target].spirits:
        raise PetError(f"Your {reg.pets[target].name} already carries the {spirit.skill} Spirit.")
    try:
        await user.remove_item(spirit_id, 1)
    except ValueError:
        raise PetError(f"You don't have a {spirit.name}.") from None
    outcome: dict = {}

    def take(house: Pethouse) -> None:
        owned = house.pets.get(target)
        if owned is not None and spirit.skill not in owned.spirits:
            owned.spirits.append(spirit.skill)
            outcome["pet"] = target

    await user.update_pethouse(take)
    if not outcome:
        await user.add_item(spirit_id, 1)
        raise PetError("That Spirit can't be given right now.")
    return reg.pets[outcome["pet"]], spirit.skill
