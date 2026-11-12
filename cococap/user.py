import time
from enum import Enum
from typing import Any, Optional
from beanie import UpdateResponse
from pymongo.errors import DuplicateKeyError

from cococap.models.models import UserDocument
from logging import getLogger

log = getLogger(__name__)


class Cooldowns(Enum):
    WORK = 6
    DAILY = 21
    WEEKLY = 167


class UserNotFound(Exception):
    pass


class InsufficientFunds(Exception):
    pass


class User:
    """
    User data and operations wrapper.

    Every mutation is a single MongoDB update operator against the stored document, never a
    read-modify-write on a cached copy, so concurrent commands/buttons cannot lose or duplicate
    value. Operations that must not go negative (spending, withdrawing, removing items) are
    *conditional* updates: the balance check and the decrement happen in one atomic step.

    Use User.get(discord_id) to get a handle; read-only properties reflect the document as it was
    when loaded, while the ``get_*_fresh``/``get_bits`` helpers re-read from the database.
    """

    def __init__(self, document: UserDocument):
        self._document = document

    @classmethod
    async def get(cls, discord_id: int) -> "User":
        """Get or create a user by Discord ID (safe against concurrent first-time calls)."""
        doc = await UserDocument.find_one(UserDocument.discord_id == discord_id)
        if not doc:
            try:
                doc = await UserDocument(name="unnamed user", discord_id=discord_id).insert()
            except DuplicateKeyError:
                # Another task created the user between our find and insert (unique index).
                doc = await UserDocument.find_one(UserDocument.discord_id == discord_id)
        return cls(doc)

    @property
    def id(self) -> int:
        return self._document.discord_id

    @property
    def name(self) -> str:
        return self._document.name

    def __str__(self) -> str:
        return self.name

    async def _update(self, filters: dict, update: dict) -> bool:
        """Apply `update` to this user's document if it matches `filters`; sync the local copy.

        Returns True if the update was applied.
        """
        updated = await UserDocument.find_one(
            {"_id": self._document.id, **filters}
        ).update(update, response_type=UpdateResponse.NEW_DOCUMENT)
        if updated is None:
            return False
        self._document = updated
        return True

    async def refresh(self) -> None:
        """Reload this handle's document from the database."""
        self._document = await UserDocument.get(self._document.id)

    # --- Atomic Currency Methods ---
    async def add_bits(self, amount: int) -> None:
        """Add bits to the user's purse (atomic)."""
        await self._update({}, {"$inc": {"purse": amount}})

    async def remove_bits(self, amount: int) -> None:
        """Remove bits from the purse. Atomically refuses to go below zero."""
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if not await self._update({"purse": {"$gte": amount}}, {"$inc": {"purse": -amount}}):
            raise InsufficientFunds("Not enough bits.")

    async def get_bits(self) -> int:
        """Get the latest purse value from the DB."""
        doc = await UserDocument.get(self._document.id)
        return doc.purse

    async def deposit_bits(self, amount: int) -> None:
        if not await self._update(
            {"purse": {"$gte": amount}}, {"$inc": {"purse": -amount, "bank": amount}}
        ):
            raise InsufficientFunds("Not enough bits in your purse.")

    async def withdraw_bits(self, amount: int) -> None:
        if not await self._update(
            {"bank": {"$gte": amount}}, {"$inc": {"purse": amount, "bank": -amount}}
        ):
            raise InsufficientFunds("Not enough bits in your bank.")

    async def add_bank(self, amount: int) -> None:
        await self._update({}, {"$inc": {"bank": amount}})

    async def pay(self, recipient: "User", amount: int) -> None:
        """Move `amount` bits from this user's purse to `recipient`'s (no money is created)."""
        await self.remove_bits(amount)
        try:
            await recipient.add_bits(amount)
        except Exception:
            await self.add_bits(amount)  # give it back; don't let a failed payout destroy bits
            raise

    async def add_tokens(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("add_tokens takes a non-negative amount; use rank_up to spend tokens")
        await self.inc_stat("tokens_earned", amount)
        await self._update({}, {"$inc": {"tokens": amount}})

    async def add_luckbucks(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("add_luckbucks takes a non-negative amount")
        await self.inc_stat("luckbucks_earned", amount)
        await self._update({}, {"$inc": {"luckbucks": amount}})

    async def rank_up(self, new_rank: int, token_price: int) -> bool:
        """Atomically buy rank `new_rank`: must currently be exactly one rank below, with enough
        tokens. Returns False (and changes nothing) otherwise, so a stale button can't replay it."""
        return await self._update(
            {"rank": new_rank - 1, "tokens": {"$gte": token_price}},
            {"$inc": {"tokens": -token_price}, "$set": {"rank": new_rank}},
        )

    # --- XP/Level Methods ---
    async def add_xp(self, skill: str, amount: int):
        """Add XP to a skill (atomic). Returns the updated skill model."""
        await self._update({}, {"$inc": {f"{skill}.xp": amount}})
        return getattr(self._document, skill)

    async def get_skill(self, skill: str):
        doc = await UserDocument.get(self._document.id)
        return getattr(doc, skill)

    # --- Statistics Updating --- #
    async def inc_stat(self, statistic: str, amount: int = 1):
        await self._update({}, {"$inc": {f"statistics.{statistic}": amount}})

    async def get_stat(self, statistic: str):
        doc = await UserDocument.get(self._document.id)
        return getattr(doc.statistics, statistic)

    async def set_stat(self, statistic: str, value: int = 0):
        await self._update({}, {"$set": {f"statistics.{statistic}": value}})

    # --- Item Methods ---
    async def add_item(self, item_id: str, quantity: int = 1) -> None:
        """Add an item to the user's inventory (atomic)."""
        await self._update({}, {"$inc": {f"items.{item_id}.quantity": quantity}})

    async def remove_item(self, item_id: str, quantity: int = 1) -> None:
        """Remove items from the inventory. Atomically raises if there aren't enough."""
        path = f"items.{item_id}.quantity"
        if not await self._update({path: {"$gte": quantity}}, {"$inc": {path: -quantity}}):
            raise ValueError("Not enough items to remove.")
        # Drop emptied stacks so the inventory doesn't fill with zero-quantity entries.
        await self._update({path: {"$lte": 0}}, {"$unset": {f"items.{item_id}": ""}})

    # --- Cooldown Methods ---
    async def set_cooldown(self, command: Cooldowns) -> None:
        await self._update({}, {"$set": {f"cooldowns.{command.name.lower()}": time.time()}})

    async def claim_cooldown(self, command: Cooldowns) -> bool:
        """Atomically start `command`'s cooldown if it has elapsed.

        Returns False if it was still on cooldown. Use this (not get_cooldown + set_cooldown)
        for rewards, so stale buttons or two simultaneous commands cannot both pay out.
        """
        now = time.time()
        field = f"cooldowns.{command.name.lower()}"
        ready_before = now - command.value * 3600
        off_cooldown = {"$or": [{field: {"$exists": False}}, {field: {"$lte": ready_before}}]}
        return await self._update(off_cooldown, {"$set": {field: now}})

    def get_cooldown(self, command: Cooldowns) -> Optional[float]:
        return getattr(self._document.cooldowns, command.name.lower(), None)

    # --- Field Access ---
    async def get_field_fresh(self, field: str) -> Any:
        doc = await UserDocument.get(self._document.id)
        return getattr(doc, field)

    def get_field(self, field: str) -> Any:
        return getattr(self._document, field)

    async def set_field(self, field: str, value: Any) -> None:
        await self._update({}, {"$set": {field: value}})

    async def increment_field(self, field: str, amount: int) -> None:
        await self._update({}, {"$inc": {field: amount}})

    # --- Static Utility Methods ---
    @staticmethod
    def level_to_xp(level: int) -> int:
        xp = ((level - 1) / 0.07) ** 2
        return int(xp)

    @staticmethod
    def xp_to_level(xp: int) -> int:
        level = 0.07 * (xp ** (1 / 2))
        return int(level + 1)

    @staticmethod
    def xp_for_next_level(xp: int):
        level = User.xp_to_level(xp)
        level_xp = User.level_to_xp(level)
        next_level = level + 1
        next_level_xp = User.level_to_xp(next_level)
        overflow_xp_at_level = xp - level_xp
        xp_between_levels = next_level_xp - level_xp
        return int(overflow_xp_at_level), int(xp_between_levels)

    @staticmethod
    def create_xp_bar(xp: int) -> str:
        overflow_xp, xp_needed = User.xp_for_next_level(xp)
        ratio = overflow_xp / xp_needed if xp_needed else 0
        xp_bar = "<:xp_bar_left:1203894026265428021>"
        xp_bar_size = 10
        for _ in range(int(ratio * xp_bar_size)):
            xp_bar += "<:xp_bar_big:1203894024243777546>"
        for _ in range(xp_bar_size - int(ratio * xp_bar_size)):
            xp_bar += "<:xp_bar_small:1203894025137037443>"
        xp_bar += "<:xp_bar_right:1203894027418599505>"
        return xp_bar
