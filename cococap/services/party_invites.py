"""Pending party invites.

A player has at most ONE invite waiting at a time, and it expires after ``INVITE_SECONDS``. Invites live in memory (the bot is one
process, and a minute-long invite is not worth a database row: a restart simply drops them). Both the Join/Decline message sent to
the invited player and the Party page read and answer the same invite, so whichever is used first wins.
"""

import time
from dataclasses import dataclass

from cococap.errors import CustomError
from cococap.services.party import Party

INVITE_SECONDS = 60


@dataclass(frozen=True)
class Invite:
    party_id: int
    inviter_id: int
    invited_id: int
    expires_at: float


_pending: dict[int, Invite] = {}  # invited player id -> their one invite


def _now(now: float | None) -> float:
    return time.time() if now is None else now


def pending_for(user_id: int, now: float | None = None) -> Invite | None:
    """The invite waiting for this player, if it has not expired."""
    invite = _pending.get(user_id)
    if invite is not None and invite.expires_at <= _now(now):
        del _pending[user_id]
        return None
    return invite


def offer(party: Party, inviter_id: int, invited_id: int, now: float | None = None) -> Invite:
    """Record an invite. Refused while that player already has one waiting."""
    when = _now(now)
    if pending_for(invited_id, when) is not None:
        raise CustomError("That player already has an invite waiting. Try again in a minute.")
    invite = Invite(party.party_id, inviter_id, invited_id, when + INVITE_SECONDS)
    _pending[invited_id] = invite
    return invite


def decline(user_id: int, now: float | None = None) -> bool:
    """Drop the invite. True if there was a live one."""
    return pending_for(user_id, now) is not None and _pending.pop(user_id, None) is not None


async def accept(user_id: int, now: float | None = None) -> Party:
    """Join the party of the waiting invite. The invite is used up whether or not joining works."""
    invite = pending_for(user_id, now)
    if invite is None:
        raise CustomError("That invite has expired.")
    del _pending[user_id]
    party = await Party.load(invite.party_id)
    if party is None:
        raise CustomError("The party you were invited to has been disbanded.")
    await party.add_member(user_id)
    return party


def clear() -> None:
    _pending.clear()
