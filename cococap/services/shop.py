"""Buying and selling. Money and goods move together or not at all."""

from dataclasses import dataclass

from cococap.constants import STARTER_TOOLS
from cococap.errors import GameRuleError
from cococap.models.instance import ItemInstance
from cococap.registry import Registry, get_registry
from cococap.services.equipment import EquipmentError, equip, equipped_stats, skill_for_tool
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
        made = await user.give_instance(item_id)
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
    """What your gear adds to a sale (0.08 = +8%): the Appraiser enchant on the tool of the item's skill, and for farm goods a Merchant's Haggler (Mastery)."""
    if item.skill not in ("mining", "foraging", "fishing", "farming", "combat"):
        return 0.0
    tool = await equipped_stats(user, item.skill, registry)
    if tool is None:
        return 0.0
    return tool.stats.get("appraise", 0.0) + (tool.stats.get("haggler", 0.0) if item.skill == "farming" else 0.0)


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


# Everything can be sold one by one except tools, but "Sell all" leaves the things you keep to USE: seeds to plant, bait, keys and deeds, scrolls to
# enchant with, and food and spirits for your pets.
KEPT_BY_SELL_ALL = frozenset({"seed", "bait", "key_item", "scroll", "pet_food", "pet_item"})


def sellable_for_skill(owned: dict[str, int], skill: str, registry: Registry | None = None, keep: dict[str, int] | None = None) -> dict[str, int]:
    """What a skill's Sell all would sell: every sellable stack of that skill's items you hold, less what you asked to `keep` (item -> how many)."""
    reg = registry or get_registry()
    found: dict[str, int] = {}
    for item_id, quantity in owned.items():
        item = reg.find_item(item_id)
        if item is None or item.skill != skill or not item.sellable or item.is_instance or item.sell_price <= 0 or item.category in KEPT_BY_SELL_ALL:
            continue
        spare = quantity - (keep or {}).get(item_id, 0)
        if spare > 0:
            found[item_id] = spare
    return found


async def sell_all_for_skill(user: User, skill: str, registry: Registry | None = None, keep: dict[str, int] | None = None) -> tuple[int, dict[str, int]]:
    """Sell everything `sellable_for_skill` finds. Returns (bits earned, what was sold)."""
    reg = registry or get_registry()
    sold: dict[str, int] = {}
    earned = 0
    for item_id, quantity in sellable_for_skill(await user.items(), skill, reg, keep).items():
        try:
            earned += await sell(user, item_id, quantity, reg)
            sold[item_id] = quantity
        except ShopError:
            continue  # (used or sold somewhere else a moment ago)
    return earned, sold
