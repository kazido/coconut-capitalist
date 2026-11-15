"""Trading: a window two players share.

One player asks another to trade (the invite waits ``INVITE_SECONDS`` on their Trade page, like a party invite). When they accept, both
see the same window: each adds items and bits to their own side, and both press Accept to finish. Changing either side takes both
Accepts back, and an Accept only counts for the exact offer the player was looking at, so nobody can swap things in after you agree.
A trade where one side adds nothing is simply a gift.

Finishing is all or nothing: both players' things are taken first (and everything given back if any of it is gone), then each is
credited. The window is closed before anything moves, so a double press cannot trade twice. Windows live in memory and close after
``IDLE_SECONDS`` without a change.
"""

import time
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.user import InsufficientFunds, User

INVITE_SECONDS = 60
IDLE_SECONDS = 600
MIN_BITS = 100  # (like /pay: no pocket-change spam)


class TradeError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class Invite:
    sender_id: int
    recipient_id: int
    expires_at: float


@dataclass
class Window:
    a: int  # who asked
    b: int
    items: dict[int, dict[str, int]] = field(default_factory=dict)  # player -> what they put in
    bits: dict[int, int] = field(default_factory=dict)
    accepted: set[int] = field(default_factory=set)
    version: int = 0  # bumps with every change: an Accept only counts for the version it was pressed on
    expires_at: float = 0.0
    closed: bool = False

    def other(self, user_id: int) -> int:
        return self.b if user_id == self.a else self.a

    def offer(self, user_id: int) -> tuple[dict[str, int], int]:
        return self.items.get(user_id, {}), self.bits.get(user_id, 0)


_invites: dict[int, Invite] = {}  # invited player -> the one invite waiting for them
_windows: dict[int, Window] = {}  # either player -> their open window
_results: dict[int, str] = {}  # what to tell a player the next time they look (a trade that finished or was called off)


def _now(now: float | None) -> float:
    return time.time() if now is None else now


def clear() -> None:
    _invites.clear()
    _windows.clear()
    _results.clear()


def pop_result(user_id: int) -> str | None:
    return _results.pop(user_id, None)


def can_send(item_id: str, registry: Registry | None = None) -> bool:
    """Stackable items only: tools and other one-of-a-kind gear stay with their owner."""
    item = (registry or get_registry()).find_item(item_id)
    return item is not None and not item.is_instance


async def tradable(user: User, registry: Registry | None = None) -> dict[str, int]:
    """What `user` could put in a trade: every stack of ordinary items they hold."""
    reg = registry or get_registry()
    return {i: q for i, q in (await user.items()).items() if q > 0 and can_send(i, reg)}


# ---- asking -------------------------------------------------------------------------------------------------------------------------
def invite_for(user_id: int, now: float | None = None) -> Invite | None:
    invite = _invites.get(user_id)
    if invite is not None and invite.expires_at <= _now(now):
        del _invites[user_id]
        return None
    return invite


def invite_from(user_id: int, now: float | None = None) -> Invite | None:
    for recipient in list(_invites):
        invite = invite_for(recipient, now)
        if invite is not None and invite.sender_id == user_id:
            return invite
    return None


def ask(sender_id: int, recipient_id: int, *, is_bot: bool = False, now: float | None = None) -> Invite:
    when = _now(now)
    if is_bot or recipient_id == sender_id:
        raise TradeError("You can only trade with other (human) players.")
    if window_of(sender_id, when) is not None:
        raise TradeError("You are already in a trade. Finish or cancel it first.")
    if window_of(recipient_id, when) is not None or invite_for(recipient_id, when) is not None:
        raise TradeError("That player is busy. Try again in a minute.")
    if (old := invite_from(sender_id, when)) is not None:
        del _invites[old.recipient_id]  # (asking someone else takes back the earlier ask)
    invite = Invite(sender_id, recipient_id, when + INVITE_SECONDS)
    _invites[recipient_id] = invite
    return invite


def withdraw_ask(sender_id: int, now: float | None = None) -> bool:
    invite = invite_from(sender_id, now)
    return invite is not None and _invites.pop(invite.recipient_id, None) is not None


def decline(recipient_id: int, now: float | None = None) -> bool:
    invite = invite_for(recipient_id, now)
    if invite is None:
        return False
    del _invites[recipient_id]
    _results[invite.sender_id] = "They declined to trade."
    return True


def accept_invite(recipient_id: int, now: float | None = None) -> Window:
    """Open the window. Both players now see it."""
    when = _now(now)
    invite = invite_for(recipient_id, when)
    if invite is None:
        raise TradeError("That request has expired.")
    del _invites[recipient_id]
    if window_of(invite.sender_id, when) is not None or window_of(recipient_id, when) is not None:
        raise TradeError("One of you is already in a trade.")
    window = Window(invite.sender_id, recipient_id, expires_at=when + IDLE_SECONDS)
    _windows[invite.sender_id] = _windows[recipient_id] = window
    return window


# ---- the window --------------------------------------------------------------------------------------------------------------------
def window_of(user_id: int, now: float | None = None) -> Window | None:
    window = _windows.get(user_id)
    if window is not None and window.expires_at <= _now(now) and not window.closed:
        _close(window, "The trade timed out, so nothing moved.")
        return None
    return window


def _close(window: Window, message: str) -> None:
    window.closed = True
    for user_id in (window.a, window.b):
        _windows.pop(user_id, None)
        _results[user_id] = message


def _open(user_id: int, now: float | None) -> Window:
    window = window_of(user_id, now)
    if window is None or window.closed:
        raise TradeError("You are not in a trade.")
    return window


def _changed(window: Window, now: float | None) -> None:
    window.accepted.clear()
    window.version += 1
    window.expires_at = _now(now) + IDLE_SECONDS


async def put_items(user: User, item_id: str, quantity: int, now: float | None = None, registry: Registry | None = None) -> Window:
    """Set how many of `item_id` you are offering (0 takes it back out)."""
    window = _open(user.id, now)
    if quantity < 0:
        raise TradeError("Enter a number above zero.")
    if quantity:
        if not can_send(item_id, registry):
            raise TradeError("Tools and gear cannot be traded.")
        if (await user.items()).get(item_id, 0) < quantity:
            raise TradeError("You do not have that many.")
        window.items.setdefault(user.id, {})[item_id] = quantity
    else:
        window.items.get(user.id, {}).pop(item_id, None)
    _changed(window, now)
    return window


async def put_bits(user: User, amount: int, now: float | None = None) -> Window:
    window = _open(user.id, now)
    if amount < 0 or (amount and amount < MIN_BITS):
        raise TradeError(f"Bits in a trade must be at least **{MIN_BITS}** (or none).")
    await user.refresh()
    if user.purse < amount:
        raise TradeError("You do not have that many bits.")
    window.bits[user.id] = amount
    _changed(window, now)
    return window


def empty_mine(user_id: int, now: float | None = None) -> Window:
    window = _open(user_id, now)
    window.items.pop(user_id, None)
    window.bits.pop(user_id, None)
    _changed(window, now)
    return window


def cancel(user_id: int, now: float | None = None) -> bool:
    window = window_of(user_id, now)
    if window is None or window.closed:
        return False
    _close(window, "The trade was called off.")
    _results[user_id] = "You called the trade off."
    return True


async def accept(user: User, version: int, now: float | None = None) -> bool:
    """Press Accept on the offer you were looking at (`version`). Returns True if that finished the trade.
    A press on an out-of-date offer is refused, so a change made a moment ago is never agreed to by accident."""
    window = _open(user.id, now)
    if version != window.version:
        raise TradeError("The offer just changed. Look it over again.")
    window.accepted.add(user.id)
    if window.accepted != {window.a, window.b}:
        return False
    await _complete(window)
    return True


def unaccept(user_id: int, now: float | None = None) -> None:
    _open(user_id, now).accepted.discard(user_id)


async def _complete(window: Window) -> None:
    window.closed = True  # (closed before anything moves: a second press finds a finished trade)
    taken: list[tuple[User, str, int]] = []  # (who, item or "bits", how much) for giving it back
    people = {window.a: await User.get(window.a), window.b: await User.get(window.b)}
    try:
        for giver_id, giver in people.items():
            items, bits = window.offer(giver_id)
            for item_id, quantity in items.items():
                await giver.remove_item(item_id, quantity)
                taken.append((giver, item_id, quantity))
            if bits:
                await giver.remove_bits(bits)
                taken.append((giver, "bits", bits))
    except (ValueError, InsufficientFunds):
        for giver, what, amount in taken:
            await (giver.add_bits(amount) if what == "bits" else giver.add_item(what, amount))
        _close(window, "One of you no longer has everything offered, so nothing moved.")
        return
    for giver_id, giver in people.items():
        receiver = people[window.other(giver_id)]
        items, bits = window.offer(giver_id)
        for item_id, quantity in items.items():
            await receiver.add_item(item_id, quantity)
        if bits:
            await receiver.add_bits(bits)
        await giver.inc_stat("trades_done")
    _close(window, "🤝 Trade complete!")
