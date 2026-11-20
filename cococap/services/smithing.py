"""Smithing: a tool is built from three PARTS (base, trim, accent) and up to three TRAITS picked from those parts.

Rules only (no Discord). All randomness comes from the `random.Random` the caller passes in, so tests can seed it.
Numbers live in configs/smithing.toml; plan: docs/plans/tools-smithing.md.
"""

import random

from cococap import emojis
from cococap.constants import STARTER_TOOLS, Rarities
from cococap.errors import GameRuleError
from cococap.models.instance import ItemInstance
from cococap.registry import Registry, get_registry
from cococap.registry.models import PART_TIERS, SmithingRules
from cococap.services.equipment import skill_for_tool
from cococap.user import User

class RestrictedPartError(GameRuleError):
    """A tool would end up with two restricted parts."""


PART_TYPES = ("base", "trim", "accent")
KINDS = ("pickaxe", "rod", "axe", "can")
XP_STAT = "smithing_xp"  # per-user counter; no migration needed


def _rules(registry: Registry | None) -> SmithingRules:
    reg = registry or get_registry()
    if reg.smithing is None:
        raise RuntimeError("configs/smithing.toml is missing")
    return reg.smithing


async def smithing_xp(user: User) -> int:
    return await user.get_stat(XP_STAT)


async def smithing_level(user: User) -> int:
    return User.xp_to_level(await smithing_xp(user))


async def add_smithing_xp(user: User, amount: int) -> None:
    if amount:
        await user.stat_add(XP_STAT, amount)


def part_emoji(slot: str, tier: int) -> str:
    """The part's tier emoji (framed in its rarity). The item template's own emoji id has no art, so never use it."""
    return emojis.get(f"part_{slot}_t{tier}", "🧩")


def part_label(slot: str, tier: int, restricted: bool = False) -> str:
    """How a part reads everywhere: "Base Part (T8)". The rarity is the tier, so it is not spelled out."""
    mark = f" {emojis.icon('restricted', '🔺')}" if restricted else ""
    return f"{slot.title()} Part (T{tier}){mark}"


# Plain glyphs for button/select text and until the `ui_trait_<stat>` emoji load (art/gen/trait_icons.py, raven_magic.toml).
TRAIT_GLYPHS = {"power": "💪", "scholar": "🧾", "appraise": "🧐", "rare_luck": "☘️", "drop_amount": "👝"}


def trait_icons(trait_ids, rules: SmithingRules, plain: bool = False) -> str:
    """Traits as icons ("no trait" if none). `plain` = unicode glyphs only, for button/select text where custom emoji do not render."""
    icons = []
    for t in trait_ids:
        stat = rules.trait(t).stat
        glyph = TRAIT_GLYPHS.get(stat, "✨")
        icons.append(glyph if plain else emojis.ui(f"trait_{stat}", glyph))
    return " ".join(icons) or "no trait"


def trait_effect(trait_id: str, rules: SmithingRules) -> str:
    """What a trait does, e.g. "+1 to +4 power" or "+3% to +10% rare luck" (the amount grows with the tool's quality)."""
    t = rules.trait(trait_id)
    lo, hi = min(t.amounts), max(t.amounts)
    fmt = (lambda v: f"{v:.0%}") if hi < 1 else (lambda v: f"{v:g}")
    return f"+{fmt(lo)} to +{fmt(hi)} {t.stat.replace('_', ' ')}"


def is_restricted(part) -> bool:
    """A part instance (rolled flag) or a tool's part dict (key) that is restricted."""
    data = part.rolled if isinstance(part, ItemInstance) else part
    return bool(data.get("restricted"))


def _flag(part) -> dict:
    return {"restricted": 1} if is_restricted(part) else {}


def enchant_cap_of(parts: dict) -> int:
    """How many different enchants a smithed tool holds: one, plus one for a restricted part."""
    return 1 + int(any(is_restricted(p) for p in (parts or {}).values()))


def scroll_for(enchant_id: str, reg: Registry):
    return next((i for i in reg.items.values() if i.scroll and i.scroll.enchant == enchant_id), None)


async def refund_enchant(user: User, enchant_id: str, levels: int, reg: Registry) -> None:
    """Give back the scroll(s) of an enchant that left a tool (nothing if no scroll exists for it)."""
    scroll = scroll_for(enchant_id, reg)
    if scroll is not None and levels > 0:
        await user.add_item(scroll.id, levels)


def _part_tier(part: ItemInstance) -> int:
    return int(part.rolled.get("tier", 1))


async def _owned_part(user: User, part_id: int, slot: str) -> ItemInstance:
    part = await user.instance(part_id)
    if part is None or part.owner_id != user.id or part.template_id != f"part_{slot}":
        raise GameRuleError(f"Pick a {slot} part you own.")
    return part


async def roll_part(
    user: User, area: int, rng: random.Random, part_type: str | None = None, registry: Registry | None = None
) -> ItemInstance:
    """A new part from a skill action in `area`: random type (unless given), tier from the area's weights,
    and fresh traits (distinct, from the whole pool) by the tier's rarity. Kind is chosen later, at smithing."""
    rules = _rules(registry)
    part_type = part_type or rng.choice(PART_TYPES)
    if part_type not in PART_TYPES:
        raise GameRuleError("Unknown part type.")
    tier = rng.choices(range(1, PART_TIERS + 1), weights=rules.weights_for_area(area))[0]
    pool = [t.id for t in rules.trait_pool]
    traits = rng.sample(pool, min(rules.fresh_trait_count(tier), len(pool)))
    rolled = {"tier": tier}
    if rng.random() < rules.restricted.chance:
        rolled["restricted"] = 1
    return await user.give_instance(f"part_{part_type}", rolled=rolled, traits=traits)


def part_line(part: ItemInstance, registry: Registry | None = None) -> str:
    """One line for a skill's result screen: the part's tier, type and traits (names from the registry)."""
    reg = registry or get_registry()
    rules = _rules(reg)
    slot = part.template_id.removeprefix("part_")
    named = f" {trait_icons(part.traits, rules)}" if part.traits else ""
    return f"Found a **{part_label(slot, _part_tier(part), is_restricted(part))}**{named}! Smith with it on Tools → Smithing."


async def maybe_drop_part(
    user: User, location: int, rng: random.Random, registry: Registry | None = None
) -> ItemInstance | None:
    """Roll once for a part from a skill action (every skill calls this once per action). Most actions give nothing.

    `location` is the skill's 1-based location number (mine, water, forest zone, field); the part's tier comes from
    the AREA that location lives in (two locations per area), so all four skills drop the same tiers in one area.
    """
    from cococap.services.areas import area_of_location

    rules = _rules(registry)
    if rng.random() >= rules.part_drop_chance:
        return None
    area = area_of_location(max(location, 1)) + 1
    # Areas past the last configured row use the last row's weights.
    area = min(area, max(w.area for w in rules.area_weights))
    return await roll_part(user, area, rng, registry=registry)


def tool_power(parts: dict, quality: str, rules: SmithingRules) -> float:
    """Sum of the three parts' tier power, times the quality grade's multiplier."""
    return sum(rules.tier_power(parts[slot]["tier"]) for slot in PART_TYPES) * rules.quality(quality).mult


def _roll_quality(rules: SmithingRules, level: int, rng: random.Random) -> str:
    """Quality grade. Higher smithing level moves odds off Crude (the first grade) onto the better grades."""
    odds = [float(q.base_odds) for q in rules.grades]
    shift = min(level * rules.levels.quality_shift_per_level, odds[0])
    odds[0] -= shift
    for i in range(1, len(odds)):
        odds[i] += shift / (len(odds) - 1)
    return rng.choices(rules.grades, weights=odds)[0].name


def _fits(rules: SmithingRules, trait_id: str, kind: str) -> bool:
    return any(t.id == trait_id for t in rules.traits_for(kind))


async def smith(
    user: User,
    kind: str,
    base_id: int,
    trim_id: int,
    accent_id: int,
    picks: dict[int, str | list[str] | None],
    rng: random.Random,
    registry: Registry | None = None,
) -> ItemInstance:
    """Build a tool of `kind` from three owned parts. `picks` maps a part id to the trait taken from it
    (at most one per part, at most max_traits in total). The three parts are used up."""
    rules = _rules(registry)
    reg = registry or get_registry()
    if kind not in KINDS:
        raise GameRuleError("A tool can be a pickaxe, rod, axe or can.")
    ids = {"base": base_id, "trim": trim_id, "accent": accent_id}
    parts = {slot: await _owned_part(user, pid, slot) for slot, pid in ids.items()}
    level = await smithing_level(user)

    if sum(1 for p in parts.values() if is_restricted(p)) > 1:
        raise RestrictedPartError("A tool can hold only one restricted part.")

    slot_trait: dict[str, str | None] = {slot: None for slot in PART_TYPES}
    slot_of = {pid: slot for slot, pid in ids.items()}
    for pid, value in picks.items():
        if pid not in slot_of:
            raise GameRuleError("That trait is not on this tool's parts.")
        if isinstance(value, list) and len(value) > 1:
            raise GameRuleError("Each part gives at most one trait.")
        trait = value[0] if isinstance(value, list) and value else value
        if trait is None:
            continue
        slot = slot_of[pid]
        if trait not in parts[slot].traits:
            raise GameRuleError("That trait is not on that part.")
        if not _fits(rules, trait, kind):
            raise GameRuleError("That trait does not fit this kind of tool.")
        slot_trait[slot] = trait
    if sum(1 for t in slot_trait.values() if t) > rules.max_traits:
        raise GameRuleError("A tool holds at most three traits.")

    # A bonus trait sometimes lands on a free slot when fewer than max_traits were picked.
    picked = {t for t in slot_trait.values() if t}
    if len(picked) < rules.max_traits and rng.random() < rules.bonus_trait_chance:
        open_slots = [s for s in PART_TYPES if slot_trait[s] is None]
        candidates = [t.id for t in rules.traits_for(kind) if t.id not in picked]
        if open_slots and candidates:
            slot_trait[rng.choice(open_slots)] = rng.choice(candidates)

    tool_parts = {slot: {"tier": _part_tier(parts[slot]), "trait": slot_trait[slot], **_flag(parts[slot])} for slot in PART_TYPES}
    quality = _roll_quality(rules, level, rng)
    cosmetic = {"rolled": True} if rng.random() < rules.cosmetic_chance else {}
    template = next(i for i in STARTER_TOOLS if reg.item(i).tool.kind == kind)

    for pid in ids.values():
        await user.delete_instance(pid)
    tool = await user.give_instance(
        template, smith_id=user.id, parts=tool_parts, quality=quality, cosmetic=cosmetic
    )
    await add_smithing_xp(user, rules.levels.xp_per_smith)
    return tool


async def _smithed_tool(user: User, tool_id: int, registry: Registry | None) -> tuple[ItemInstance, str]:
    """A tool this player owns that has smithing parts. Returns (tool, its kind)."""
    reg = registry or get_registry()
    tool = await user.instance(tool_id)
    if tool is None or tool.owner_id != user.id:
        raise GameRuleError("That tool isn't yours.")
    if not tool.parts:
        raise GameRuleError("Only smithed tools have parts.")
    item = reg.find_item(tool.template_id)
    if item is None or item.tool is None:
        raise GameRuleError("That isn't a tool.")
    skill = skill_for_tool(item.tool.kind)
    if skill and (equipped := await user.equipped_instance(skill)) and equipped.id == tool.id:
        raise GameRuleError("Unequip the tool before you change it.")
    return tool, item.tool.kind


async def salvage(user: User, tool_id: int, registry: Registry | None = None) -> list[ItemInstance]:
    """Break a tool you did NOT smith down into its three parts. Each part keeps its tier and only the trait
    the smith picked from it. The tool is deleted."""
    rules = _rules(registry)
    tool, _kind = await _smithed_tool(user, tool_id, registry)
    if tool.smith_id is None:
        raise GameRuleError("Game-made tools can't be salvaged.")
    if tool.smith_id == user.id:
        raise GameRuleError("You can't salvage a tool you smithed yourself.")
    given: list[ItemInstance] = []
    for slot in PART_TYPES:
        info = tool.parts[slot]
        trait = info.get("trait")
        given.append(
            await user.give_instance(
                f"part_{slot}", rolled={"tier": info["tier"], **_flag(info)}, traits=[trait] if trait else []
            )
        )
    reg = registry or get_registry()
    for enchant_id, lvl in tool.enchants.items():
        await refund_enchant(user, enchant_id, lvl, reg)
    await user.delete_instance(tool.id)
    await add_smithing_xp(user, rules.levels.xp_per_salvage)
    return given


async def swap_part(
    user: User,
    tool_id: int,
    slot: str,
    part_id: int,
    trait_id: str | None = None,
    registry: Registry | None = None,
) -> ItemInstance:
    """Swap one part of a smithed tool for one of yours. The old part comes back as a part (with its picked
    trait only). Quality is kept. Needs the smithing level from levels.swap_unlock_level."""
    rules = _rules(registry)
    if slot not in PART_TYPES:
        raise GameRuleError("Unknown part slot.")
    level = await smithing_level(user)
    if level < rules.levels.swap_unlock_level:
        raise GameRuleError(f"Swapping parts unlocks at smithing level {rules.levels.swap_unlock_level}.")
    tool, kind = await _smithed_tool(user, tool_id, registry)
    new_part = await _owned_part(user, part_id, slot)

    parts = {s: dict(tool.parts[s]) for s in PART_TYPES}
    others = sum(1 for s in PART_TYPES if s != slot and parts[s].get("trait"))
    if trait_id is not None:
        if trait_id not in new_part.traits:
            raise GameRuleError("That trait is not on that part.")
        if not _fits(rules, trait_id, kind):
            raise GameRuleError("That trait does not fit this kind of tool.")
        if others + 1 > rules.max_traits:
            raise GameRuleError("A tool holds at most three traits.")

    old = parts[slot]
    if is_restricted(new_part) and any(is_restricted(p) for s, p in parts.items() if s != slot):
        raise RestrictedPartError("A tool can hold only one restricted part.")
    old_trait = old.get("trait")
    returned = await user.give_instance(
        f"part_{slot}", rolled={"tier": old["tier"], **_flag(old)}, traits=[old_trait] if old_trait else []
    )
    await user.delete_instance(new_part.id)
    parts[slot] = {"tier": _part_tier(new_part), "trait": trait_id, **_flag(new_part)}
    await user.set_instance_parts(tool.id, parts)
    # Losing the restricted part loses the extra enchant slot: the oldest enchant over the cap comes off.
    reg = registry or get_registry()
    cap = enchant_cap_of(parts)
    fresh = await user.instance(tool.id)
    for e in list(fresh.enchants)[: max(0, len(fresh.enchants) - cap)]:
        await refund_enchant(user, e, fresh.enchants[e], reg)
        await user.set_enchant_level(tool.id, e, 0)
    return returned


async def remove_enchant(user: User, tool_id: int, enchant_id: str, registry: Registry | None = None) -> None:
    """Take an enchant off a tool and get its scroll(s) back. Needs removal.enchant_unlock_level."""
    rules = _rules(registry)
    reg = registry or get_registry()
    if await smithing_level(user) < rules.removal.enchant_unlock_level:
        raise GameRuleError(f"Removing enchants unlocks at smithing level {rules.removal.enchant_unlock_level}.")
    tool = await user.instance(tool_id)
    if tool is None or tool.owner_id != user.id:
        raise GameRuleError("That tool isn't yours.")
    item = reg.find_item(tool.template_id)
    skill = skill_for_tool(item.tool.kind) if item and item.tool else None
    if skill and (eq := await user.equipped_instance(skill)) and eq.id == tool.id:
        raise GameRuleError("Unequip the tool before you change it.")
    lvl = tool.enchants.get(enchant_id, 0)
    if lvl <= 0:
        raise GameRuleError("That enchant isn't on this tool.")
    await user.set_enchant_level(tool_id, enchant_id, 0)
    await refund_enchant(user, enchant_id, lvl, reg)
