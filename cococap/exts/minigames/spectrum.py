from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class SequenceCog(commands.Cog):
    """Remember the pattern for luckbucks. The game itself lives in the /play hub."""

    @app_commands.command(name="sequence", description="Remember the pattern for luckbucks.")
    async def sequence(self, interaction: Interaction):
        await open_screen(interaction, "sequence")


async def setup(bot):
    await bot.add_cog(SequenceCog())
