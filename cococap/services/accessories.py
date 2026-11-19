"""Accessories: small gear worn beside a skill's tool (2 slots per skill). Their stats are added to the tool's in
services/equipment.py, so the engines read them unchanged. Rolled ones carry traits. No Discord, no SQL here."""

import random

from cococap.errors import GameRuleError
from cococap.models.instance import ItemInstance
from cococap.registry import Registry, get_registry
from cococap.registry.models import ACCESSORY_SKILLS, AccessoryRules
from cococap.user import User


def _rules(registry: Registry | None) -> AccessoryRules:
    return (registry or get_registry()).accessories


def _check_skill(skill: str) -> None:
    if skill not in ACCESSORY_SKILLS:
        raise GameRuleError("Accessories are for mining, foraging, fishing and farming.")


def _check_slot(rules: AccessoryRules, slot: int) -> None:
    if not 0 <= slot < rules.slots_per_skill:
        raise GameRuleError("That accessory slot doesn't exist.")


async def _slots(user: User, skill: str, rules: AccessoryRules) -> list[int | None]:
    """The skill's slot list, padded or cut to the configured number of slots."""
    ids = list((await user.skill(skill)).accessory_ids)
    return (ids + [None] * rules.slots_per_skill)[: rules.slots_per_skill]


async def roll_accessory(user: User, skill: str, rng: random.Random, registry: Registry | None = None) -> ItemInstance:
    """A new accessory of `skill`: a random template for that skill, with traits drawn from that skill's pool
    (the count depends on the template's rarity). Traits are distinct."""
    rules = _rules(registry)
    _check_skill(skill)
    template = rng.choice([t for t in rules.templates if t.skill == skill])
    pool = rules.traits_for(skill)
    count = min(rules.trait_count(template.rarity), len(pool))
    traits = [t.id for t in rng.sample(pool, count)]
    return await user.give_instance(template.id, traits=traits)


async def maybe_drop_accessory(
    user: User, skill: str, rng: random.Random, registry: Registry | None = None
) -> ItemInstance | None:
    """Roll once per skill action for a rare accessory. Most actions give nothing (drop_chance)."""
    rules = _rules(registry)
    if rng.random() >= rules.drop_chance:
        return None
    return await roll_accessory(user, skill, rng, registry=registry)


def accessory_line(inst: ItemInstance, registry: Registry | None = None) -> str:
    """One line for a skill's result screen: the accessory's name and traits (names from the registry)."""
    reg = registry or get_registry()
    rules = _rules(reg)
    template = rules.template(inst.template_id)
    emoji = reg.item(inst.template_id).emoji or "🧿"
    names = [rules.trait(t).name for t in inst.traits]
    named = f" ({', '.join(names)})" if names else ""
    return f"{emoji} Found a **{template.name}**{named}! Wear it on Tools → Accessories."


async def equip(user: User, skill: str, instance_id: int, slot: int, registry: Registry | None = None) -> ItemInstance:
    """Put an accessory you own into one of the skill's slots. Each accessory sits in one slot at a time."""
    rules = _rules(registry)
    _check_skill(skill)
    _check_slot(rules, slot)
    instance = await user.instance(instance_id)
    if instance is None or instance.owner_id != user.id:
        raise GameRuleError("You don't own that accessory.")
    if rules.template(instance.template_id).skill != skill:
        raise GameRuleError(f"That accessory isn't for {skill}.")
    slots = await _slots(user, skill, rules)
    if instance_id in slots:
        raise GameRuleError("That accessory is already worn.")

    def put(data) -> None:
        slots[slot] = instance_id
        data.accessory_ids = slots

    await user.update_skill(skill, put)
    return instance


async def unequip(user: User, skill: str, slot: int, registry: Registry | None = None) -> None:
    """Take the accessory out of a slot. The accessory stays in your inventory."""
    rules = _rules(registry)
    _check_skill(skill)
    _check_slot(rules, slot)
    slots = await _slots(user, skill, rules)
    if slots[slot] is None:
        raise GameRuleError("Nothing is worn in that slot.")
    slots[slot] = None

    def take(data) -> None:
        data.accessory_ids = slots

    await user.update_skill(skill, take)


async def equipped(user: User, skill: str, registry: Registry | None = None) -> list[ItemInstance | None]:
    """What is worn in each slot of `skill`, in slot order (None = empty or no longer owned)."""
    _check_skill(skill)
    rules = _rules(registry)
    result: list[ItemInstance | None] = []
    for instance_id in await _slots(user, skill, rules):
        instance = await user.instance(instance_id) if instance_id is not None else None
        result.append(instance if instance is not None and instance.owner_id == user.id else None)
    return result


def stats_of(instance: ItemInstance, registry: Registry | None = None) -> dict[str, float]:
    """One accessory's stat bonuses: its template's base stats plus each trait's value at its rarity."""
    rules = _rules(registry)
    template = rules.template(instance.template_id)
    out = dict(template.stats)
    for trait_id in instance.traits:
        trait = rules.trait(trait_id)
        out[trait.stat] = out.get(trait.stat, 0.0) + rules.value(trait, template.rarity)
    return out


async def bonus(user: User, skill: str, registry: Registry | None = None) -> dict[str, float]:
    """Every stat bonus from the accessories worn for `skill` (summed). Skills with no accessories (combat) give none."""
    total: dict[str, float] = {}
    if skill not in ACCESSORY_SKILLS:
        return total
    for instance in await equipped(user, skill, registry):
        if instance is None:
            continue
        for stat, amount in stats_of(instance, registry).items():
            total[stat] = total.get(stat, 0.0) + amount
    return total
