from discord.ext import commands
from discord import app_commands
import discord


class UnscrambleCog(commands.Cog, name='Unscramble'):
    """Unscramble a scrambled word for some bits."""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree


async def setup(bot):
    await bot.add_cog(UnscrambleCog(bot))