"""Gifts between players: items and bits, no tools, nothing required back.

You build a gift for one player. It waits for them for ``OFFER_SECONDS`` and nothing moves until they accept, so nobody can be
handed things they did not ask for, and a gift you decline simply goes away. A player has at most one offer waiting at a time.
Offers live in memory (a few minutes long, so a restart dropping them costs nothing).

Accepting is all or nothing: the sender's things are taken first (and given back if any of them is gone), then the receiver is
credited. The offer is removed before anything moves, so pressing Accept twice can never pay twice.
"""

import time
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.user import InsufficientFunds, User

OFFER_SECONDS = 300
MIN_BITS = 100  # (like /pay: no pocket-change spam)


class TradeError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class Offer:
    sender_id: int
    recipient_id: int
    items: dict[str, int] = field(default_factory=dict)
    bits: int = 0
    expires_at: float = 0.0


_pending: dict[int, Offer] = {}  # recipient id -> the one offer waiting for them


def _now(now: float | None) -> float:
    return time.time() if now is None else now


def clear() -> None:
    _pending.clear()


def pending_for(user_id: int, now: float | None = None) -> Offer | None:
    """The gift waiting for this player, if it has not expired."""
    offer = _pending.get(user_id)
    if offer is not None and offer.expires_at <= _now(now):
        del _pending[user_id]
        return None
    return offer


def sent_by(user_id: int, now: float | None = None) -> Offer | None:
    """A gift this player has sent that has not been answered yet."""
    for recipient in list(_pending):
        offer = pending_for(recipient, now)
        if offer is not None and offer.sender_id == user_id:
            return offer
    return None


def can_send(item_id: str, registry: Registry | None = None) -> bool:
    """Stackable items only: tools and other one-of-a-kind gear stay with their owner."""
    item = (registry or get_registry()).find_item(item_id)
    return item is not None and not item.is_instance


async def tradable(user: User, registry: Registry | None = None) -> dict[str, int]:
    """What `user` could put in a gift: every stack of ordinary items they hold."""
    reg = registry or get_registry()
    return {i: q for i, q in (await user.items()).items() if q > 0 and can_send(i, reg)}


async def offer(sender: User, recipient_id: int, items: dict[str, int], bits: int, *, is_bot: bool = False,
                now: float | None = None, registry: Registry | None = None) -> Offer:
    """Put a gift on the table for `recipient_id` (it still has to be accepted)."""
    reg = registry or get_registry()
    when = _now(now)
    items = {i: q for i, q in items.items() if q > 0}
    if is_bot or recipient_id == sender.id:
        raise TradeError("You can only send gifts to other (human) players.")
    if not items and not bits:
        raise TradeError("Put something in the gift first.")
    if bits < 0 or (bits and bits < MIN_BITS):
        raise TradeError(f"A gift of bits must be at least **{MIN_BITS}**.")
    for item_id in items:
        if not can_send(item_id, reg):
            raise TradeError("Tools and gear cannot be sent.")
    await _check_owned(sender, items, bits)
    if pending_for(recipient_id, when) is not None:
        raise TradeError("That player already has a gift waiting. Try again in a few minutes.")
    made = Offer(sender.id, recipient_id, dict(items), bits, when + OFFER_SECONDS)
    _pending[recipient_id] = made
    return made


async def _check_owned(sender: User, items: dict[str, int], bits: int) -> None:
    owned = await sender.items()
    for item_id, quantity in items.items():
        if owned.get(item_id, 0) < quantity:
            raise TradeError("You do not have all of that.")
    await sender.refresh()
    if sender.purse < bits:
        raise TradeError("You do not have that many bits.")


def withdraw(sender_id: int, now: float | None = None) -> bool:
    """Take back a gift nobody has answered yet."""
    offer = sent_by(sender_id, now)
    return offer is not None and _pending.pop(offer.recipient_id, None) is not None


def decline(recipient_id: int, now: float | None = None) -> bool:
    return pending_for(recipient_id, now) is not None and _pending.pop(recipient_id, None) is not None


async def accept(recipient: User, now: float | None = None) -> Offer:
    """Take the waiting gift. The sender's things move to the recipient, or nothing does."""
    offer = pending_for(recipient.id, now)
    if offer is None or _pending.pop(recipient.id, None) is None:  # (removed first: a second press finds nothing)
        raise TradeError("That gift has expired or was already taken.")
    sender = await User.get(offer.sender_id)
    taken_items: dict[str, int] = {}
    taken_bits = 0
    try:
        for item_id, quantity in offer.items.items():
            await sender.remove_item(item_id, quantity)
            taken_items[item_id] = quantity
        if offer.bits:
            await sender.remove_bits(offer.bits)
            taken_bits = offer.bits
    except (ValueError, InsufficientFunds):
        for item_id, quantity in taken_items.items():
            await sender.add_item(item_id, quantity)
        raise TradeError("The sender no longer has everything in the gift, so nothing moved.") from None
    for item_id, quantity in taken_items.items():
        await recipient.add_item(item_id, quantity)
    if taken_bits:
        await recipient.add_bits(taken_bits)
    await sender.inc_stat("gifts_sent")
    await recipient.inc_stat("gifts_received")
    await recipient.refresh()
    return offer
