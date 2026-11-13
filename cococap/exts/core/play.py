from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class Play(commands.Cog):
    """The front door: one message that links to everything in the game."""

    @app_commands.command(name="play", description="Open the game menu.")
    async def play(self, interaction: Interaction):
        await open_screen(interaction, "home")


async def setup(bot):
    await bot.add_cog(Play())
