"""Pets: collect them from Familiar Orbs, feed them crops, and the active one helps you everywhere.

* A pet species has one or more **bonuses** (``stat`` + value, in ``configs/pets.toml``). The game looks the stats up with
  ``bonuses(user)``: fishing asks for ``bite_speed``, mining for ``danger_reduction``, the Work button for ``work_bonus``...
* A bonus is its configured value x **stars** (a duplicate adds one) x **level** (fed crops; a fresh pet does a tenth of it, see ``level_floor``).
* A **Spirit** item, given to a pet, adds +15% xp in its skill while that pet is active.
* One pet is active at a time. Everything that changes the pet house goes through ``User.update_pethouse`` (one transaction).
"""

import math
import random
import time
from dataclasses import dataclass

from cococap import emojis
from cococap.errors import GameRuleError
from cococap.models.pethouse import CURVE_VERSION, OwnedPet, Pethouse
from cococap.registry import Item, Pet, Registry, get_registry
from cococap.user import User

ORB = "key_orb_familiar"  # the standard orb; others are the items whose id ends `_orb`, each with its own odds table in economy.toml [pets.orbs]
LEGACY_XP_SCALE = 300  # the one xp scale every pet had before levels depended on rarity (curve version 0); history, not balance

# Every stat the rest of the game looks up (a test checks that pets cover all of them and use no others).
RARE_FROM = 4  # a "rare drop" for the Fox: an item of this rarity or more


KNOWN_STATS = frozenset({
    "work_bonus",  # economy: the Work wage
    "payout_bonus",  # economy: shipments and the daily check-in pay this much more bits (Raven)
    "sell_bonus",  # economy: every sale pays this much more (Magpie)
    "bite_speed", "rare_luck", "treasure_luck", "pot_speed", "pot_luck",  # fishing and crab pots
    "danger_reduction", "ore_yield", "dig_shave",  # mining (the Mole's dig_shave takes this share off the pressure every dug row adds)
    "good_chop",  # foraging
    "grow_chance", "extra_harvest",  # farming (the Bee's extra_harvest: the chance a harvested plot gives a whole second harvest)
    "rare_reroll",  # every skill's rare drops (rarity 4 and up): the chance of a free second roll when the first one is not rare (Fox)
    "xp_all",  # every skill's xp
    "xp_fishing", "xp_mining", "xp_foraging", "xp_farming", "xp_combat",  # one skill's xp (a Spirit gives one of these too)
})


_STAT_SKILL = {
    "bite_speed": "fishing", "rare_luck": "fishing", "treasure_luck": "fishing", "pot_speed": "fishing", "pot_luck": "fishing",
    "danger_reduction": "mining", "ore_yield": "mining", "dig_shave": "mining", "good_chop": "foraging", "grow_chance": "farming", "extra_harvest": "farming",
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


SKILL_EMOJI = {"global": ("world", "🌐"), "mining": ("pickaxe", "⛏️"), "farming": ("can", "🌽"), "foraging": ("tree", "🌳"), "fishing": ("rod", "🎣"), "combat": ("sword", "⚔️")}  # icon name, plain glyph


def skill_emoji(pet: Pet) -> str:
    name, glyph = SKILL_EMOJI[pet.skill]
    return emojis.skill(pet.skill, emojis.icon(name, glyph))


def food_xp(item: Item, registry: Registry | None = None) -> int:
    """What one of this food is worth before any bonus (crops: their own pet xp)."""
    reg = registry or get_registry()
    if item.pet_food:
        return round(reg.economy.pets.food_xp[item.pet_food.tier - 1] * item.pet_food.xp_mult)
    return crop_pet_xp(item)


def food_skill(item: Item) -> str | None:
    return "farming" if item.crop else (item.skill if item.pet_food else None)


def food_multiplier(pet: Pet, item: Item, registry: Registry | None = None) -> float:
    """How much more this food is worth to this pet: x3 for its own skill, x2 for a pet with no skill, x1 otherwise.
    Crops are the exception: any pet gets the full matched bonus from them (they are a sellable currency, not a free drop)."""
    rules = (registry or get_registry()).economy.pets
    if item.crop:
        return rules.matched_food_multiplier
    skill = pet.skill
    if skill == "global":
        return rules.global_food_multiplier
    return rules.matched_food_multiplier if skill == food_skill(item) else 1.0


def pet_level(xp: int, rarity: int, registry: Registry | None = None) -> int:
    rules = (registry or get_registry()).economy.pets
    return min(rules.max_level, 1 + int(math.sqrt(max(0, xp) / rules.xp_scale[rarity])))


def level_xp(level: int, rarity: int, registry: Registry | None = None) -> int:
    """The xp a pet of this rarity needs to be this level."""
    return (level - 1) ** 2 * (registry or get_registry()).economy.pets.xp_scale[rarity]


def strength(owned: OwnedPet, rarity: int, registry: Registry | None = None) -> float:
    """How much of its full bonus a pet gives right now: more with stars and with level."""
    rules = (registry or get_registry()).economy.pets
    level = pet_level(owned.xp, rarity, registry)
    return (1 + rules.star_bonus * (owned.stars - 1)) * (rules.level_floor + (1 - rules.level_floor) * level / rules.max_level)


def upgrade_curve(house: Pethouse, registry: Registry | None = None) -> bool:
    """Move a pet house saved on an older xp curve onto the current one, so that every pet keeps exactly the level it had.
    (Version 0 used one scale for every species; a rarity's scale changed that. Returns whether anything was rescaled.)"""
    if house.curve_version >= CURVE_VERSION:
        return False
    reg = registry or get_registry()
    rules = reg.economy.pets
    for pet_id, owned in house.pets.items():
        pet = reg.pets.get(pet_id)
        if pet is None:
            continue
        old_level = min(rules.max_level, 1 + int(math.sqrt(max(0, owned.xp) / LEGACY_XP_SCALE)))
        xp = math.ceil(owned.xp * rules.xp_scale[pet.rarity] / LEGACY_XP_SCALE)
        while xp > 0 and pet_level(xp, pet.rarity, reg) > old_level:
            xp -= 1
        while pet_level(xp, pet.rarity, reg) < old_level:
            xp += 1
        owned.xp = xp
    house.curve_version = CURVE_VERSION
    return True


def effects(pet: Pet, owned: OwnedPet, registry: Registry | None = None) -> dict[str, float]:
    """What this pet is worth right now: {stat: amount} (a Spirit adds xp in its skill)."""
    reg = registry or get_registry()
    scale = strength(owned, pet.rarity, reg)
    found: dict[str, float] = {}
    for bonus in pet.bonuses:
        found[bonus.stat] = found.get(bonus.stat, 0.0) + bonus.value * scale
    for skill in owned.spirits:
        found[f"xp_{skill}"] = found.get(f"xp_{skill}", 0.0) + reg.economy.pets.spirit_bonus
    return found


def describe(pet: Pet, owned: OwnedPet, registry: Registry | None = None) -> list[str]:
    """The pet's bonuses as the player reads them, at its current strength."""
    reg = registry or get_registry()
    scale = strength(owned, pet.rarity, reg)
    top = (1 + reg.economy.pets.star_bonus * (owned.stars - 1))  # what it gives at the top level, with the stars it has
    lines = [bonus.text.format(v=bonus.value * scale) + (f" (max level: {bonus.value * top:.0%})" if scale < top - 1e-9 else "")
             for bonus in pet.bonuses]
    lines += [f"+{reg.economy.pets.spirit_bonus:.0%} {skill} xp (Spirit)" for skill in owned.spirits]
    return lines


def max_buffs(pet: Pet) -> str:
    """The pet's buffs at max level with one star, in words (the numbers the wiki lists)."""
    return " · ".join(bonus.text.format(v=bonus.value) for bonus in pet.bonuses)


async def bonuses(user: User, registry: Registry | None = None) -> dict[str, float]:
    """Everything your active pet is giving you right now, as {stat: amount}. Empty with no active pet."""
    reg = registry or get_registry()
    house = user.pethouse
    owned = house.pets.get(house.active) if house.active else None
    pet = reg.pets.get(house.active) if house.active else None
    return effects(pet, owned, reg) if pet and owned else {}


async def payout(user: User, bits: int, registry: Registry | None = None) -> int:
    """`bits` with your pet's `payout_bonus` (a Raven) added: what a shipment or the daily check-in pays."""
    return round(bits * (1 + (await bonuses(user, registry)).get("payout_bonus", 0.0)))


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
        gained = round(amount * play_share(pet, skill, reg) * buff_multiplier(owned, reg))
        owned.xp += gained
        return gained

    return await user.update_pethouse(give)


# ---- sidekicks: fuel tank, idle haul, food buff, lent tool (rules in services/pet_score.py) --------------------------------------
def buff_multiplier(owned: OwnedPet, registry: Registry | None = None, now: float | None = None) -> float:
    """1.5x pet xp while the skill-food buff lasts, else 1."""
    reg = registry or get_registry()
    return 1 + reg.pet_score.food_buff_bonus if owned.buff_until > (time.time() if now is None else now) else 1.0


def tank_cap_seconds(registry: Registry | None = None) -> float:
    return (registry or get_registry()).pet_score.tank_cap_hours * 3600


def _settle(house: Pethouse, now: float, reg: Registry) -> float:
    """Seconds of idle work since the last settle, limited by the fuel left (which it burns). Moves `last_collect` to now."""
    elapsed = max(0.0, now - house.last_collect) if house.last_collect else 0.0
    worked = min(elapsed, house.fuel_seconds)
    house.fuel_seconds -= worked
    house.last_collect = now
    return worked


async def fuel(user: User, crop_id: str, quantity: int, registry: Registry | None = None, now: float | None = None) -> float:
    """Pour crops into the active pet's tank (like the magnet meter). Worth = sell price x `fuel_minutes_per_value`. Returns seconds added.
    The tank is capped: only the crops that fit are used."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    crop = reg.find_item(crop_id)
    if crop is None or crop.crop is None or crop.sell_price <= 0:
        raise PetError("Only crops work as fuel.")
    await _pet_to_look_after(user, None, reg)
    per_crop = crop.sell_price * reg.pet_score.fuel_minutes_per_value * 60
    cap = tank_cap_seconds(reg)
    have = await user.item_quantity(crop_id)
    used = {}

    def pour(house: Pethouse) -> None:
        _settle(house, now, reg)
        room = max(0.0, cap - house.fuel_seconds)
        n = min(quantity, have, int(room // per_crop) + (1 if room % per_crop else 0))
        used["n"] = n
        used["added"] = min(room, n * per_crop)
        house.fuel_seconds += used["added"]

    await user.update_pethouse(pour)
    if used["n"] < 1:
        raise PetError("The tank is full." if have else f"You don't have any {crop.name}.")
    await user.remove_item(crop_id, used["n"])
    return used["added"]


def haul_skill(house: Pethouse, pet: Pet, skill_xp: dict[str, int]) -> str | None:
    """The skill a pet's haul goes to: its own, or for a global pet the one you have the most xp in."""
    if pet.skill in skill_xp:
        return pet.skill
    return max(skill_xp, key=skill_xp.get) if pet.skill == "global" and skill_xp else None


async def collect(user: User, registry: Registry | None = None, now: float | None = None) -> tuple[str | None, int, float]:
    """Bank the active pet's idle haul (skill xp, burning fuel). Returns (skill, xp, hours worked). Empty tank: nothing."""
    from cococap.services import pet_score as ps

    reg = registry or get_registry()
    now = time.time() if now is None else now
    await user.refresh()
    house = user.pethouse
    pet = reg.pets.get(house.active) if house.active else None
    owned = house.pets.get(house.active) if pet else None
    if pet is None or owned is None:
        raise PetError("You need a pet to look after.")
    xps = {s: (await user.skill(s)).xp for s in ("mining", "fishing", "foraging", "farming")}
    skill = haul_skill(house, pet, xps)
    done: dict = {}

    def settle(h: Pethouse) -> None:
        done["worked"] = _settle(h, now, reg)

    await user.update_pethouse(settle)
    hours = done["worked"] / 3600
    others = [(reg.pets[k], o) for k, o in user.pethouse.pets.items() if k != house.active]
    side = ps.sidekick_bonus(others, reg)
    xp = round(ps.haul_xp_per_hour(ps.score(pet, owned, registry=reg), side, registry=reg) * hours) if skill else 0
    if xp > 0 and skill:
        await user.add_xp(skill, xp)
    return skill, xp, hours


async def lend_tool(user: User, instance_id: str | None, pet_id: str | None = None, registry: Registry | None = None) -> None:
    """Lend one of your tools to a pet (None takes it back). Equipment checks that the tool is not equipped are done by the caller (equipment.py)."""
    reg = registry or get_registry()
    target = await _pet_to_look_after(user, pet_id, reg)

    def put(house: Pethouse) -> None:
        house.pets[target].lent_tool = instance_id

    await user.update_pethouse(put)


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


def orb_ids(registry: Registry) -> list[str]:
    """Every kind of orb (cheapest first): the items whose id ends `_orb`. Each has an odds table in economy.toml [pets.orbs]."""
    return sorted((i for i in registry.items if i.startswith("key_orb_")), key=lambda i: (registry.items[i].price, i))


def orb_odds(registry: Registry, target: str | None = None, misses: int = 0, orb: str = ORB) -> dict[str, float]:
    """The chance of each pet from one orb (they add up to 1). Each rarity has a weight (per orb kind) shared among its species,
    and a targeted pet's share is boosted."""
    weights = registry.economy.pets.orbs[orb]
    pets_ = sorted(registry.pets.values(), key=lambda p: p.id)
    per_rarity = {r: sum(1 for p in pets_ if p.rarity == r) for r in weights}
    raw = {p.id: weights.get(p.rarity, 0) / max(1, per_rarity.get(p.rarity, 1)) for p in pets_}
    if target in raw:
        raw[target] *= target_boost(misses, registry)
    total = sum(raw.values())
    return {pet_id: w / total for pet_id, w in raw.items()}


def roll_pet(rng: random.Random, registry: Registry, target: str | None = None, misses: int = 0, orb: str = ORB) -> Pet:
    odds = orb_odds(registry, target, misses, orb)
    ids = sorted(odds)
    return registry.pets[rng.choices(ids, weights=[odds[i] for i in ids])[0]]


async def open_orb(user: User, rng: random.Random, registry: Registry | None = None, orb: str = ORB) -> OrbResult:
    """Spend an orb (the standard Familiar Orb unless you name another kind): a random pet, or another star for one you have."""
    reg = registry or get_registry()
    rules = reg.economy.pets
    if orb not in rules.orbs:
        raise PetError("That isn't an orb.")
    name = reg.item(orb).name
    try:
        await user.remove_item(orb, 1)
    except ValueError:
        raise PetError(f"You don't have a {name}.") from None
    house_now = user.pethouse
    pet = roll_pet(rng, reg, house_now.target, house_now.misses, orb)
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
        await user.add_item(orb, 1)  # the pet never arrived: the orb isn't wasted
        raise
    await user.inc_stat("orbs_opened")  # for the Pets stats page
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
        # Misses are kept when you switch: the pity you built up still counts toward whatever you hunt next
        # (a hit on any pet resets it, in open_orb).
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
        outcome.update(before=pet_level(owned.xp, reg.pets[target].rarity, reg), boost=boost, gained=gained)
        owned.xp += gained
        if food.pet_food is not None:  # skill food (not crops) also starts the timed xp buff
            owned.buff_until = time.time() + reg.pet_score.food_buff_minutes * 60
        outcome["after"] = pet_level(owned.xp, reg.pets[target].rarity, reg)

    await user.update_pethouse(eat)
    if not outcome:  # the pet vanished in the meantime
        await user.add_item(food_id, quantity)
        raise PetError("You need a pet to look after.")
    await user.inc_stat("pet_foods_fed", quantity)  # for the Pets stats page
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
