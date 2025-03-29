import discord

from discord.ext import commands
from discord import app_commands

from cococap.user import User
from cococap.item_models import Master
from cococap.utils.messages import Cembed
from cococap.utils.menus import Menu, MenuHandler
from cococap.pagination import LinePaginator


class InventoryCog(commands.Cog, name="Inventory"):
    """Check out all the useful items you own."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="Check your inventory!")
    async def inventory(self, interaction: discord.Interaction, filter: "str" = None):
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        inventory: dict = user.get_field("items")

        if len(inventory) == 0:
            return await interaction.response.send_message(
                "You don't have any items! Get to it!", ephemeral=True
            )

        class Inventory(Menu):
            def __init__(self, handler: MenuHandler):
                self.lines = []  # This is to work with pagination, currently not working
                embed = Cembed(
                    title=f"{interaction.user.name}'s Inventory",
                    desc="",
                    color=discord.Color.from_rgb(153, 176, 162),
                    interaction=interaction,
                    activity="inventory",
                )
                # TODO: Handle when inventory gets too big
                has_item = False
                for k, v in inventory.items():
                    data: Master = Master.get_by_id(k)
                    if not filter:
                        embed.description += f"{data.emoji} {v['quantity']:,} {data.display_name}\n"
                    elif any(filter.lower() in x for x in (data.display_name.lower(), data.item_id.lower(), data.skill.lower())):
                        has_item = True
                        # self.lines.append(f"{data.emoji} {v['quantity']:,} {data.display_name}")
                        embed.description += f"{data.emoji} {v['quantity']:,} {data.display_name}\n"
                if filter and (not has_item):
                    print(filter)
                    print(not has_item)
                    embed.description = f"*No items found using this filter:* {filter}"
                super().__init__(handler, "inventory", embed=embed)
                
        # Initialize a menu handler, allowing us to move back and forth between menu pages
        inventory_menu = Inventory(handler=MenuHandler(interaction=interaction))
        await interaction.response.send_message(embed=inventory_menu.embed, view=inventory_menu)


async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
