"""Parties: who is in one, and the rules for creating, leaving and inviting. No Discord views here
(see ``cococap.ui.party_invite``); the /party commands and the /play Party screen both call this."""

import random

from sqlalchemy import delete, select, update

from cococap.db import get_database
from cococap.db.tables import PartyMemberRow, PartyRow
from cococap.errors import CustomError
from cococap.registry import Registry, get_registry
from cococap.user import User


# Custom errors
class PartyNotFound(CustomError):
    pass


class AlreadyInParty(CustomError):
    pass


class UserNotInParty(CustomError):
    pass


class NotPartyOwner(CustomError):
    pass


class PartyNotEmpty(CustomError):
    pass


class Party:
    """A party and its members, backed by the parties / party_members tables.

    Instances are snapshots: call ``Party.load`` again to see changes made elsewhere. All changes
    go through single transactions, so two people joining at once cannot corrupt the roster.
    """

    def __init__(self, party_id: int, owner_id: int, members: list[int]):
        self.party_id = party_id
        self._owner_id = owner_id
        self._members = members

    @classmethod
    async def load(cls, party_id: int) -> "Party | None":
        async with get_database().session() as session:
            row = await session.get(PartyRow, party_id)
            if row is None:
                return None
            ids = await session.scalars(
                select(PartyMemberRow.user_id).where(PartyMemberRow.party_id == party_id)
            )
            return cls(party_id, row.owner_id, list(ids))

    @classmethod
    async def for_user(cls, user_id: int) -> "Party | None":
        """The party `user_id` belongs to, if any."""
        async with get_database().session() as session:
            party_id = await session.scalar(
                select(PartyMemberRow.party_id).where(PartyMemberRow.user_id == user_id)
            )
        return await cls.load(party_id) if party_id is not None else None

    @property
    def members(self) -> list[int]:
        return list(self._members)

    @property
    def owner(self) -> int:
        return self._owner_id

    async def add_member(self, user_id: int):
        """Add a member (they must not already be in any party)."""
        if self.is_member(user_id):
            raise AlreadyInParty("The specified user is already in your party.")
        await User.get(user_id)  # make sure the player exists (foreign key)
        async with get_database().session() as session:
            if await session.get(PartyMemberRow, user_id) is not None:
                raise AlreadyInParty(
                    "The specified user is already in a party.",
                    title="Failed to invite the specified user",
                    footer="Tell them to do /party leave.",
                )
            session.add(PartyMemberRow(user_id=user_id, party_id=self.party_id))
        self._members.append(user_id)

    async def remove_member(self, user_id: int):
        """Remove a member from the party."""
        if not self.is_member(user_id):
            raise UserNotInParty("The specified user is not in your party...")
        async with get_database().session() as session:
            await session.execute(delete(PartyMemberRow).where(PartyMemberRow.user_id == user_id))
        self._members.remove(user_id)

    async def change_owner(self, user_id: int):
        async with get_database().session() as session:
            await session.execute(
                update(PartyRow).where(PartyRow.party_id == self.party_id).values(owner_id=user_id)
            )
        self._owner_id = user_id

    async def delete(self):
        """Delete the party; membership rows are removed by the foreign-key cascade."""
        async with get_database().session() as session:
            await session.execute(delete(PartyRow).where(PartyRow.party_id == self.party_id))
        self._members.clear()

    def is_member(self, user_id: int) -> bool:
        return user_id in self._members

    def is_owner(self, user_id: int) -> bool:
        return self._owner_id == user_id

    def member_count(self) -> int:
        return len(self._members)

    @staticmethod
    async def create(owner_id: int) -> "Party":
        await User.get(owner_id)
        async with get_database().session() as session:
            if await session.get(PartyMemberRow, owner_id) is not None:
                raise AlreadyInParty(
                    "You are already in a party.",
                    footer="Use /party leave to leave your current party.",
                )
            for _ in range(50):  # 4-digit ids; retry on the (rare) collision
                party_id = random.randint(1000, 9999)
                if await session.get(PartyRow, party_id) is None:
                    break
            else:
                raise CustomError("Too many parties right now, try again in a bit.")
            session.add(PartyRow(party_id=party_id, owner_id=owner_id))
            await session.flush()  # the member row references the party row
            session.add(PartyMemberRow(user_id=owner_id, party_id=party_id))
        return Party(party_id, owner_id, [owner_id])

    async def leave(self, user_id: int) -> bool:
        """`user_id` leaves. Returns True if that emptied (and so deleted) the party."""
        if not self.is_member(user_id):
            raise UserNotInParty("You are not in this party.")
        if self.is_owner(user_id) and self.member_count() > 1:
            raise PartyNotEmpty(
                "You are the leader of the party!",
                title="You cannot leave the party",
                footer="Promote someone else to party leader or disband the party.",
            )
        if self.member_count() == 1:
            await self.delete()
            return True
        await self.remove_member(user_id)
        return False

    def check_invite(self, inviter_id: int, member_id: int, *, is_bot: bool = False) -> None:
        """Raise if `inviter_id` may not invite this person."""
        if not self.is_owner(inviter_id):
            raise NotPartyOwner(
                "Only the party leader can invite members.",
                title="You do not have permission",
                footer="Ask your leader to invite the user to the party.",
            )
        if inviter_id == member_id:
            raise AlreadyInParty(
                "You're already here, bro.",
                title="Nice try bucko",
                footer="For real though, good curiosity. Test out all options!",
            )
        if is_bot:
            raise CustomError("Bots can't join parties.")


async def xp_multiplier(user_id: int, registry: Registry | None = None) -> float:
    """The skill-xp multiplier for `user_id`: a bonus in every skill while in a party of two or more."""
    party = await Party.for_user(user_id)
    if party is None or party.member_count() < 2:
        return 1.0
    return 1 + (registry or get_registry()).economy.party_xp_bonus
