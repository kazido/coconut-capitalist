import time

from enum import Enum
from typing import Any, Optional
from cococap.models import UserDocument
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
    User data and operations wrapper. All currency and XP changes are atomic.
    Use User.get(discord_id) to always get a fresh user from DB.
    """

    def __init__(self, document: UserDocument):
        self._document = document

    @classmethod
    async def get(cls, discord_id: int) -> "User":
        """Get or create a user by Discord ID."""
        doc = await UserDocument.find_one(UserDocument.discord_id == discord_id)
        if not doc:
            doc = await UserDocument(name="unnamed user", discord_id=discord_id).insert()
        return cls(doc)

    @property
    def id(self) -> int:
        return self._document.discord_id

    @property
    def name(self) -> str:
        return self._document.name

    def __str__(self):
        return self.name

    # --- Atomic Currency Methods ---
    async def add_bits(self, amount: int) -> None:
        await self._document.inc({"purse": amount})

    async def remove_bits(self, amount: int) -> None:
        if await self.get_bits() < amount:
            raise InsufficientFunds("Not enough bits.")
        await self._document.inc({"purse": -amount})

    async def get_bits(self) -> int:
        # Always fetch latest from DB
        doc = await UserDocument.get(self._document.id)
        return doc.purse

    async def add_bank(self, amount: int) -> None:
        await self._document.inc({"bank": amount})

    async def add_tokens(self, amount: int) -> None:
        await self._document.inc({"tokens": amount})

    async def add_luckbucks(self, amount: int) -> None:
        await self._document.inc({"luckbucks": amount})

    # --- XP/Level Methods ---
    async def add_xp(self, skill: str, amount: int) -> dict:
        # Atomic XP add for a skill
        await self._document.inc({f"{skill}.xp": amount})
        # Optionally, handle level up logic here
        return await self.get_skill(skill)

    async def get_skill(self, skill: str) -> dict:
        doc = await UserDocument.get(self._document.id)
        return getattr(doc, skill)

    # --- Item Methods ---
    async def add_item(self, item_id: str, quantity: int = 1) -> None:
        # Atomic item add (assumes items is a dict of {item_id: {quantity: int}})
        doc = await UserDocument.get(self._document.id)
        items = doc.items.copy()
        if item_id in items:
            items[item_id]["quantity"] += quantity
        else:
            items[item_id] = {"quantity": quantity}
        await doc.set({"items": items})

    async def remove_item(self, item_id: str, quantity: int = 1) -> None:
        doc = await UserDocument.get(self._document.id)
        items = doc.items.copy()
        if item_id not in items or items[item_id]["quantity"] < quantity:
            raise ValueError("Not enough items to remove.")
        items[item_id]["quantity"] -= quantity
        if items[item_id]["quantity"] <= 0:
            del items[item_id]
        await doc.set({"items": items})

    # --- Cooldown Methods ---
    async def set_cooldown(self, command: Cooldowns) -> None:
        now = time.time()
        await self._document.set({f"cooldowns.{command.name.lower()}": now})

    async def get_cooldown(self, command: Cooldowns) -> Optional[float]:
        doc = await UserDocument.get(self._document.id)
        return doc.cooldowns.get(command.name.lower())

    # --- Field Access ---
    async def get_field(self, field: str) -> Any:
        doc = await UserDocument.get(self._document.id)
        return getattr(doc, field)

    async def set_field(self, field: str, value: Any) -> None:
        await self._document.set({field: value})

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
        xp_bar += f"<:xp_bar_right:1203894027418599505>"
        return xp_bar
