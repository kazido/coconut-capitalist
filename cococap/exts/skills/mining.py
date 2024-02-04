from typing import Any, Optional
import discord
import random

from discord import app_commands
from discord.ext import commands
from random import randint
from logging import getLogger
from discord.interactions import Interaction

from cococap.utils.menus import ParentMenu, SubMenu
from cococap.utils.messages import Cembed
from cococap.utils.items import get_skill_drops, roll_item
from cococap.user import User
from cococap.constants import DiscordGuilds
from cococap.item_models import Master

log = getLogger(__name__)
log.setLevel(10)

# get the possible drops for mining
loot_table = get_skill_drops("mining")


class Node:

    levels = {
        1: ["copper_ore"],
        2: ["copper_ore", "iron_ore", "weathered_seed"],
        3: ["copper_ore", "iron_ore", "gold_ore", "weathered_seed"],
        4: [
            "copper_ore",
            "iron_ore",
            "gold_ore",
            "sanity_gemstone",
            "rage_gemstone",
            "implosion_gemstone",
        ],
        5: [
            "copper_ore",
            "iron_ore",
            "gold_ore",
            "peace_gemstone",
            "balance_gemstone",
            "implosion_gemstone",
            "oreo_gemstone",
        ],
    }

    def __init__(self, depth: int) -> None:
        self.depth: int = depth
        self.item: Master = None
        self.quantity: int = 0

        for item in self.levels[self.depth]:
            roll = roll_item(loot_table[item])
            if roll:
                self.item = item
                self.quantity = roll

    def __repr__(self) -> str:
        if self.item:
            return f"d{self.depth}: {self.quantity}x {self.item}"
        return f"d{self.depth}: x"


class Column:
    levels = 5

    # first 3 rows are ores, last 2 include gems
    def __init__(self) -> None:
        self.nodes = []
        for i in range(Column.levels):
            node = Node(depth=i + 1)
            self.nodes.append(node)
            
    def __repr__(self) -> str:
        rtrn = ""
        for node in self.nodes:
            rtrn += f"{node}" + "\n"
        return rtrn


class Mineshaft:
    num_cols = 5

    def __init__(self) -> None:
        self.columns: list[Column] = []
        for _ in range(Mineshaft.num_cols):
            self.columns.append(Column())


class MiningView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)


class MiningCog(commands.Cog, name="Mining"):
    """Mine!"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mine")
    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    async def mine(self, interaction: Interaction):
        """Displays your mining profile and all available actions."""
        embed = Cembed(
            title="Mining",
            desc="Placeholder",
            color=discord.Color.dark_blue(),
            interaction=interaction,
            activity="mining",
        )
        menu = ParentMenu(embed=embed)

        sub_embed = Cembed(
            title="Mining module",
            desc="Mining stuff xD",
            color=discord.Color.dark_blue(),
            interaction=interaction,
            activity="mining",
        )
        sub_menu = SubMenu(sub_embed)

        class MineButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Mine!", style=discord.ButtonStyle.green)

            async def callback(self, interaction: Interaction) -> Any:
                menu.move_forward()
                await interaction.response.edit_message(embed=sub_embed, view=sub_menu)

        menu.add_item(MineButton())

        menu.add_submenu(sub_menu)
        await interaction.response.send_message(embed=menu.embed, view=menu)


async def setup(bot):
    await bot.add_cog(MiningCog(bot))
