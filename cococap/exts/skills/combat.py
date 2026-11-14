from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class CombatCog(commands.Cog, name="Combat"):
    """Turn-based fights. The game itself lives in the /play hub."""

    @app_commands.command(name="fight", description="Fight monsters in turn-based combat.")
    async def fight(self, interaction: Interaction):
        await open_screen(interaction, "fight")


async def setup(bot):
    await bot.add_cog(CombatCog())
