"""The level-up notification: a small message with the skill icon, the new level and an XP bar, sent only to the player and
removed after a few seconds. The navigator calls `check` after every click, so no skill screen has to know about it."""

import logging

import discord

from cococap import emojis
from cococap.ui.components import xp_bar
from cococap.user import User

log = logging.getLogger(__name__)

LIFETIME = 8  # seconds the notification stays before it deletes itself
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


async def check(interaction: discord.Interaction, user: User, seen: dict[str, int] | None) -> dict[str, int]:
    """Compare levels with the last look; notify for every skill that went up. Returns the new levels to remember.
    A failure here must never break the click that caused it."""
    try:
        now = await snapshot(user)
        if seen is None:
            return now
        for name, level in now.items():
            if level > seen.get(name, level):
                xp = (await user.skill(name)).xp
                await interaction.followup.send(message(name, level, xp), ephemeral=True, delete_after=LIFETIME)
        return now
    except Exception:  # a missing notification is better than a broken click
        log.exception("level-up check failed")
        return seen or {}
