"""Paying bits and items together, or not at all (crab pots and the Workbench both use it)."""

from cococap.errors import GameRuleError
from cococap.registry import Registry
from cococap.user import User


async def pay(user: User, bits: int, items: dict[str, int], reg: Registry, error: type[GameRuleError] = GameRuleError) -> None:
    """Take `bits` and `items` together, or nothing: say what is missing (as `error`, which the player sees)."""
    await user.refresh()
    owned = await user.items()
    lacking = ([f"{bits - user.purse:,} more bits"] if user.purse < bits else []) + [
        f"{reg.item(i).name} {owned.get(i, 0):,}/{q:,}" for i, q in items.items() if owned.get(i, 0) < q]
    if lacking:
        raise error("You still need " + ", ".join(lacking) + ".")
    taken: dict[str, int] = {}
    paid = 0
    try:
        if bits:
            await user.remove_bits(bits)
            paid = bits
        for item_id, quantity in items.items():
            await user.remove_item(item_id, quantity)
            taken[item_id] = quantity
    except Exception:
        await refund(user, paid, taken)
        raise error("You don't have everything it needs.") from None


async def refund(user: User, bits: int, items: dict[str, int]) -> None:
    """Give back what `pay` took (a later step failed)."""
    if bits:
        await user.add_bits(bits)
    for item_id, quantity in items.items():
        await user.add_item(item_id, quantity)
