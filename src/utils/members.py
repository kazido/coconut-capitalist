import discord
import peewee

from src.models import Users, Backrefs
from src.entity_models import DataRanks
from src.utils.items import get_entity

from logging import getLogger
from playhouse.shortcuts import model_to_dict

from pprint import pprint

log = getLogger(__name__)
log.setLevel(20)


class UserDoesNotExist(Exception):
    pass


def _sanitize_user_data(user_data):
    related_fields = [
        "foraging",
        "farming",
        "fishing",
        "combat",
        "mining",
        "settings",
        "cooldowns",
    ]
    for field, value in user_data.items():
        if field in related_fields:
            value = value[0]
            user_data[field] = value
    return user_data


def get_user_data(user_id: int, backrefs: bool = False):
    """Retrieve an user by ID."""
    user, created = Users.get_or_create(user_id=user_id)

    # Create rows where needed if user is new
    if created:
        log.info(f"New user! Creating rows...")
        for data in Backrefs:
            data.value.create(user_id=user_id)

    data = model_to_dict(user, backrefs=backrefs)
    return _sanitize_user_data(data)


def set_user_field(user_id: int, field, value):
    """Set the field of an entity"""
    if not hasattr(Users, field):
        raise ValueError(f"Field '{field}' does not exist in model {Users.__name__}")
    updated_rows = Users.set_by_id(user_id, {field: value})
    if updated_rows:
        return updated_rows
    raise UserDoesNotExist(f"No {Users.__name__} found with ID {user_id}")


def get_user_tool(user_id: int, skill: str):
    """Retrieve information about the tool that a user has equipped for specified skill."""
    user = get_user_data(user_id, backrefs=True)
    user_tool_id = user[skill]['tool_id']['item_id']['item_id']
    user_tool = get_entity(user_id, user_tool_id, backrefs=True)
    return user_tool


def get_user_rank(user_id: int, interaction: discord.Interaction) -> DataRanks:
    """Retrieve the corresponding rank of a user based on their roles in a Discord guild."""
    guild_roles = interaction.guild.roles
    user = discord.utils.get(interaction.guild.members, id=user_id)

    for rank in DataRanks.select():
        discord_role = discord.utils.get(guild_roles, id=rank.rank_id)

        # Check to see if the user has any matching role in discord
        if discord_role in user.roles:
            rank_data = model_to_dict(rank)
            return rank_data


def get_user_name(user_id: int) -> str:
    """Retrieve the display name or name of the entity."""
    try:
        user = Users.get_by_id(user_id)
        return getattr(user, "name", None)
    except peewee.DoesNotExist:
        raise UserDoesNotExist(f"No {Users.__name__} found with ID {user_id}")


def update_user_name(user: discord.Member) -> None:
    """Compares the name in the table with the name in discord
    and updates the table if they are not the same"""
    table_name = get_user_name(user.id)
    if table_name != user.display_name:
        set_user_field(user.id, "name", user.display_name)
        log.info(f"Updating user name to {user.display_name}")


def start_user_game(user_id: int):
    set_user_field(user_id, "in_game", True)
    log.info(f"Started game for user with ID {user_id}")


def end_user_game(user_id: int):
    set_user_field(user_id, "in_game", False)
    log.info(f"Ended game for user with ID {user_id}")
