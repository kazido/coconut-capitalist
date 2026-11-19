"""The level-up popup (one per click): an embed with the skill icon, the new level and an XP bar, sent only to the player with Share and Close
buttons (`ui/popup.py`). The navigator calls `check` after every click, so no skill screen has to know about it."""

import logging

import discord

from cococap import emojis
from cococap.ui import popup
from cococap.ui.components import xp_bar
from cococap.user import User

log = logging.getLogger(__name__)

SKILLS = tuple(emojis.SKILL_ICONS)


async def snapshot(user: User) -> dict[str, int]:
    """Every skill's level right now."""
    return {name: User.xp_to_level((await user.skill(name)).xp) for name in SKILLS}


def message(skill: str, old: int, new: int, xp: int) -> str:
    """The text for one skill (separate from sending it so it can be tested). A jump over several levels is ONE line: `Level up! 1 -> 5`."""
    overflow, needed = User.xp_for_next_level(xp)
    fraction = overflow / needed if needed else 0
    return (
        f"{emojis.ui('star', '🎉')} {emojis.skill(skill)} **{skill.title()}** Level up! **{old} -> {new}**\n"
        f"{xp_bar(fraction, 10)}  {overflow:,} / {needed:,} xp to level {new + 1}"
    )


async def check(interaction: discord.Interaction, user: User, seen: dict[str, int] | None) -> dict[str, int]:
    """Compare levels with the last look and send ONE notice (one block per skill that went up, old -> new level). Returns the new levels to
    remember. A failure here must never break the click that caused it."""
    try:
        now = await snapshot(user)
        if seen is None:
            return now
        blocks = [message(name, seen[name], level, (await user.skill(name)).xp) for name, level in now.items() if level > seen.get(name, level)]
        if blocks:
            await popup.send(interaction, discord.Embed(title="Level up!", description="\n\n".join(blocks), colour=discord.Colour.gold()))
        return now
    except Exception:  # a missing notification is better than a broken click
        log.exception("level-up check failed")
        return seen or {}
