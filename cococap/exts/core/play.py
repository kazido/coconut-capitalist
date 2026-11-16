from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen
from cococap.services.shop import claim_starter_tools
from cococap.user import User


class Play(commands.Cog):
    """The front door: one message that links to everything in the game."""

    @app_commands.command(name="play", description="Open the game menu.")
    async def play(self, interaction: Interaction):
        await claim_starter_tools(await User.get(interaction.user.id))  # (a new player starts with the four free tools)
        await open_screen(interaction, "home")


async def setup(bot):
    await bot.add_cog(Play())
