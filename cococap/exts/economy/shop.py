import discord
from discord import app_commands
from discord.ext import commands

from cococap.registry import get_registry
from cococap.screens import open_screen
from cococap.services import shop as shop_service
from cococap.services.shop import ShopError
from cococap.user import User
from cococap.errors import CustomError
from utils.custom_embeds import CustomEmbed
from utils.items.items import _matching, buyable_autocomplete, construct_embed
from utils.menus import Menu, MenuHandler, PaginationMenu

class ShopCog(commands.Cog, name="Shop"):
    """Buy tools, seeds and supplies. Sell what you've gathered."""

    @app_commands.command(name="shop", description="See what's for sale.")
    async def shop(self, interaction: discord.Interaction):
        await open_screen(interaction, "shop")

    @app_commands.command(name="buy", description="Buy something from the shop.")
    @app_commands.describe(item="what to buy", quantity="how many")
    @app_commands.autocomplete(item=buyable_autocomplete)
    async def buy(self, interaction: discord.Interaction, item: str, quantity: int = 1):
        user = await User.get(interaction.user.id)
        try:
            purchase = await shop_service.buy(user, item, quantity)
        except ShopError as e:
            raise CustomError(str(e)) from e
        embed = construct_embed(item, for_shop=True)
        embed.title = f"Purchased {purchase.quantity:,} × {embed.title}"
        embed.set_footer(text=f"Spent {purchase.total:,} bits")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="sell", description="Sell items from your inventory.")
    @app_commands.describe(item="what to sell", quantity="how many")
    async def sell(self, interaction: discord.Interaction, item: str, quantity: int = 1):
        user = await User.get(interaction.user.id)
        try:
            earned = await shop_service.sell(user, item, quantity)
        except ShopError as e:
            raise CustomError(str(e)) from e
        name = get_registry().item(item).name
        await interaction.response.send_message(
            f"Sold {quantity:,} × {name} for **{earned:,}** bits."
        )

    @sell.autocomplete("item")
    async def _sell_autocomplete(self, interaction: discord.Interaction, current: str):
        owned = await (await User.get(interaction.user.id)).items()
        reg = get_registry()
        sellable = [i for i in (reg.find_item(k) for k in owned) if i and i.sellable]
        return _matching(sellable, current)


async def setup(bot):
    await bot.add_cog(ShopCog())
