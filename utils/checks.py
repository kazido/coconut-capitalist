import cococap
import discord

from pydis_core.utils import scheduling
from typing import Sequence
from logging import getLogger


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
