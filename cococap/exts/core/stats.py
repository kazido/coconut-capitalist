from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class Stats(commands.Cog):
    """Check out those stats!"""

    @app_commands.command(name="stats", description="Number go up man happy.")
    async def stats(self, interaction: Interaction):
        """Display your various metrics."""
        await open_screen(interaction, "stats")


async def setup(bot):
    await bot.add_cog(Stats())
