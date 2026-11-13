from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class ForagingCog(commands.Cog, name="Foraging"):
    """Chop trees alone, or join the hourly community tree. The game itself lives in the /play hub."""

    @app_commands.command(name="chop", description="Chop down some trees.")
    async def chop(self, interaction: Interaction):
        await open_screen(interaction, "forage")


async def setup(bot):
    await bot.add_cog(ForagingCog())
