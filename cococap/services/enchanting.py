"""Enchant scrolls: found in play (drops, chests, bosses), spent to put an enchant on one of your tools.

A scroll adds one level of its enchant to a tool of a fitting kind that isn't already at the maximum. The scroll is
used up and the enchant added together, or neither happens.
"""

from cococap.errors import GameRuleError
from cococap.models.instance import ItemInstance
from cococap.registry import Item, Registry, get_registry
from cococap.services import smithing
from cococap.services.equipment import add_enchant
from cococap.user import User


class EnchantError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


async def owned_scrolls(user: User, registry: Registry | None = None) -> list[tuple[Item, int]]:
    reg = registry or get_registry()
    owned = await user.items()
    found = [(reg.item(i), q) for i, q in owned.items() if q > 0 and (it := reg.find_item(i)) and it.scroll]
    return sorted(found, key=lambda e: e[0].name)


def problem(scroll: Item, instance: ItemInstance, reg: Registry) -> str | None:
    """Why this scroll can't go on this tool (None if it can)."""
    enchant = reg.enchant(scroll.scroll.enchant)
    tool = reg.item(instance.template_id)
    if tool.tool is None or tool.tool.kind not in enchant.applies_to:
        return f"{enchant.name} fits a {' or '.join(enchant.applies_to)}."
    if instance.enchants.get(enchant.id, 0) >= enchant.max_level:
        return f"{enchant.name} is already at its highest level on that tool."
    return None


async def apply_scroll(user: User, scroll_id: str, instance_id: int, registry: Registry | None = None) -> ItemInstance:
    reg = registry or get_registry()
    scroll = reg.find_item(scroll_id)
    if scroll is None or scroll.scroll is None:
        raise EnchantError("That isn't a scroll.")
    instance = await user.instance(instance_id)
    if instance is None:
        raise EnchantError("You don't own that tool.")
    if (why := problem(scroll, instance, reg)) is not None:
        raise EnchantError(why)
    try:
        await user.remove_item(scroll_id, 1)
    except ValueError:
        raise EnchantError(f"You don't have a {scroll.name}.") from None
    try:
        result = await add_enchant(user, instance_id, scroll.scroll.enchant, registry=reg)
        if instance.parts:  # a smithed tool holds one enchant (two with a restricted part): the oldest are replaced
            cap = smithing.enchant_cap_of(instance.parts)
            others = [e for e in result.enchants if e != scroll.scroll.enchant]
            for other in others[: max(0, len(result.enchants) - cap)]:
                await smithing.refund_enchant(user, other, result.enchants[other], reg)
                result = await user.set_enchant_level(instance_id, other, 0)
        return result
    except Exception:
        await user.add_item(scroll_id, 1)  # the enchant didn't take: the scroll is not wasted
        raise
