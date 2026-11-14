from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class PetsCog(commands.Cog, name="Pets"):
    """Hatch, feed and choose pets. The game itself lives in the /play hub."""

    @app_commands.command(name="pets", description="Open your Pet House.")
    async def pets(self, interaction: Interaction):
        await open_screen(interaction, "pets")


async def setup(bot):
    await bot.add_cog(PetsCog())
