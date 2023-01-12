import asyncio
from random import randint

from discord.ext import commands
# from ClassLibrary import *
from exts.ErrorHandler import registered


class FishingCog(commands.Cog, name='Fishing'):
    """Fish to fill your collection book and find treasure!"""

    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(FishingCog(bot))
