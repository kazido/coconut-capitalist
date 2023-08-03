import discord

from discord import utils
from src.models import DataRanks
from logging import getLogger

log = getLogger(__name__)


def retrieve_rank(user_id, interaction: discord.Interaction):
    """Retrieve the corresponding rank of a user based on their roles in a Discord guild."""
    guild_roles = interaction.guild.roles
    user = utils.get(interaction.guild.members, id=user_id)
    
    for rank in DataRanks.select():
        discord_role = utils.get(guild_roles, id=rank.rank_id)

        # Check to see if the user has any matching role in discord
        if discord_role in user.roles:
            return rank
