"""Rules for unique tools: their final stats, equipping, and enchanting. No Discord, no SQL here."""

from dataclasses import dataclass, field, replace

from cococap.errors import GameRuleError
from cococap.models.instance import ItemInstance
from cococap.registry import Registry, get_registry
from cococap.services import accessories
from cococap.services.tool_effects import WEAPON_KINDS  # all of these go in the combat slot
from cococap.user import User

# Which kind of tool each skill uses.
TOOL_FOR_SKILL = {"mining": "pickaxe", "foraging": "axe", "combat": "sword", "fishing": "rod", "farming": "can"}


def skill_for_tool(kind: str) -> str | None:
    """Inverse of TOOL_FOR_SKILL: which skill uses this kind of tool."""
    if kind in WEAPON_KINDS:
        return "combat"
    return next((skill for skill, k in TOOL_FOR_SKILL.items() if k == kind), None)


class EquipmentError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class EffectiveStats:
    """What a tool is actually worth: template base + rolled bonuses + enchants."""

    power: int
    requirement: int
    stats: dict[str, float] = field(default_factory=dict)
    flags: frozenset[str] = frozenset()
    ability: str | None = None

    def has(self, flag: str) -> bool:
        return flag in self.flags


def effective_stats(instance: ItemInstance, registry: Registry | None = None) -> EffectiveStats:
    """Compute a tool instance's final stats. Pure: same inputs, same output.

    Order: template base, then rolled bonuses, then every enchant's ``stat_add``, then every
    ``stat_mult`` (so multipliers apply to the fully-added total regardless of enchant order).
    """
    reg = registry or get_registry()
    template = reg.item(instance.template_id)
    if template.tool is None:
        raise EquipmentError(f"{template.name} is not a tool")

    from cococap.services import smithing  # (imported here: smithing imports this module)

    stats: dict[str, float] = {"power": float(template.tool.power), **template.tool.stats}
    if instance.parts:  # a smithed tool's power comes from its three parts and its quality grade
        rules = smithing._rules(reg)
        stats["power"] = float(smithing.tool_power(instance.parts, instance.quality, rules))
        grade = [q.name for q in rules.grades].index(instance.quality)
        mult = rules.quality(instance.quality).mult
        for slot in smithing.PART_TYPES:  # each picked trait adds its amount for this grade, times the grade's mult
            trait_id = (instance.parts.get(slot) or {}).get("trait")
            if trait_id:
                trait = rules.trait(trait_id)
                stats[trait.stat] = stats.get(trait.stat, 0.0) + trait.amounts[grade] * mult
    for stat, bonus in instance.rolled.items():
        stats[stat] = stats.get(stat, 0.0) + bonus

    flags: set[str] = set()
    multipliers: list[tuple[str, float]] = []
    for enchant_id, level in instance.enchants.items():
        if enchant_id not in reg.enchants:  # a retired enchant still stored on an old tool: ignore it, don't crash
            continue
        enchant = reg.enchant(enchant_id)
        level = min(level, enchant.max_level)
        for effect in enchant.effects:
            if effect.type == "stat_add":
                stats[effect.stat] = stats.get(effect.stat, 0.0) + effect.amount * level
            elif effect.type == "stat_mult":
                multipliers.append((effect.stat, 1 + effect.amount * level))
            else:
                flags.add(effect.flag)
    for stat, factor in multipliers:
        stats[stat] = stats.get(stat, 0.0) * factor

    from cococap.services import tool_effects  # (pure; imported here so the two modules can know each other)

    power = round(stats["power"])
    for stat, bonus in tool_effects.power_stats(template.tool.kind, power, reg, template.tool.path).items():  # what this much power gives besides its main effect
        stats[stat] = stats.get(stat, 0.0) + bonus
    return EffectiveStats(
        power=power,
        requirement=template.tool.requirement,
        stats=stats,
        flags=frozenset(flags),
        ability=template.tool.ability,
    )


async def equip(user: User, skill: str, instance_id: int, registry: Registry | None = None) -> ItemInstance:
    """Equip a tool for a skill, checking ownership, tool kind and the level requirement."""
    reg = registry or get_registry()
    instance = await user.instance(instance_id)
    if instance is None:
        raise EquipmentError("You don't own that item.")
    template = reg.item(instance.template_id)
    if template.tool is None or skill_for_tool(template.tool.kind) != skill:
        raise EquipmentError(f"{template.name} can't be used for {skill}.")
    level = User.xp_to_level((await user.skill(skill)).xp)
    if level < template.tool.requirement:
        raise EquipmentError(f"{template.name} needs {skill} level {template.tool.requirement}.")
    await user.equip(skill, instance_id)
    return instance


async def auto_equip(user: User, skill: str, registry: Registry | None = None) -> ItemInstance | None:
    """Equip the newest owned tool that fits `skill` (and its level requirement); None if there is none."""
    reg = registry or get_registry()
    for instance in reversed(await user.instances()):
        tool = reg.item(instance.template_id).tool
        if tool is None or skill_for_tool(tool.kind) != skill:
            continue
        try:
            return await equip(user, skill, instance.id, reg)
        except EquipmentError:
            continue
    return None


async def equipped_stats(user: User, skill: str, registry: Registry | None = None) -> EffectiveStats | None:
    """Stats of the tool equipped for `skill`, or None if the player owns no usable tool for it.

    If nothing is equipped but the player owns a fitting tool (e.g. a freshly smithed one), it is equipped
    automatically, so screens never tell an owner to "claim" a tool they already have."""
    instance = await user.equipped_instance(skill) or await auto_equip(user, skill, registry)
    if not instance:
        return None
    base = effective_stats(instance, registry)
    from cococap.services import mastery  # (mastery only needs the user, so there is no cycle at run time)

    extra = dict(mastery.stats((await user.skill(skill)).mastery, registry))
    for stat, amount in (await accessories.bonus(user, skill, registry)).items():  # worn accessories add to the tool's stats
        extra[stat] = extra.get(stat, 0.0) + amount
    from cococap.services import areas  # (imported here: areas pulls in the registry models like this module)

    drop = (await areas.overdrive_bonus(user, registry))[1]  # a burned fuel adds to every drop
    if drop:
        extra["drop_amount"] = extra.get("drop_amount", 0.0) + drop
    if not extra:
        return base
    return replace(base, stats={**base.stats, **{k: base.stats.get(k, 0.0) + v for k, v in extra.items()}})


async def add_enchant(
    user: User, instance_id: int, enchant_id: str, *, levels: int = 1, registry: Registry | None = None
) -> ItemInstance:
    """Apply (or level up) an enchant. Crafting, shop purchases and drops all end here."""
    reg = registry or get_registry()
    instance = await user.instance(instance_id)
    if instance is None:
        raise EquipmentError("You don't own that item.")
    enchant = reg.enchant(enchant_id)
    kind = reg.item(instance.template_id).tool.kind
    if kind not in enchant.applies_to:
        raise EquipmentError(f"{enchant.name} can't be applied to a {kind}.")
    current = instance.enchants.get(enchant_id, 0)
    if current >= enchant.max_level:
        raise EquipmentError(f"{enchant.name} is already at its maximum level.")
    return await user.set_enchant_level(instance_id, enchant_id, min(enchant.max_level, current + levels))
