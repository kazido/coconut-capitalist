from discord.ext import commands


class ShipmentCog(commands.Cog, name='Shipment'):
    """Purchase helpful items on your way to the top!"""

    def __init__(self, bot):
        self.bot = bot
        
        


async def setup(bot):
    await bot.add_cog(ShipmentCog(bot))
