"""The level-up popup (one per click): an embed with the skill icon, the new level and an XP bar, sent only to the player with Share and Close
buttons (`ui/popup.py`). The navigator calls `check` after every click, so no skill screen has to know about it."""

import logging

import discord

from cococap import emojis
from cococap.ui import popup
from cococap.registry import get_registry
from cococap.services import pets
from cococap.ui.components import xp_bar
from cococap.user import User

log = logging.getLogger(__name__)

SKILLS = tuple(emojis.SKILL_ICONS)


PET = "pet:"  # the key of the active pet in a snapshot (so a pet level-up rides in the same notice)


async def snapshot(user: User) -> dict[str, int]:
    """Every skill's level right now, plus the active pet's (key `pet:<id>`)."""
    levels = {name: User.xp_to_level((await user.skill(name)).xp) for name in SKILLS}
    house = user.pethouse
    if house.active in house.pets:
        reg = get_registry()
        levels[PET + house.active] = pets.pet_level(house.pets[house.active].xp, reg.pets[house.active].rarity, reg)
    return levels


def message(skill: str, old: int, new: int, xp: int) -> str:
    """The text for one skill (separate from sending it so it can be tested). A jump over several levels is ONE line: `level up! 1 -> 5`."""
    overflow, needed = User.xp_for_next_level(xp)
    fraction = overflow / needed if needed else 0
    return (  # one line: icon, name, old -> new, a short bar and what is left
        f"{emojis.ui('star', '🎉')} {emojis.skill(skill)} **{skill.title()}** level up! **{old} -> {new}**  "
        f"{xp_bar(fraction, 6)} {overflow:,}/{needed:,} xp to level {new + 1}"
    )


def pet_message(pet_id: str, old: int, new: int, xp: int, registry=None) -> str:
    """The same one-line notice for the active pet (it rides in the player's own level-up popup)."""
    reg = registry or get_registry()
    pet = reg.pets[pet_id]
    top = new >= reg.economy.pets.max_level
    low, high = pets.level_xp(new, pet.rarity, reg), pets.level_xp(new + 1, pet.rarity, reg)
    fraction = 1.0 if top or high <= low else (xp - low) / (high - low)
    tail = "max level" if top else f"{xp - low:,}/{high - low:,} xp to level {new + 1}"
    return f"{emojis.icon('pet', '🐾')} {pet.emoji} **{pet.name}** level up! **{old} -> {new}**  {xp_bar(fraction, 6)} {tail}"


async def check(interaction: discord.Interaction, user: User, seen: dict[str, int] | None) -> dict[str, int]:
    """Compare levels with the last look and send ONE notice (one block per skill that went up, old -> new level). Returns the new levels to
    remember. A failure here must never break the click that caused it."""
    try:
        now = await snapshot(user)
        if seen is None:
            return now
        blocks = []
        for name, level in now.items():
            if level <= seen.get(name, level):
                continue
            if name.startswith(PET):
                blocks.append(pet_message(name[len(PET):], seen[name], level, user.pethouse.pets[name[len(PET):]].xp))
            else:
                blocks.append(message(name, seen[name], level, (await user.skill(name)).xp))
        if blocks:
            # Not ephemeral: the level-up notice is public so others can see it (rare drops stay private).
            await popup.send(interaction, discord.Embed(title="Level up!", description="\n\n".join(blocks), colour=discord.Colour.gold()), ephemeral=False)
        return now
    except Exception:  # a missing notification is better than a broken click
        log.exception("level-up check failed")
        return seen or {}
