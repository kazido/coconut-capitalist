"""Upgrading tools: spend bits and materials and your tool turns into the next one up, in place.

The tool keeps its id (so it stays equipped), its enchants and its rolled bonuses. The shop only sells the first
tool of each kind; everything better is made here. Money, materials and the change happen together or not at all.
"""

from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.models.instance import ItemInstance
from cococap.registry import Item, Registry, get_registry
from cococap.registry.models import ToolUpgrade
from cococap.services.equipment import skill_for_tool
from cococap.user import InsufficientFunds, User


class UpgradeError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class UpgradeOffer:
    instance: ItemInstance
    current: Item
    target: Item
    cost: ToolUpgrade
    missing: tuple[str, ...]  # what the player lacks, in words ("12,000 more bits", "Feather 40/100")
    level_needed: int = 0  # the skill level the new tool asks for, if the player is below it

    @property
    def affordable(self) -> bool:
        return not self.missing and not self.level_needed


def _missing(purse: int, owned: dict[str, int], cost: ToolUpgrade, reg: Registry) -> tuple[str, ...]:
    lacking = []
    if purse < cost.bits:
        lacking.append(f"{cost.bits - purse:,} more bits")
    for item_id, need in cost.items.items():
        have = owned.get(item_id, 0)
        if have < need:
            lacking.append(f"{reg.item(item_id).name} {have:,}/{need:,}")
    return tuple(lacking)


async def offer_for(user: User, instance: ItemInstance, registry: Registry | None = None) -> UpgradeOffer | None:
    """What this tool can become, or None if it is already the best of its kind."""
    reg = registry or get_registry()
    current = reg.item(instance.template_id)
    if current.tool is None or current.tool.upgrade is None:
        return None
    cost = current.tool.upgrade
    target = reg.item(cost.to)
    skill = skill_for_tool(target.tool.kind)
    level = User.xp_to_level((await user.skill(skill)).xp) if skill else 0
    await user.refresh()
    return UpgradeOffer(
        instance, current, target, cost, _missing(user.purse, await user.items(), cost, reg),
        target.tool.requirement if level < target.tool.requirement else 0,
    )


async def offers(user: User, registry: Registry | None = None) -> list[UpgradeOffer]:
    found = []
    for instance in await user.instances():
        offer = await offer_for(user, instance, registry)
        if offer is not None:
            found.append(offer)
    return found


async def upgrade(user: User, instance_id: int, registry: Registry | None = None) -> UpgradeOffer:
    """Pay for and perform the upgrade. Returns the offer that was carried out."""
    reg = registry or get_registry()
    instance = await user.instance(instance_id)
    if instance is None:
        raise UpgradeError("You don't own that tool.")
    offer = await offer_for(user, instance, reg)
    if offer is None:
        raise UpgradeError("That tool can't be upgraded any further.")
    if offer.level_needed:
        raise UpgradeError(f"{offer.target.name} needs level {offer.level_needed} in its skill.")
    if offer.missing:
        raise UpgradeError("You still need " + ", ".join(offer.missing) + ".")
    cost = offer.cost
    taken: dict[str, int] = {}
    paid = 0
    try:
        if cost.bits:
            await user.remove_bits(cost.bits)
            paid = cost.bits
        for item_id, need in cost.items.items():
            await user.remove_item(item_id, need)
            taken[item_id] = need
        if not await user.change_template(instance.id, offer.current.id, offer.target.id):
            raise UpgradeError("That tool has already been upgraded.")
    except (InsufficientFunds, ValueError, UpgradeError) as error:
        if paid:
            await user.add_bits(paid)
        for item_id, quantity in taken.items():
            await user.add_item(item_id, quantity)
        raise error if isinstance(error, UpgradeError) else UpgradeError("You don't have everything it needs.") from None
    await user.inc_stat("tools_upgraded")
    return offer
