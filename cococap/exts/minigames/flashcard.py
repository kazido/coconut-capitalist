from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class FlashcardCog(commands.Cog):
    """Solve a sum for luckbucks. The game itself lives in the /play hub."""

    @app_commands.command(name="flashcard", description="Solve a sum for luckbucks.")
    async def flashcard(self, interaction: Interaction):
        await open_screen(interaction, "flashcard")


async def setup(bot):
    await bot.add_cog(FlashcardCog())
