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
from cococap.constants import DiscordGuilds, IMAGES_REPO, Rarities, Categories


class FishingCog(commands.Cog, name="Fishing"):
    """Fish to fill your collection book and find treasure!"""

    def __init__(self, bot):
        self.bot = bot

    # gets all items from the sqlite database that have the tag 'mining'
    fishing_items = get_items_from_db("fishing")

    class Bite:
        def __init__(self, fish) -> None:
            self.caught = False
            self.fish = fish
            self.pattern = [
                "<" if random.randint(0, 1) == 1 else ">" for _ in range(0, fish.rarity * 2)
            ]
            print(self.pattern)

        def next_in_pattern(self):
            return self.pattern.pop(0)

    class FishingView(discord.ui.View):
        def __init__(self, bite: "FishingCog.Bite", interaction: Interaction) -> None:
            self.interaction = interaction
            self.bite: "FishingCog.Bite" = bite
            self.embed = Cembed(
                title="A bite!",
                desc="Catch the fish lol...",
                color=discord.Color.from_str(Rarities.from_value(bite.fish.rarity).color),
                interaction=interaction,
                activity="fishing",
            )
            super().__init__()

        @discord.ui.button(label="<", style=discord.ButtonStyle.blurple)
        async def left(self, l_interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [l_interaction.user.id]):
                return
            if self.bite.next_in_pattern() != "<":
                self.embed.title = "Too bad..."
                self.embed.description = "You failed the pattern..."
                self.embed.color = discord.Color.red()
                return await l_interaction.response.edit_message(embed=self.embed, view=None)
            await l_interaction.response.send_message("good")

    @app_commands.command(name="fish")
    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
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
