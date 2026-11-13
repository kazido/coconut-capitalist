from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class UnscrambleCog(commands.Cog):
    """Unscramble a word for luckbucks. The game itself lives in the /play hub."""

    @app_commands.command(name="unscramble", description="Unscramble a word for luckbucks.")
    async def unscramble(self, interaction: Interaction):
        await open_screen(interaction, "unscramble")


async def setup(bot):
    await bot.add_cog(UnscrambleCog())
