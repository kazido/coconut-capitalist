import cococap
import discord
import random

from datetime import datetime
from discord import Interaction
from discord.colour import Colour
from discord.types.embed import EmbedType
from pydis_core.utils import scheduling
from typing import Any, Sequence
from logging import getLogger

from cococap.constants import SUCCESS_REPLIES, FAILURE_REPLIES, ERROR_REPLIES


log = getLogger(__name__)


def reaction_check(
    reaction: discord.Reaction,
    user: discord.abc.User,
    *,
    message_id: int,
    allowed_emoji: Sequence[str],
    allowed_users: Sequence[int],
    allow_mods: bool = True,
) -> bool:
    """
    Check if a reaction's emoji and author are allowed and the message is `message_id`.

    If the user is not allowed, remove the reaction. Ignore reactions made by the bot.
    If `allow_mods` is True, allow users with moderator roles even if they're not in `allowed_users`.
    """
    log.debug(f"Began reaction check for {user}")
    right_reaction = (
        user != cococap.instance.user
        and reaction.message.id == message_id
        and str(reaction.emoji) in allowed_emoji
    )
    if not right_reaction:
        log.debug(f"Improper reaction by {user} on {reaction.message.id}.")
        return False

    # is_moderator = allow_mods and any(
    #     role.id in MODERATION_ROLES for role in getattr(user, "roles", [])
    # )

    if user.id in allowed_users:
        log.info(f"Allowed reaction {reaction} by {user} on {reaction.message.id}.")
        return True
    else:
        log.info(
            f"Removing reaction {reaction} by {user} on {reaction.message.id}: disallowed user."
        )
        scheduling.create_task(
            reaction.message.remove_reaction(reaction.emoji, user),
            suppressed_exceptions=(discord.HTTPException,),
            name=f"remove_reaction-{reaction}-{reaction.message.id}-{user}",
        )
        return False


async def button_check(interaction: Interaction, allowed_users: list[int]):
    if interaction.user.id in allowed_users:
        log.debug(f"{interaction.user.id} ({interaction.user.name}) passed button check.")
        return True
    embed = Cembed(
        title="Who do you think you are?",
        desc="This isn't your button... Don't hit it.",
        color=discord.Color.red(),
        interaction=interaction,
        activity="mischieving",
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    log.debug(f"{interaction.user.id} ({interaction.user.name}) failed button check.")
    return False


class Cembed(discord.Embed):
    def __init__(
        self,
        *,
        color: int | Colour | None = None,
        colour: int | Colour | None = None,
        title: Any | None = None,
        type: EmbedType = "rich",
        url: Any | None = None,
        desc: Any | None = None,
        description: Any | None = None,
        timestamp: datetime | None = None,
        interaction: Interaction | None = None,
        activity: str = ":)",
    ):
        if colour is not None:
            color = colour
        if description is not None:
            desc = description
        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            description=desc,
            timestamp=timestamp,
        )
        if interaction:
            self.set_author(
                name=f"{interaction.user.name} - {activity}",
                icon_url=interaction.user.display_avatar,
            )


class SuccessEmbed(Cembed):
    def __init__(
        self,
        *,
        color=discord.Color.green(),
        title=random.choice(SUCCESS_REPLIES),
        type="rich",
        url=None,
        desc=None,
        timestamp=None,
        interaction=None,
        activity=":D",
    ):

        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            desc=desc,
            timestamp=timestamp,
            interaction=interaction,
            activity=activity,
        )


class FailureEmbed(Cembed):
    def __init__(
        self,
        *,
        color=discord.Color.dark_gray(),
        title=random.choice(FAILURE_REPLIES),
        type="rich",
        url=None,
        desc=None,
        timestamp=None,
        interaction=None,
        activity=":(",
    ):

        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            desc=desc,
            timestamp=timestamp,
            interaction=interaction,
            activity=activity,
        )


class ErrorEmbed(Cembed):
    def __init__(
        self,
        *,
        color=discord.Color.red(),
        title=random.choice(ERROR_REPLIES),
        type="rich",
        url=None,
        desc=None,
        timestamp=None,
        interaction=None,
        activity=":)",
    ):

        super().__init__(
            color=color,
            title=title,
            type=type,
            url=url,
            desc=desc,
            timestamp=timestamp,
            interaction=interaction,
            activity=activity,
        )
