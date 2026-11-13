"""Buying and selling. Money and goods move together or not at all."""

from dataclasses import dataclass

from cococap.models.instance import ItemInstance
from cococap.registry import Registry, get_registry
from cococap.user import InsufficientFunds, User

MAX_PER_PURCHASE = 1000


class ShopError(Exception):
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
    return Purchase(item.id, quantity, total, made)


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
    earned = item.sell_price * quantity
    try:
        await user.add_bits(earned)
    except Exception:
        await user.add_item(item.id, quantity)  # payment failed: give the items back
        raise
    await user.inc_stat("items_sold", quantity)
    return earned
