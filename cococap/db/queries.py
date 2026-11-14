"""Queries that span users (leaderboards) and the megadrop singleton."""

from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from . import get_database
from .tables import MegadropRow, SkillRow, StatRow, UserRow

MEGADROP_ID = 1


# --- leaderboards -------------------------------------------------------------------------
@dataclass(frozen=True)
class Entry:
    rank: int  # 1-based position
    discord_id: int
    name: str
    value: int


def _value_expression(category: str):
    """SQL expression (and its filter) that a leaderboard category sorts by."""
    if category == "bits":
        return UserRow.purse
    if category == "luckbucks":
        return UserRow.luckbucks
    raise KeyError(category)


async def leaderboard(category: str, *, limit: int = 10, exclude: int | None = None) -> list[Entry]:
    """Top `limit` players. `category` is "bits", "luckbucks", "skill:<name>" or "stat:<name>".

    `exclude` hides one account (the house) from the board.
    """
    kind, _, arg = category.partition(":")
    if kind == "skill":
        value = SkillRow.xp
        query = select(UserRow.discord_id, UserRow.name, value).join(
            SkillRow, (SkillRow.user_id == UserRow.discord_id) & (SkillRow.skill == arg)
        )
    elif kind == "stat":
        value = StatRow.value
        query = select(UserRow.discord_id, UserRow.name, value).join(
            StatRow, (StatRow.user_id == UserRow.discord_id) & (StatRow.name == arg)
        )
    else:
        value = _value_expression(category)
        query = select(UserRow.discord_id, UserRow.name, value)
    if exclude is not None:
        query = query.where(UserRow.discord_id != exclude)
    query = query.where(value > 0).order_by(value.desc(), UserRow.discord_id).limit(limit)
    async with get_database().session() as session:
        rows = (await session.execute(query)).all()
    return [Entry(i, r[0], r[1], r[2]) for i, r in enumerate(rows, start=1)]


async def position_of(category: str, discord_id: int, *, exclude: int | None = None) -> Entry | None:
    """The caller's own place on a board (for "Your rank: 57"), or None if they have no score."""
    kind, _, arg = category.partition(":")
    async with get_database().session() as session:
        if kind == "skill":
            value = SkillRow.xp
            base = select(UserRow.discord_id, UserRow.name, value).join(
                SkillRow, (SkillRow.user_id == UserRow.discord_id) & (SkillRow.skill == arg)
            )
        elif kind == "stat":
            value = StatRow.value
            base = select(UserRow.discord_id, UserRow.name, value).join(
                StatRow, (StatRow.user_id == UserRow.discord_id) & (StatRow.name == arg)
            )
        else:
            value = _value_expression(category)
            base = select(UserRow.discord_id, UserRow.name, value)
        mine = (await session.execute(base.where(UserRow.discord_id == discord_id))).first()
        if mine is None or mine[2] <= 0:
            return None
        ahead = base.where(value > mine[2])
        if exclude is not None:
            ahead = ahead.where(UserRow.discord_id != exclude)
        count = (await session.execute(select(func.count()).select_from(ahead.subquery()))).scalar_one()
        return Entry(count + 1, mine[0], mine[1], mine[2])


async def bits_in_circulation(*, exclude: int | None = None) -> int:
    query = select(func.coalesce(func.sum(UserRow.purse), 0))
    if exclude is not None:
        query = query.where(UserRow.discord_id != exclude)
    async with get_database().session() as session:
        return (await session.execute(query)).scalar_one()


# --- megadrop -----------------------------------------------------------------------------
async def ensure_megadrop(date_started: str) -> None:
    """Create the megadrop row on a fresh database (no-op if it exists)."""
    async with get_database().session() as session:
        await session.execute(
            sqlite_insert(MegadropRow)
            .values(id=MEGADROP_ID, date_started=date_started)
            .on_conflict_do_nothing(index_elements=["id"])
        )


async def get_megadrop() -> MegadropRow:
    async with get_database().session() as session:
        return await session.get(MegadropRow, MEGADROP_ID)


async def update_megadrop(*, inc: dict[str, int] | None = None, **set_values) -> None:
    """Atomically add `inc` to numeric columns and/or set columns, e.g.
    update_megadrop(inc={"counter": 1}, last_winner=123)."""
    values = dict(set_values)
    for column, amount in (inc or {}).items():
        values[column] = getattr(MegadropRow, column) + amount
    async with get_database().session() as session:
        await session.execute(update(MegadropRow).where(MegadropRow.id == MEGADROP_ID).values(**values))
