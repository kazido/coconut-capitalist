from cogs.ErrorHandler import registered
from ClassLibrary import *

class InventoryCog(commands.Cog, name='Inventory'):
    """Check out all the useful items you own."""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @commands.command(name="Inventory", aliases=["inv"], description="Check your inventory!", brief="-inventory")
    async def inventory(self, ctx):
        # User info
        user = User(ctx)
        inventory = Inventory(ctx)

        embed = discord.Embed(
            title=f"{ctx.author.name}'s Inventory",
            description="Testing description. Seeds are not stored here.",
            color=discord.Color.from_rgb(153, 176, 162)
        )
        for x in await inventory.get():
            embed.add_field(name=x['item'].replace('_', ' '), value=x['quantity'])
        embed.set_footer(text="Test footer")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(InventoryCog(bot))