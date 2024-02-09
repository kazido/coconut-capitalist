from typing import Coroutine
import discord

from discord.ext import commands
from discord import app_commands
from discord.app_commands import Choice

from cococap.utils.items import field_formats
from cococap.constants import Rarities
from cococap.user import User
from cococap.item_models import Master
from cococap.utils.messages import Cembed


class InventoryCog(commands.Cog, name="Inventory"):
    """Check out all the useful items you own."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="Check your inventory!")
    @app_commands.guilds(977351545966432306, 856915776345866240)
    async def inventory(self, interaction: discord.Interaction):
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        inventory: dict = user.get_field("items")

        if len(inventory) == 0:
            return await interaction.response.send_message(
                "You don't have any items!", ephemeral=True
            )

        inventory_embed = Cembed(
            title=f"{interaction.user.name}'s Inventory",
            desc="",
            color=discord.Color.from_rgb(153, 176, 162),
            interaction=interaction,
            activity="inventory",
        )
        for k, v in inventory.items():
            data: Master = Master.get_by_id(k)
            inventory_embed.description += f"{data.emoji} {v['quantity']:,} {data.display_name}\n"

        await interaction.response.send_message(embed=inventory_embed)

    @app_commands.command(name="wiki", description="What is this item?")
    @app_commands.guilds(977351545966432306, 856915776345866240)
    @app_commands.describe(category="category of item")
    @app_commands.choices(
        category=[
            #Choice(name="General", value="none"),
            Choice(name="Mining", value="mining"),
            #Choice(name="Foraging", value="foraging"),
        ]
    )
    async def wiki(self, interaction: discord.Interaction, category: Choice[str]):
        class WikiView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                if category.value == "none":
                    category.value = None
                select_menu = WikiSelect(category=category.value)
                self.add_item(select_menu)

            def on_timeout(self):
                self.clear_items()
                self.stop()
                return

        class WikiSelect(discord.ui.Select):
            def __init__(self, category: str):
                super().__init__(placeholder="Select an item to view")

                for item in Master.select().where(Master.skill == category):
                    item: Master
                    if item.emoji:
                        self.add_option(
                            label=item.display_name,
                            description=item.description,
                            emoji=discord.PartialEmoji.from_str(item.emoji),
                            value=item.item_id,
                        )

            async def callback(self, interaction: discord.Interaction):
                embed: discord.Embed = construct_embed(self.values[0], for_shop=False)
                await interaction.response.edit_message(embed=embed)
                return

        await interaction.response.send_message("Pick one!", view=WikiView())


def construct_stats_string(item_data: dict, for_shop: bool):
    """Constructs a string filled with item information."""
    stats_string = ""
    for field_name in item_data:
        if field_name in field_formats.keys():
            value = item_data[field_name]
            if field_name == "rarity":
                rarity = Rarities.from_value(value)
                value = rarity.rarity_name
            if not value or (for_shop and not "shop_field" in formatting):
                continue
            formatting = field_formats[field_name]
            stats_string += formatting["text"].format(value) + "\n"

    return stats_string


def construct_embed(item_id, for_shop: bool):
    """Constructs an embed filled with formatted data about the item that is passed.

    Args:
        item_id: The item ID to create an embed for.
        for_shop (bool): If True, will only add fields needed for the shop.

    Returns:
        discord.Embed: An embed filled with the items data.
    """
    item_data: Master = Master.get_by_id(item_id)

    # Create an embed with the proper information from the item
    embed = discord.Embed(
        title=f"{item_data.emoji} {item_data.display_name}",
        description=f"{item_data.description}\n",
    )
    rarity = Rarities.from_value(item_data.rarity)
    embed.color = discord.Color.from_str(rarity.color)
    embed.set_footer(text=f"Wiki: {item_id}")

    stats_string = construct_stats_string(item_data.__dict__["__data__"], for_shop)
    embed.set_thumbnail(url=discord.PartialEmoji.from_str(item_data.emoji).url)
    # Add the string to the embed under a field titled "Stats"
    embed.description += stats_string
    return embed


async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
