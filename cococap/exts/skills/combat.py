from discord import Interaction, app_commands
from discord.ext import commands
from cococap import emojis



class CombatCog(commands.Cog, name="Combat"):
    """Turn-based fights. The game itself lives in the /play hub."""

    @app_commands.command(name="fight", description="Fight monsters in turn-based combat.")
    async def fight(self, interaction: Interaction):
        await interaction.response.send_message(f"{emojis.icon('sword', '⚔️')} Combat is paused while it gets a rework. Check back soon!", ephemeral=True)


async def setup(bot):
    await bot.add_cog(CombatCog())
