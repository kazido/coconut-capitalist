import time
from dataclasses import dataclass
from enum import Enum
from logging import getLogger
from typing import Callable, TypeVar

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError

from cococap import emojis
from cococap.db import get_database
from cococap.db.tables import ItemInstanceRow, ItemRow, SkillRow, StatRow, UserRow
from cococap.models.instance import ItemInstance
from cococap.models.pethouse import Pethouse
from cococap.models.settings import Settings
from cococap.models.skills.base import Skill
from cococap.models.skills.combat import Combat
from cococap.models.skills.farming import Farming
from cococap.models.skills.fishing import Fishing
from cococap.models.skills.foraging import Foraging
from cococap.models.skills.mining import Mining

log = getLogger(__name__)

SKILL_MODELS: dict[str, type[Skill]] = {
    "mining": Mining,
    "farming": Farming,
    "foraging": Foraging,
    "fishing": Fishing,
    "combat": Combat,
}
_COLUMN_FIELDS = {"xp", "equipped_instance_id"}  # stored as real columns, not in the JSON blob

S = TypeVar("S", bound=Skill)
T = TypeVar("T")


class Cooldowns(Enum):
    """Cooldown name -> hours between claims."""

    WORK = 6
    DAILY = 21
    WEEKLY = 167


class UserNotFound(Exception):
    pass


class InsufficientFunds(Exception):
    pass


@dataclass(frozen=True)
class Snapshot:
    """The user's scalar columns as of the last read/write."""

    discord_id: int
    name: str
    rank: int
    purse: int
    bank: int
    tokens: int
    luckbucks: int
    work_cooldown: float
    daily_cooldown: float
    weekly_cooldown: float
    settings: Settings
    pethouse: Pethouse

    @classmethod
    def from_row(cls, row: UserRow) -> "Snapshot":
        return cls(
            discord_id=row.discord_id,
            name=row.name,
            rank=row.rank,
            purse=row.purse,
            bank=row.bank,
            tokens=row.tokens,
            luckbucks=row.luckbucks,
            work_cooldown=row.work_cooldown,
            daily_cooldown=row.daily_cooldown,
            weekly_cooldown=row.weekly_cooldown,
            settings=Settings.model_validate(row.settings or {}),
            pethouse=Pethouse.model_validate(row.pethouse or {}),
        )


class User:
    """
    A player. Properties (``user.purse``, ``user.rank`` ...) reflect the database as of this
    object's last read or write; every method that changes data does so with a single SQL
    statement/transaction and then refreshes the snapshot, so concurrent commands can't lose or
    duplicate value. Anything that must not go negative (spending, withdrawing, removing items) is
    a *conditional* UPDATE: the check and the change are one atomic step.

    Use ``await User.get(discord_id)`` to get a handle (creating the player on first use).
    """

    def __init__(self, snapshot: Snapshot):
        self._s = snapshot

    @classmethod
    async def get(cls, discord_id: int) -> "User":
        """Get or create a user by Discord ID (safe against concurrent first-time calls)."""
        async with get_database().session() as session:
            await session.execute(
                sqlite_insert(UserRow)
                .values(discord_id=discord_id, name="unnamed user", settings={}, pethouse={})
                .on_conflict_do_nothing(index_elements=["discord_id"])
            )
            row = await session.get(UserRow, discord_id)
            return cls(Snapshot.from_row(row))

    @classmethod
    async def find(cls, discord_id: int) -> "User | None":
        """Like get(), but never creates a user."""
        async with get_database().session() as session:
            row = await session.get(UserRow, discord_id)
            return cls(Snapshot.from_row(row)) if row else None

    # --- snapshot properties -------------------------------------------------------------
    @property
    def id(self) -> int:
        return self._s.discord_id

    @property
    def name(self) -> str:
        return self._s.name

    @property
    def rank(self) -> int:
        return self._s.rank

    @property
    def purse(self) -> int:
        return self._s.purse

    @property
    def bank(self) -> int:
        return self._s.bank

    @property
    def tokens(self) -> int:
        return self._s.tokens

    @property
    def luckbucks(self) -> int:
        return self._s.luckbucks

    @property
    def settings(self) -> Settings:
        return self._s.settings

    @property
    def pethouse(self) -> Pethouse:
        return self._s.pethouse

    def __str__(self) -> str:
        return self.name

    async def refresh(self) -> None:
        """Reload this handle from the database."""
        async with get_database().session() as session:
            self._s = Snapshot.from_row(await session.get(UserRow, self.id))

    async def _update(self, *conditions, **values) -> bool:
        """UPDATE this user's row SET `values` (column expressions allowed) WHERE `conditions`.

        Returns True if a row matched (and refreshes the snapshot), False if a condition failed.
        """
        async with get_database().session() as session:
            result = await session.execute(
                update(UserRow)
                .where(UserRow.discord_id == self.id, *conditions)
                .values(**values)
                .returning(UserRow)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return False
            self._s = Snapshot.from_row(row)
            return True

    # --- currency ------------------------------------------------------------------------
    async def add_bits(self, amount: int) -> None:
        """Add bits to the purse. (Negative amounts are allowed but can't go below zero.)"""
        if amount < 0:
            return await self.remove_bits(-amount)
        await self._update(purse=UserRow.purse + amount)

    async def remove_bits(self, amount: int) -> None:
        """Remove bits from the purse; atomically refuses to go below zero."""
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if not await self._update(UserRow.purse >= amount, purse=UserRow.purse - amount):
            raise InsufficientFunds("Not enough bits.")

    # --- wallets: the two spendable currencies, addressed by name ---------------------------
    CURRENCIES = ("purse", "luckbucks")

    def balance(self, currency: str) -> int:
        self._check_currency(currency)
        return getattr(self._s, currency)

    @classmethod
    def _check_currency(cls, currency: str) -> None:
        if currency not in cls.CURRENCIES:
            raise ValueError(f"unknown currency {currency!r}")

    async def spend(self, currency: str, amount: int) -> None:
        """Take `amount` of `currency`; atomically refuses to go below zero."""
        self._check_currency(currency)
        if amount < 0:
            raise ValueError("amount must be non-negative")
        column = getattr(UserRow, currency)
        if not await self._update(column >= amount, **{currency: column - amount}):
            raise InsufficientFunds(f"Not enough {'bits' if currency == 'purse' else currency}.")

    async def credit(self, currency: str, amount: int) -> None:
        """Give `amount` of `currency` (a plain add: no stats are touched)."""
        self._check_currency(currency)
        if amount < 0:
            raise ValueError("amount must be non-negative")
        column = getattr(UserRow, currency)
        await self._update(**{currency: column + amount})

    async def get_bits(self) -> int:
        """The purse as it is in the database right now."""
        await self.refresh()
        return self.purse

    async def deposit_bits(self, amount: int) -> None:
        if not await self._update(
            UserRow.purse >= amount, purse=UserRow.purse - amount, bank=UserRow.bank + amount
        ):
            raise InsufficientFunds("Not enough bits in your purse.")

    async def withdraw_bits(self, amount: int) -> None:
        if not await self._update(
            UserRow.bank >= amount, purse=UserRow.purse + amount, bank=UserRow.bank - amount
        ):
            raise InsufficientFunds("Not enough bits in your bank.")

    async def add_bank(self, amount: int) -> None:
        await self._update(bank=UserRow.bank + amount)

    async def pay(self, recipient: "User", amount: int) -> None:
        """Move `amount` bits from this user's purse to `recipient`'s, in one transaction."""
        if amount < 0:
            raise ValueError("amount must be non-negative")
        async with get_database().session() as session:
            taken = await session.execute(
                update(UserRow)
                .where(UserRow.discord_id == self.id, UserRow.purse >= amount)
                .values(purse=UserRow.purse - amount)
            )
            if taken.rowcount == 0:
                raise InsufficientFunds("Not enough bits.")
            await session.execute(
                update(UserRow)
                .where(UserRow.discord_id == recipient.id)
                .values(purse=UserRow.purse + amount)
            )
        await self.refresh()
        await recipient.refresh()

    async def add_tokens(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("add_tokens takes a non-negative amount; use rank_up to spend tokens")
        await self.inc_stat("tokens_earned", amount)
        await self._update(tokens=UserRow.tokens + amount)

    async def add_luckbucks(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("add_luckbucks takes a non-negative amount")
        await self.inc_stat("luckbucks_earned", amount)
        await self._update(luckbucks=UserRow.luckbucks + amount)

    async def rank_up(self, new_rank: int, token_price: int) -> bool:
        """Atomically buy rank `new_rank`: the user must currently be exactly one rank below and
        have enough tokens. Returns False (changing nothing) otherwise, so a stale button can't
        replay a purchase."""
        return await self._update(
            UserRow.rank == new_rank - 1,
            UserRow.tokens >= token_price,
            rank=new_rank,
            tokens=UserRow.tokens - token_price,
        )

    async def set_name(self, name: str) -> None:
        if name != self.name:
            await self._update(name=name)

    async def set_setting(self, key: str, value) -> None:
        settings = self.settings.model_copy(update={key: value})
        Settings.model_validate(settings.model_dump())  # reject unknown keys / wrong types
        await self._update(settings=settings.model_dump())

    # --- skills --------------------------------------------------------------------------
    async def skill(self, name: str) -> Skill:
        """The user's progress in a skill, as the skill's Pydantic model (defaults if untouched)."""
        model = SKILL_MODELS[name]
        async with get_database().session() as session:
            row = await session.get(SkillRow, (self.id, name))
        if row is None:
            return model()
        return model.model_validate(
            {**(row.data or {}), "xp": row.xp, "equipped_instance_id": row.equipped_instance_id}
        )

    async def add_xp(self, skill: str, amount: int) -> Skill:
        """Add XP to a skill (atomic). Returns the updated skill."""
        async with get_database().session() as session:
            await session.execute(
                sqlite_insert(SkillRow)
                .values(user_id=self.id, skill=skill, xp=amount, data={})
                .on_conflict_do_update(
                    index_elements=["user_id", "skill"], set_={"xp": SkillRow.xp + amount}
                )
            )
        return await self.skill(skill)

    async def update_skill(self, name: str, change: Callable[[S], None]) -> S:
        """Read-modify-write a skill's data inside one transaction.

        ``change`` receives the skill model, mutates it in place, and the result is saved.
        Transactions are serialized by the database (BEGIN IMMEDIATE), so concurrent updates
        can't overwrite each other.
        """
        model = SKILL_MODELS[name]
        async with get_database().session() as session:
            row = await session.get(SkillRow, (self.id, name))
            skill = (
                model.model_validate(
                    {**(row.data or {}), "xp": row.xp, "equipped_instance_id": row.equipped_instance_id}
                )
                if row
                else model()
            )
            change(skill)
            values = {
                "xp": skill.xp,
                "equipped_instance_id": skill.equipped_instance_id,
                "data": skill.model_dump(exclude=_COLUMN_FIELDS),
            }
            if row is None:
                session.add(SkillRow(user_id=self.id, skill=name, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        return skill

    async def grant_daily_capped(
        self, key: str, currency: str, amount: int, cap: int, *, day: int | None = None
    ) -> int:
        """Credit up to `amount` of `currency`, but never more than `cap` per UTC day for `key`.

        Returns what was actually granted (0 once the day's cap is used up). The counter and the
        credit change in one transaction, so simultaneous games can't both slip past the cap.
        """
        self._check_currency(currency)
        day = int(time.time() // 86400) if day is None else day
        day_stat, total_stat = f"daily_{key}_day", f"daily_{key}_total"
        async with get_database().session() as session:
            day_row = await session.get(StatRow, (self.id, day_stat))
            total_row = await session.get(StatRow, (self.id, total_stat))
            used = total_row.value if (day_row and total_row and day_row.value == day) else 0
            granted = max(0, min(amount, cap - used))
            for name, value in ((day_stat, day), (total_stat, used + granted)):
                await session.execute(
                    sqlite_insert(StatRow)
                    .values(user_id=self.id, name=name, value=value)
                    .on_conflict_do_update(index_elements=["user_id", "name"], set_={"value": value})
                )
            if granted:
                column = getattr(UserRow, currency)
                await session.execute(
                    update(UserRow).where(UserRow.discord_id == self.id).values(**{currency: column + granted})
                )
        await self.refresh()
        return granted

    # --- statistics ----------------------------------------------------------------------
    async def inc_stat(self, statistic: str, amount: int = 1) -> None:
        async with get_database().session() as session:
            await session.execute(
                sqlite_insert(StatRow)
                .values(user_id=self.id, name=statistic, value=amount)
                .on_conflict_do_update(
                    index_elements=["user_id", "name"], set_={"value": StatRow.value + amount}
                )
            )

    async def get_stat(self, statistic: str) -> int:
        async with get_database().session() as session:
            row = await session.get(StatRow, (self.id, statistic))
            return row.value if row else 0

    async def set_stat(self, statistic: str, value: int = 0) -> None:
        async with get_database().session() as session:
            await session.execute(
                sqlite_insert(StatRow)
                .values(user_id=self.id, name=statistic, value=value)
                .on_conflict_do_update(index_elements=["user_id", "name"], set_={"value": value})
            )

    async def stats(self) -> dict[str, int]:
        """Every statistic this user has recorded."""
        async with get_database().session() as session:
            rows = await session.execute(select(StatRow).where(StatRow.user_id == self.id))
            return {row.name: row.value for row in rows.scalars()}

    # --- items ---------------------------------------------------------------------------
    @staticmethod
    def _check_item_id(item_id: str) -> None:
        if not item_id or not item_id.replace("_", "").isalnum():
            raise ValueError(f"Invalid item id {item_id!r}: use e.g. 'apple_seed', not 'apple.seed'")

    async def items(self) -> dict[str, int]:
        """The inventory as {item_id: quantity}."""
        async with get_database().session() as session:
            rows = await session.execute(select(ItemRow).where(ItemRow.user_id == self.id))
            return {row.item_id: row.quantity for row in rows.scalars()}

    async def item_quantity(self, item_id: str) -> int:
        async with get_database().session() as session:
            row = await session.get(ItemRow, (self.id, item_id))
            return row.quantity if row else 0

    async def add_item(self, item_id: str, quantity: int = 1) -> None:
        """Add items to the inventory (atomic)."""
        self._check_item_id(item_id)
        if quantity < 0:
            raise ValueError("quantity must be non-negative")
        if quantity == 0:
            return
        async with get_database().session() as session:
            await session.execute(
                sqlite_insert(ItemRow)
                .values(user_id=self.id, item_id=item_id, quantity=quantity)
                .on_conflict_do_update(
                    index_elements=["user_id", "item_id"],
                    set_={"quantity": ItemRow.quantity + quantity},
                )
            )

    async def remove_item(self, item_id: str, quantity: int = 1) -> None:
        """Remove items. Atomically raises ValueError if there aren't enough."""
        self._check_item_id(item_id)
        async with get_database().session() as session:
            result = await session.execute(
                update(ItemRow)
                .where(
                    ItemRow.user_id == self.id,
                    ItemRow.item_id == item_id,
                    ItemRow.quantity >= quantity,
                )
                .values(quantity=ItemRow.quantity - quantity)
            )
            if result.rowcount == 0:
                raise ValueError("Not enough items to remove.")
            await session.execute(
                delete(ItemRow).where(
                    ItemRow.user_id == self.id,
                    ItemRow.item_id == item_id,
                    ItemRow.quantity == 0,
                )
            )
            # (a quantity>0 CHECK would reject the 0 row, so empty stacks are deleted above)

    # --- item instances (unique tools) -----------------------------------------------------
    @staticmethod
    def _to_instance(row: ItemInstanceRow) -> ItemInstance:
        return ItemInstance(
            id=row.id,
            owner_id=row.owner_id,
            template_id=row.template_id,
            rolled=dict(row.rolled or {}),
            enchants=dict(row.enchants or {}),
        )

    async def instances(self) -> list[ItemInstance]:
        """Every unique item this player owns, oldest first."""
        async with get_database().session() as session:
            rows = await session.scalars(
                select(ItemInstanceRow)
                .where(ItemInstanceRow.owner_id == self.id)
                .order_by(ItemInstanceRow.id)
            )
            return [self._to_instance(r) for r in rows]

    async def instance(self, instance_id: int) -> ItemInstance | None:
        """One of this player's instances (None if it doesn't exist or belongs to someone else)."""
        async with get_database().session() as session:
            row = await session.get(ItemInstanceRow, instance_id)
            if row is None or row.owner_id != self.id:
                return None
            return self._to_instance(row)

    async def give_instance(
        self,
        template_id: str,
        *,
        enchants: dict[str, int] | None = None,
        rolled: dict[str, float] | None = None,
    ) -> ItemInstance:
        """Create a new unique item owned by this player."""
        async with get_database().session() as session:
            row = ItemInstanceRow(
                owner_id=self.id,
                template_id=template_id,
                rolled=dict(rolled or {}),
                enchants=dict(enchants or {}),
            )
            session.add(row)
            await session.flush()
            return self._to_instance(row)

    async def set_enchant_level(self, instance_id: int, enchant_id: str, level: int) -> ItemInstance:
        """Set an enchant's level on an instance this player owns (level 0 removes it)."""
        async with get_database().session() as session:
            row = await session.get(ItemInstanceRow, instance_id)
            if row is None or row.owner_id != self.id:
                raise ValueError("You don't own that item.")
            enchants = dict(row.enchants or {})
            if level <= 0:
                enchants.pop(enchant_id, None)
            else:
                enchants[enchant_id] = level
            row.enchants = enchants  # reassign so the JSON change is detected
            return self._to_instance(row)

    async def update_pethouse(self, change: Callable[[Pethouse], T]) -> T:
        """Read-modify-write the pet house inside one transaction (so two clicks can't both win)."""
        async with get_database().session() as session:
            row = await session.get(UserRow, self.id)
            house = Pethouse.model_validate(row.pethouse or {})
            result = change(house)
            row.pethouse = house.model_dump()
        await self.refresh()
        return result

    async def change_template(self, instance_id: int, old: str, new: str) -> bool:
        """Turn one of this player's tools into another kind (an upgrade), keeping its enchants and rolls.
        Only happens if it is still `old`, so a double click can't upgrade twice. Returns whether it changed."""
        async with get_database().session() as session:
            result = await session.execute(
                update(ItemInstanceRow)
                .where(ItemInstanceRow.id == instance_id, ItemInstanceRow.owner_id == self.id,
                       ItemInstanceRow.template_id == old)
                .values(template_id=new)
            )
            return result.rowcount == 1

    async def transfer_instance(self, instance_id: int, to: "User") -> None:
        """Give an instance to another player (and unequip it everywhere)."""
        async with get_database().session() as session:
            result = await session.execute(
                update(ItemInstanceRow)
                .where(ItemInstanceRow.id == instance_id, ItemInstanceRow.owner_id == self.id)
                .values(owner_id=to.id)
            )
            if result.rowcount == 0:
                raise ValueError("You don't own that item.")
            await session.execute(
                update(SkillRow)
                .where(SkillRow.equipped_instance_id == instance_id)
                .values(equipped_instance_id=None)
            )

    async def equip(self, skill: str, instance_id: int | None) -> None:
        """Equip one of this player's instances for a skill (None unequips)."""
        async with get_database().session() as session:
            if instance_id is not None:
                row = await session.get(ItemInstanceRow, instance_id)
                if row is None or row.owner_id != self.id:
                    raise ValueError("You don't own that item.")
            await session.execute(
                sqlite_insert(SkillRow)
                .values(user_id=self.id, skill=skill, xp=0, data={}, equipped_instance_id=instance_id)
                .on_conflict_do_update(
                    index_elements=["user_id", "skill"], set_={"equipped_instance_id": instance_id}
                )
            )

    async def equipped_instance(self, skill: str) -> ItemInstance | None:
        """The tool equipped for `skill`, if any."""
        equipped = (await self.skill(skill)).equipped_instance_id
        return await self.instance(equipped) if equipped is not None else None

    # --- cooldowns -----------------------------------------------------------------------
    @staticmethod
    def _cd_column(command: Cooldowns):
        return getattr(UserRow, f"{command.name.lower()}_cooldown")

    def get_cooldown(self, command: Cooldowns) -> float:
        return getattr(self._s, f"{command.name.lower()}_cooldown")

    async def set_cooldown(self, command: Cooldowns) -> None:
        await self._update(**{f"{command.name.lower()}_cooldown": time.time()})

    async def reset_cooldowns(self) -> None:
        await self._update(work_cooldown=0, daily_cooldown=0, weekly_cooldown=0)

    async def refresh_cooldowns(self, *commands: Cooldowns) -> None:
        """Make these commands ready again (e.g. after an agricultural anomaly)."""
        await self._update(**{f"{c.name.lower()}_cooldown": 0 for c in commands})

    async def claim_cooldown(self, command: Cooldowns) -> bool:
        """Atomically start `command`'s cooldown if it has elapsed.

        Returns False if it was still on cooldown. Use this (not get_cooldown + set_cooldown) for
        rewards, so stale buttons or two simultaneous commands cannot both pay out.
        """
        now = time.time()
        column = self._cd_column(command)
        return await self._update(
            column <= now - command.value * 3600,
            **{f"{command.name.lower()}_cooldown": now},
        )

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
        xp_bar = emojis.get("xp_bar_left")
        xp_bar_size = 10
        filled = int(ratio * xp_bar_size)
        xp_bar += emojis.get("xp_bar_full", "🟩") * filled
        xp_bar += emojis.get("xp_bar_empty", "⬛") * (xp_bar_size - filled)
        xp_bar += emojis.get("xp_bar_right")
        return xp_bar
