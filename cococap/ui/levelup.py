"""The level-up notification (shown once, after the xp settles): a small message with the skill icon, the new level and an XP bar, sent only to the player and
removed after a few seconds. The navigator calls `check` after every click, so no skill screen has to know about it."""

import asyncio
import logging

import discord

from cococap import emojis
from cococap.ui.components import xp_bar
from cococap.user import User

log = logging.getLogger(__name__)

LIFETIME = 8  # seconds the notification stays before it deletes itself
SETTLE = 2.5  # seconds without a new click before the level-up is announced (so a run of level-ups shows once, at the final level)
SKILLS = tuple(emojis.SKILL_ICONS)


async def snapshot(user: User) -> dict[str, int]:
    """Every skill's level right now."""
    return {name: User.xp_to_level((await user.skill(name)).xp) for name in SKILLS}


def message(skill: str, level: int, xp: int) -> str:
    """The text of one notification (separate from sending it so it can be tested)."""
    overflow, needed = User.xp_for_next_level(xp)
    fraction = overflow / needed if needed else 0
    return (
        f"{emojis.ui('star', '🎉')} {emojis.skill(skill)} **{skill.title()}** reached **level {level}**!\n"
        f"{xp_bar(fraction, 10)}  {overflow:,} / {needed:,} xp to level {level + 1}"
    )


_baseline: dict[int, dict[str, int]] = {}  # user id -> levels before the level-ups still waiting to be announced
_waiting: dict[int, asyncio.Task] = {}  # user id -> the timer that announces them


async def _announce(interaction: discord.Interaction, user: User, uid: int) -> None:
    """After the xp has stopped coming in for SETTLE seconds, say each skill's FINAL level once (a burst of level-ups is one message)."""
    try:
        await asyncio.sleep(SETTLE)
        before = _baseline.pop(uid, {})
        _waiting.pop(uid, None)
        await user.refresh()
        for name, level in (await snapshot(user)).items():
            if level > before.get(name, level):
                xp = (await user.skill(name)).xp
                await interaction.followup.send(message(name, level, xp), ephemeral=True, delete_after=LIFETIME)
    except asyncio.CancelledError:
        raise  # a newer click restarted the timer
    except Exception:  # a missing notification is better than a broken click
        log.exception("level-up announcement failed")


async def flush(user_id: int) -> None:
    """Wait for the pending announcement of this player, if any (tests use it; the bot never needs to)."""
    task = _waiting.get(user_id)
    if task is not None:
        await asyncio.gather(task, return_exceptions=True)


async def check(interaction: discord.Interaction, user: User, seen: dict[str, int] | None) -> dict[str, int]:
    """Compare levels with the last look. A level-up (or more xp while one is waiting) restarts a short timer; when it ends, ONE notification per
    skill shows the final level. Returns the new levels to remember. A failure here must never break the click that caused it."""
    try:
        now = await snapshot(user)
        if seen is None:
            return now
        uid = user.id
        if uid not in _baseline and any(level > seen.get(name, level) for name, level in now.items()):
            _baseline[uid] = dict(seen)
        if uid in _baseline:  # something is waiting: (re)start the settle timer
            if old := _waiting.get(uid):
                old.cancel()
            _waiting[uid] = asyncio.create_task(_announce(interaction, user, uid))
        return now
    except Exception:
        log.exception("level-up check failed")
        return seen or {}
