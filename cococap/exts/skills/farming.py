from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class FarmingCog(commands.Cog, name="Farming"):
    """Plant seeds, wait for the rain, harvest. The game itself lives in the /play hub."""

    @app_commands.command(name="farm", description="Tend your farm.")
    async def farm(self, interaction: Interaction):
        await open_screen(interaction, "farm")


async def setup(bot):
    await bot.add_cog(FarmingCog())
