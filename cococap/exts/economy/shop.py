import discord
from discord import app_commands
from discord.ext import commands

from cococap.registry import get_registry
from cococap.services import shop as shop_service
from cococap.services.shop import ShopError
from cococap.user import User
from cococap.errors import CustomError
from utils.custom_embeds import CustomEmbed
from utils.items.items import _matching, buyable_autocomplete, construct_embed
from utils.menus import Menu, MenuHandler, PaginationMenu

PER_PAGE = 8


def shop_pages() -> list[list[str]]:
    """The shop listing, grouped by skill then price, split into pages of lines."""
    items = sorted(get_registry().shop_items(), key=lambda i: (i.skill or "", i.price, i.name))
    lines = [f"{i.emoji or '▫️'} **{i.name}**: {i.price:,} bits (`{i.id}`)" for i in items]
    return [lines[n : n + PER_PAGE] for n in range(0, len(lines), PER_PAGE)]


class ShopCog(commands.Cog, name="Shop"):
    """Buy tools, seeds and supplies. Sell what you've gathered."""

    @app_commands.command(name="shop", description="See what's for sale.")
    async def shop(self, interaction: discord.Interaction):
        pages = shop_pages()
        handler = MenuHandler(interaction=interaction)
        for number, lines in enumerate(pages, start=1):
            embed = CustomEmbed(
                title="Shop",
                desc="\n".join(lines) + "\n\nBuy with `/buy item:<name> quantity:<n>`",
                color=discord.Color.gold(),
                interaction=interaction,
                activity="shopping",
            )
            embed.set_footer(text=f"Page {number}/{len(pages)}")
            handler.add_menu((PaginationMenu if len(pages) > 1 else Menu)(embed=embed))
        first = handler.get_current()
        await interaction.response.send_message(embed=first.embed, view=first)

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
