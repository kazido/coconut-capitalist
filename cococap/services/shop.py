"""Buying and selling. Money and goods move together or not at all."""

from dataclasses import dataclass

from cococap.constants import STARTER_TOOLS
from cococap.errors import GameRuleError
from cococap.models.instance import ItemInstance
from cococap.registry import Registry, get_registry
from cococap.services import farming, pets
from cococap.services.equipment import EquipmentError, equip, equipped_stats, skill_for_tool
from cococap.services.legacy_tools import give_starter_tool
from cococap.user import InsufficientFunds, User

MAX_PER_PURCHASE = 1000


class ShopError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class Purchase:
    item_id: str
    quantity: int
    total: int
    instances: list[ItemInstance]  # the new unique items, for tools (empty for stackables)


async def buy(user: User, item_id: str, quantity: int = 1, registry: Registry | None = None) -> Purchase:
    reg = registry or get_registry()
    item = reg.find_item(item_id)
    if item is None or not item.buyable:
        raise ShopError("That isn't sold in the shop.")
    if (field := (await farming.locked_seeds(user, reg)).get(item.id)) is not None:
        raise ShopError(f"Reach {field} to buy that seed.")
    if not 1 <= quantity <= MAX_PER_PURCHASE:
        raise ShopError(f"You can buy between 1 and {MAX_PER_PURCHASE:,} at a time.")
    if item.is_instance:
        await _check_can_own_another(user, item, quantity, reg)
    total = item.price * quantity
    try:
        await user.remove_bits(total)
    except InsufficientFunds:
        raise ShopError(f"You need {total:,} bits for that.") from None

    try:
        if item.is_instance:
            made = [await user.give_instance(item.id) for _ in range(quantity)]
        else:
            await user.add_item(item.id, quantity)
            made = []
    except Exception:
        await user.add_bits(total)  # the goods never arrived: give the money back
        raise
    await user.inc_stat("items_bought", quantity)
    await _equip_first_tool(user, item, made, reg)
    return Purchase(item.id, quantity, total, made)


async def claim_starter_tools(user: User, registry: Registry | None = None) -> list[str]:
    """Give the free starter tools this player has never had and has no tool of that kind for. Each is claimed once ever (a stat remembers it).
    Returns the item ids handed over; the first tool of a skill is equipped for you."""
    reg = registry or get_registry()
    have = {t.tool.kind for i in await user.instances() if (t := reg.find_item(i.template_id)) and t.tool}
    given: list[str] = []
    for item_id in STARTER_TOOLS:
        item = reg.item(item_id)
        stat = f"starter_claimed_{item_id}"
        if item.tool.kind in have or await user.get_stat(stat):
            continue
        made = await give_starter_tool(user, item_id, reg)
        await user.set_stat(stat, 1)
        await _equip_first_tool(user, item, [made], reg)
        given.append(item_id)
    return given


async def _check_can_own_another(user: User, item, quantity: int, reg: Registry) -> None:
    """You own one tool per kind and make it better with upgrades; starter tools are free (see claim_starter_tools)."""
    if quantity != 1:
        raise ShopError("You only need one. Buy it once, then upgrade it.")
    if item.tool is None:
        return
    for owned in await user.instances():
        template = reg.find_item(owned.template_id)
        if template and template.tool and template.tool.kind == item.tool.kind:
            raise ShopError(f"You already have a {item.tool.kind}. Upgrade it from your inventory instead.")


async def _equip_first_tool(user: User, item, made: list[ItemInstance], reg: Registry) -> None:
    """Your first tool for a skill is equipped for you, so a new player can start straight away."""
    if not made or item.tool is None:
        return
    skill = skill_for_tool(item.tool.kind)
    if skill is None or await user.equipped_instance(skill) is not None:
        return
    try:
        await equip(user, skill, made[0].id, reg)
    except EquipmentError:
        pass  # e.g. the level requirement isn't met yet: they can equip it later from the inventory


async def haggle(user: User, item, registry: Registry | None = None) -> float:
    """What your gear and pet add to a sale (0.08 = +8%): the Appraiser enchant on the tool of the item's skill, for farm goods a Merchant's
    Haggler (Mastery), and an active Magpie's `sell_bonus` on anything. They add up."""
    magpie = (await pets.bonuses(user, registry)).get("sell_bonus", 0.0)
    if item.skill not in ("mining", "foraging", "fishing", "farming", "combat"):
        return magpie
    tool = await equipped_stats(user, item.skill, registry)
    if tool is None:
        return magpie
    return magpie + tool.stats.get("appraise", 0.0) + (tool.stats.get("haggler", 0.0) if item.skill == "farming" else 0.0)


async def sell(user: User, item_id: str, quantity: int = 1, registry: Registry | None = None) -> int:
    """Sell stackable items for bits. Returns the bits received."""
    reg = registry or get_registry()
    item = reg.find_item(item_id)
    if item is None or not item.sellable or item.is_instance:
        raise ShopError("That can't be sold.")
    if quantity < 1:
        raise ShopError("Sell at least one.")
    try:
        await user.remove_item(item.id, quantity)
    except ValueError:
        raise ShopError(f"You don't have {quantity:,} {item.name}.") from None
    earned = round(item.sell_price * quantity * (1 + await haggle(user, item, reg)))
    try:
        await user.add_bits(earned)
    except Exception:
        await user.add_item(item.id, quantity)  # payment failed: give the items back
        raise
    await user.inc_stat("items_sold", quantity)
    return earned


async def max_affordable(user: User, item_id: str, registry: Registry | None = None) -> int:
    """How many of an item `buy` would accept from this player right now: what their bits pay for, and what they may own (one tool per kind,
    the per-purchase cap). Uses the same checks as `buy`, so a button sized from this never fails on money or ownership. 0 = can't buy any."""
    reg = registry or get_registry()
    item = reg.find_item(item_id)
    if item is None or not item.buyable:
        return 0
    if (await farming.locked_seeds(user, reg)).get(item.id) is not None:
        return 0
    if item.is_instance:
        try:
            await _check_can_own_another(user, item, 1, reg)
        except ShopError:
            return 0
        cap = 1
    else:
        cap = MAX_PER_PURCHASE
    if item.price <= 0:
        return cap
    return min(cap, await user.get_bits() // item.price)
