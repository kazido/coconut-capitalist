import discord
import random
import time
import math

from typing import Any, Coroutine
from discord import Interaction, app_commands
from discord.ext import commands
from logging import getLogger

from cococap.utils.menus import MenuHandler, Menu
from cococap.utils.messages import Cembed, button_check
from cococap.utils.items.items import get_items_from_db, roll_item
from cococap.utils.utils import timestamp_to_english
from cococap.user import User
from cococap.item_models import Master
from cococap.constants import DiscordGuilds, IMAGES_REPO, Rarities, Categories


class FishingCog(commands.Cog, name="Fishing"):
    """Fish to fill your collection book and find treasure!"""

    def __init__(self, bot):
        self.bot = bot

    # gets all items from the sqlite database that have the tag 'fishing'
    fishing_items = get_items_from_db("fishing")

    class Bite:
        def __init__(self, fish) -> None:
            self.caught = False
            self.fish: Master = fish
            self.pattern = [
                "<" if random.randint(0, 1) == 1 else ">" for _ in range(0, fish.rarity * 2)
            ]

        def next_in_pattern(self):
            element = self.pattern.pop(0)
            if len(self.pattern) == 0:
                self.caught = True
            return element

    class FishingView(discord.ui.View):
        def __init__(self, bite: "FishingCog.Bite", interaction: Interaction) -> None:
            self.interaction = interaction
            self.bite: "FishingCog.Bite" = bite
            self.embed = Cembed(
                title="A bite!",
                desc=f"You found a {bite.fish.display_name}...\n{bite.pattern}",
                color=discord.Color.from_str(Rarities.from_value(bite.fish.rarity).color),
                interaction=interaction,
                activity="fishing",
            )
            super().__init__()
            
        def update_embed(self):
            if self.bite.caught:
                self.embed = Cembed(
                    title="You caught the fish!"
                )
            # Update the description of the embed to show the pattern
            self.embed.description = f"Keep going, catch the {self.bite.fish.display_name}!\n{self.bite.pattern}"
            return self.embed

        @discord.ui.button(label="<", style=discord.ButtonStyle.blurple)
        async def left(self, l_interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [l_interaction.user.id]):
                return
            if self.bite.next_in_pattern() != "<":
                self.embed.title = "Too bad..."
                self.embed.description = "The fish darted > right, not < left..."
                self.embed.color = discord.Color.red()
                return await l_interaction.response.edit_message(embed=self.embed, view=None)
            await l_interaction.response.edit_message(embed=self.update_embed(), view=self)

        @discord.ui.button(label=">", style=discord.ButtonStyle.blurple)
        async def right(self, r_interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [r_interaction.user.id]):
                return
            if self.bite.next_in_pattern() != ">":
                self.embed.title = "Too bad..."
                self.embed.description = "The fish darted < left, not > right..."
                self.embed.color = discord.Color.red()
                return await r_interaction.response.edit_message(embed=self.embed, view=None)
            await r_interaction.response.edit_message(embed=self.update_embed(), view=self)

    # THE COMMAND
    @app_commands.command(name="fish")
    async def fish(self, interaction: Interaction):
        """Displays your fishing profile and all available actions."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        # Load the user's items and mining data
        user_items = user.get_field("items")
        user_fishing = user.get_field("fishing")

        # Initialize a menu handler, allowing us to move back and forth between menu pages
        handler = MenuHandler(interaction=interaction)

        # Main menu view when you type /mine
        class FishMenu(Menu):
            def __init__(self, handler: MenuHandler):
                super().__init__(handler, "Home")

                # GENERAL CREATION OF THE EMBED!! COPY THIS AS A TEMPLATE FOR OTHER SKILLS!
                self.embed = Cembed(
                    title=f"Level: 🌟 {user.xp_to_level(user_fishing['xp']):,}",
                    color=discord.Color.from_str(Categories.FISHING.color),
                    interaction=interaction,
                    activity="fishing",
                )
                balances = ""
                for fish_type in ["cod"]:
                    item: dict = user_items.get(fish_type, {})
                    emoji = FishingCog.fishing_items[fish_type].emoji
                    balances += f"{emoji} x{item.get('quantity', 0):,}\n"

                self.embed.add_field(
                    name="Fish",
                    value=balances,
                ).add_field(
                    name="Fish Caught",
                    value=f":fish: **{user_fishing['fish_caught']:,}** fish",
                    inline=False,
                ).set_thumbnail(url=f"{IMAGES_REPO}/skills/fishing.png")

            @discord.ui.button(label="Fish", style=discord.ButtonStyle.gray)
            async def fish(self, interaction: Interaction, button: discord.Button) -> Any:
                fish_view = FishingCog.FishingView(
                    FishingCog.Bite(FishingCog.fishing_items["cod"]), interaction=interaction
                )
                await interaction.response.send_message(embed=fish_view.embed, view=fish_view)

        fish_menu = FishMenu(handler=handler)
        await interaction.response.send_message(embed=fish_menu.embed, view=fish_menu)


async def setup(bot):
    await bot.add_cog(FishingCog(bot))
