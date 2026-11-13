from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class MiningCog(commands.Cog, name="Mining"):
    """Dig for ores and gems; upgrade your reactor. The game itself lives in the /play hub."""

    @app_commands.command(name="mine", description="Head down into the mines.")
    async def mine(self, interaction: Interaction):
        await open_screen(interaction, "mining")


async def setup(bot):
    await bot.add_cog(MiningCog())
