from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class FishingCog(commands.Cog, name="Fishing"):
    """Cast a line and reel in fish. The game itself lives in the /play hub."""

    @app_commands.command(name="fish", description="Cast a line and catch some fish.")
    async def fish(self, interaction: Interaction):
        await open_screen(interaction, "fish")


async def setup(bot):
    await bot.add_cog(FishingCog())
