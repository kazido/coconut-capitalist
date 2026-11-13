from discord import Interaction, app_commands
from discord.ext import commands

from cococap.screens import open_screen


class Settings(commands.Cog):
    """Change your settings."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Change your account settings.")
    async def settings(self, interaction: Interaction):
        await open_screen(interaction, "settings")


async def setup(bot):
    await bot.add_cog(Settings(bot))
