"""Who is playing, and taking idle players out of parties.

Every button press and command stamps the player's ``last_active``. A sweep (run every few minutes by the bot) removes party
members who have been idle longer than ``party_idle_hours``, so a party's size, and the xp bonus that comes with it, is
about the people actually playing. Nothing is stored per command: one number per player, written at most once a minute.
"""

import random
import time
from dataclasses import dataclass

from sqlalchemy import delete, select, update

from cococap import emojis
from cococap.db import get_database
from cococap.db.tables import PartyMemberRow, PartyRow, SkillRow, UserRow
from cococap.registry import Registry, get_registry

TOUCH_EVERY = 60.0  # seconds: pressing buttons all day writes to the database once a minute at most
_last_written: dict[int, float] = {}


async def touch(user_id: int, now: float | None = None, registry: Registry | None = None) -> None:
    """Note that `user_id` just did something (and maybe find a token). Players who have never been seen are left alone (no row is made)."""
    now = time.time() if now is None else now
    if now - _last_written.get(user_id, 0.0) < TOUCH_EVERY:
        return
    _last_written[user_id] = now
    async with get_database().session() as session:
        await session.execute(update(UserRow).where(UserRow.discord_id == user_id).values(last_active=now))
    if await roll_token(user_id, now, registry):
        notices.setdefault(user_id, []).append(f"{emojis.icon('tokens', '🪙')} You found a **token** while you were out and about!")


notices: dict[int, list[str]] = {}  # things to tell a player the next time a screen is drawn (e.g. a token they found)


def pop_notices(user_id: int) -> list[str]:
    return notices.pop(user_id, [])


async def roll_token(user_id: int, now: float, registry: Registry | None = None) -> bool:
    """Once an hour of play, a chance of one token. The roll is fixed by (player, hour), and the hour is written first in one
    statement, so a second press, a second process or a restart cannot roll it again."""
    chance = (registry or get_registry()).economy.token_drop_chance
    hour = int(now // 3600)
    async with get_database().session() as session:
        claimed = await session.execute(
            update(UserRow).where(UserRow.discord_id == user_id, UserRow.last_token_roll < hour).values(last_token_roll=hour))
        if claimed.rowcount != 1 or random.Random(f"token:{user_id}:{hour}").random() >= chance:
            return False
        await session.execute(update(UserRow).where(UserRow.discord_id == user_id).values(tokens=UserRow.tokens + 1))
    from cococap.user import User

    user = await User.get(user_id)
    await user.inc_stat("tokens_earned")
    return True


@dataclass(frozen=True)
class Kicked:
    user_id: int
    party_id: int
    disbanded: bool  # the party had nobody active left, so it is gone
    new_owner: int | None  # who the party went to, if the kicked player owned it


async def sweep(now: float | None = None, registry: Registry | None = None) -> list[Kicked]:
    """Take everybody idle out of their party. One transaction, so a member cannot be half-removed."""
    now = time.time() if now is None else now
    cutoff = now - (registry or get_registry()).economy.party_idle_hours * 3600
    kicked: list[Kicked] = []
    async with get_database().session() as session:
        idle = (await session.execute(
            select(PartyMemberRow.user_id, PartyMemberRow.party_id)
            .join(UserRow, UserRow.discord_id == PartyMemberRow.user_id)
            .where(UserRow.last_active < cutoff)
        )).all()
        for party_id in sorted({p for _, p in idle}):
            gone = {u for u, p in idle if p == party_id}
            owner = await session.scalar(select(PartyRow.owner_id).where(PartyRow.party_id == party_id))
            await session.execute(delete(PartyMemberRow).where(PartyMemberRow.user_id.in_(gone)))
            left = (await session.execute(
                select(PartyMemberRow.user_id, UserRow.last_active)
                .join(UserRow, UserRow.discord_id == PartyMemberRow.user_id)
                .where(PartyMemberRow.party_id == party_id)
                .order_by(UserRow.last_active.desc())
            )).all()
            new_owner = None
            if not left:
                await session.execute(delete(PartyRow).where(PartyRow.party_id == party_id))
            elif owner in gone:
                new_owner = left[0][0]
                await session.execute(update(PartyRow).where(PartyRow.party_id == party_id).values(owner_id=new_owner))
            kicked += [Kicked(u, party_id, not left, new_owner if u == owner else None) for u in sorted(gone)]
    return kicked


async def recent_players(skills: tuple[str, ...], days: float, now: float | None = None) -> tuple[int, float]:
    """(how many players pressed something in the last `days`, their average level across `skills`). Used to size the weekly community shipment."""
    from cococap.user import User

    now = time.time() if now is None else now
    async with get_database().session() as session:
        ids = (await session.execute(select(UserRow.discord_id).where(UserRow.last_active >= now - days * 86400))).scalars().all()
        if not ids:
            return 0, 0.0
        xps = (await session.execute(select(SkillRow.user_id, SkillRow.xp).where(SkillRow.user_id.in_(ids), SkillRow.skill.in_(skills)))).all()
    levels = {uid: len(skills) for uid in ids}  # (a skill you have not started counts as level 1)
    for uid, xp in xps:
        levels[uid] += User.xp_to_level(xp) - 1
    return len(ids), sum(levels.values()) / len(ids) / len(skills)
