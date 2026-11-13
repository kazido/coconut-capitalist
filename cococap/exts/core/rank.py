from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class RanksCog(commands.Cog):
    """Rank up for a higher wage!"""

    @app_commands.command(name="rank", description="Check your rank and rank up.")
    async def rank(self, interaction: Interaction):
        """Check your current rank and its perks."""
        await open_screen(interaction, "rank")


async def setup(bot):
    await bot.add_cog(RanksCog())
