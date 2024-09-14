import discord

from discord.ext import commands
from discord import app_commands

from cococap.user import User
from cococap.item_models import Master
from cococap.utils.messages import Cembed, button_check
from cococap.utils.menus import Menu, MenuHandler, MainMenu
from cococap.constants import Categories
from cococap.pagination import LinePaginator


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
                "You don't have any items! Get to it!", ephemeral=True
            )

        class Inventory(MainMenu):
            def __init__(self, handler: MenuHandler):
                self.lines = [] # This is to work with pagination, currently not working
                embed = Cembed(
                    title=f"{interaction.user.name}'s Inventory",
                    desc="",
                    color=discord.Color.from_rgb(153, 176, 162),
                    interaction=interaction,
                    activity="inventory",
                )
                # TODO: Handle when inventory gets too big
                for k, v in inventory.items():
                    data: Master = Master.get_by_id(k)
                    # self.lines.append(f"{data.emoji} {v['quantity']:,} {data.display_name}")
                    embed.description += f"{data.emoji} {v['quantity']:,} {data.display_name}\n"
                super().__init__(handler, embed=embed)
                
            @discord.ui.button(label="Filters", emoji="🔡", style=discord.ButtonStyle.gray, row=3)
            async def filters(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not await button_check(interaction, [self.handler.interaction.user.id]):
                    return
                self.add_item(CategorySelect(self.handler))
                self.remove_item(self.filters)
                await interaction.response.edit_message(view=self)

        class SubInventory(Menu):
            def __init__(self, handler: MenuHandler, category: Categories):
                self.lines = [] # This is to work with pagination, currently not working
                embed = Cembed(
                    title=f"{interaction.user.name}'s {category.display_name} Inventory {category.emoji}",
                    desc="",
                    color=discord.Color.from_str(category.color),
                    interaction=interaction,
                    activity="inventory",
                )
                # TODO: Handle when inventory gets too big
                has_item = False
                for k, v in inventory.items():
                    data: Master = Master.get_by_id(k)
                    if category.display_name.lower() in data.skill:
                        has_item = True
                        # self.lines.append(f"{data.emoji} {v['quantity']:,} {data.display_name}\n") 
                        embed.description += f"{data.emoji} {v['quantity']:,} {data.display_name}\n"
                if not has_item:
                    embed.description = "*You have no items in this category...*"
                super().__init__(handler, id=category.name.lower(), embed=embed)

            @discord.ui.button(label="Back", emoji="🔙", style=discord.ButtonStyle.gray, row=4)
            async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
                if not await button_check(interaction, [self.handler.interaction.user.id]):
                    return
                menu = self.handler.move_home()
                await interaction.response.edit_message(embed=menu.embed, view=menu)

        # TODO: Maybe add a button to choose to filter to hide the ugly select menu by default
        class CategorySelect(discord.ui.Select):
            def __init__(self, handler: MenuHandler):
                self.handler = handler
                super().__init__(placeholder="Select a filter")
                for category in Categories:
                    category: Categories
                    self.add_option(
                        label=category.display_name,
                        description=f"Display your {category.display_name.lower()} items.",
                        emoji=discord.PartialEmoji.from_str(category.emoji),
                        value=category.display_name.lower(),
                    )

            async def callback(self, interaction: discord.Interaction):
                subinventory = SubInventory(self.handler, Categories.from_name(self.values[0]))
                self.handler.add_menu(subinventory)
                menu = self.handler.move_to(self.values[0])
                await interaction.response.edit_message(embed=menu.embed, view=menu)
                return

        # Initialize a menu handler, allowing us to move back and forth between menu pages
        inventory_menu = Inventory(handler=MenuHandler(interaction=interaction))
        await interaction.response.send_message(embed=inventory_menu.embed, view=inventory_menu)


async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
