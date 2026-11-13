from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class TriviaCog(commands.Cog):
    """Answer trivia for luckbucks. The game itself lives in the /play hub."""

    @app_commands.command(name="trivia", description="Answer trivia for luckbucks.")
    async def trivia(self, interaction: Interaction):
        await open_screen(interaction, "trivia")


async def setup(bot):
    await bot.add_cog(TriviaCog())
