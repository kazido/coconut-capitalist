"""SQLAlchemy table definitions (the whole database schema lives in this file).

Money-like columns carry CHECK constraints so the database itself refuses to go negative, no matter
which code path touches them.
"""

import time

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    BigInteger,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("purse >= 0", name="purse_non_negative"),
        CheckConstraint("bank >= 0", name="bank_non_negative"),
        CheckConstraint("tokens >= 0", name="tokens_non_negative"),
        CheckConstraint("luckbucks >= 0", name="luckbucks_non_negative"),
    )

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String, default="unnamed user")
    rank: Mapped[int] = mapped_column(Integer, default=0)
    purse: Mapped[int] = mapped_column(BigInteger, default=1000)  # bits on hand
    bank: Mapped[int] = mapped_column(BigInteger, default=0)  # bits that earn interest
    tokens: Mapped[int] = mapped_column(BigInteger, default=0)  # only used to rank up
    luckbucks: Mapped[int] = mapped_column(BigInteger, default=100)  # fun currency: minigames, casino, cosmetics
    # Unix timestamps of the last claim (see cococap.user.Cooldowns)
    work_cooldown: Mapped[float] = mapped_column(Float, default=0)
    daily_cooldown: Mapped[float] = mapped_column(Float, default=0)
    weekly_cooldown: Mapped[float] = mapped_column(Float, default=0)
    last_token_roll: Mapped[int] = mapped_column(BigInteger, default=0)  # the hour (since 1970) of the last token roll
    last_active: Mapped[float] = mapped_column(Float, default=time.time)  # when they last pressed anything (see services/activity)
    # Validated by cococap.models.settings.Settings / pethouse.Pethouse
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    pethouse: Mapped[dict] = mapped_column(JSON, default=dict)


class StatRow(Base):
    """One counter per (user, statistic name), e.g. ('hl_wins', 12)."""

    __tablename__ = "user_stats"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0)


class SkillRow(Base):
    """A user's progress in one skill. xp/equipped_tool are columns (queried for leaderboards);
    everything skill-specific (farm plots, reactor, quest book, ...) is validated JSON."""

    __tablename__ = "user_skills"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True
    )
    skill: Mapped[str] = mapped_column(String, primary_key=True)
    xp: Mapped[int] = mapped_column(BigInteger, default=0)
    # The unique tool currently equipped for this skill (see ItemInstanceRow).
    equipped_instance_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("item_instances.id", ondelete="SET NULL"), nullable=True
    )
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class ItemInstanceRow(Base):
    """A unique object a player owns (a tool). Base stats come from the registry template at read
    time; only what is unique to *this* object is stored: random rolls and enchant levels."""

    __tablename__ = "item_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[str] = mapped_column(String)
    rolled: Mapped[dict] = mapped_column(JSON, default=dict)  # {"power": 3}: fixed at creation
    enchants: Mapped[dict] = mapped_column(JSON, default=dict)  # {"soloist": 1}
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class ItemRow(Base):
    """An inventory stack (empty stacks are deleted, never left at 0)."""

    __tablename__ = "user_items"
    __table_args__ = (CheckConstraint("quantity >= 0", name="quantity_non_negative"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(String, primary_key=True)
    quantity: Mapped[int] = mapped_column(BigInteger)


class PartyRow(Base):
    __tablename__ = "parties"

    party_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.discord_id"))


class PartyMemberRow(Base):
    """Membership. user_id is the primary key, so a user can be in at most one party."""

    __tablename__ = "party_members"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True
    )
    party_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parties.party_id", ondelete="CASCADE"), index=True
    )


class MegadropRow(Base):
    """Single-row table (id = 1) holding the community megadrop pot."""

    __tablename__ = "megadrop"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)
    total_drops: Mapped[int] = mapped_column(Integer, default=0)
    total_drops_missed: Mapped[int] = mapped_column(Integer, default=0)
    counter: Mapped[int] = mapped_column(Integer, default=0)
    times_missed: Mapped[int] = mapped_column(Integer, default=0)
    last_winner: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date_started: Mapped[str] = mapped_column(String, default="")


class CommunityTreeRow(Base):
    """The community tree of one hour (`window` = unix hour). Created by whoever first looks at it."""

    __tablename__ = "community_trees"
    __table_args__ = (
        CheckConstraint("hp >= 0 AND hp <= max_hp", name="hp_in_range"),
        CheckConstraint("status IN ('growing', 'felled', 'expired')", name="status_known"),
    )

    window: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    zone: Mapped[int] = mapped_column(Integer)
    max_hp: Mapped[int] = mapped_column(Integer)
    hp: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="growing")
    opens_at: Mapped[float] = mapped_column(Float)
    closes_at: Mapped[float] = mapped_column(Float)
    settled: Mapped[bool] = mapped_column(Boolean, default=False)  # rewards have been worked out


class TreeChopRow(Base):
    """How much hp of a community tree one player has chopped."""

    __tablename__ = "tree_chops"
    __table_args__ = (CheckConstraint("damage >= 0", name="damage_non_negative"),)

    window: Mapped[int] = mapped_column(
        Integer, ForeignKey("community_trees.window", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True
    )
    damage: Mapped[int] = mapped_column(Integer, default=0)


class TreeRewardRow(Base):
    """A player's share of a finished community tree, waiting to be claimed from their own panel."""

    __tablename__ = "tree_rewards"

    window: Mapped[int] = mapped_column(
        Integer, ForeignKey("community_trees.window", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), primary_key=True
    )
    damage: Mapped[int] = mapped_column(Integer)
    felled: Mapped[bool] = mapped_column(Boolean)  # False: the tree fell over unfinished (a consolation prize)
    drops: Mapped[dict] = mapped_column(JSON, default=dict)
    bits: Mapped[int] = mapped_column(BigInteger, default=0)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)


class CommunityStateRow(Base):
    """Shared, server-wide state kept as one small JSON document per key (the fishing community book, each
    month's community quests). Every change is a read-modify-write inside one serialized transaction."""

    __tablename__ = "community_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
