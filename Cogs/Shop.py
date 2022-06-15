from Cogs.ErrorHandler import registered
from ClassLibrary import *


class ShopCog(commands.Cog, name='Shop'):
    """Purchase helpful items on your way to the top!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @commands.command(name="Shop", aliases=["buy"], description="Buy helpful items!", brief="-shop")
    async def shop(self, ctx, category: str = None):
        menu_page = discord.Embed(
            title="Shop Select",
            description="Choose which section you would like to shop from!",
            color=discord.Color.teal()
        )
        await ctx.send(embed=menu_page)

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
