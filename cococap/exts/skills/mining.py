from typing import Any
import discord

from discord import app_commands
from discord.ext import commands
from logging import getLogger
from discord.interactions import Interaction

from cococap.utils.menus import ParentMenu
from cococap.utils.messages import Cembed
from cococap.utils.items import get_skill_drops, roll_item, create_item
from cococap.user import User
from cococap.constants import DiscordGuilds

log = getLogger(__name__)
log.setLevel(10)


class MiningCog(commands.Cog, name="Mining"):
    """Mine nodes to recieve ores, gems, and bits!
    Upgrade your reactor for increased mining power."""

    def __init__(self, bot):
        self.bot = bot

    # get the possible drops for mining
    loot_table = get_skill_drops("mining")

    levels = [
        [
            "copper_ore",
        ],
        [
            "copper_ore",
            "iron_ore",
            "weathered_seed",
        ],
        [
            "copper_ore",
            "iron_ore",
            "gold_ore",
            "weathered_seed",
        ],
        [
            "copper_ore",
            "iron_ore",
            "gold_ore",
            "sanity_gemstone",
            "rage_gemstone",
            "peace_gemstone",
            "balance_gemstone",
            "implosion_gemstone",
        ],
        [
            "copper_ore",
            "iron_ore",
            "gold_ore",
            "sanity_gemstone",
            "rage_gemstone",
            "peace_gemstone",
            "balance_gemstone",
            "implosion_gemstone",
            "oreo_gemstone",
        ],
    ]

    def create_node(depth: int):
        # Creates a node with loot based on the passed level
        level = MiningCog.levels[depth]
        level.reverse()
        for item_id in level:
            item = MiningCog.loot_table[item_id]
            quantity = roll_item(item)
            if quantity:
                return item, quantity
        return None, 0

    def create_column():
        # Creates a column of 5 nodes
        nodes = []
        for i in range(5):
            node = MiningCog.create_node(depth=i)
            nodes.append(node)
        return nodes

    class Mineshaft:
        def __init__(self) -> None:
            self.columns = []
            for _ in range(5):
                self.columns.append(MiningCog.create_column())

    class MiningView(discord.ui.View):
        marker = ":small_red_triangle_down:"
        marker_notch = ":black_small_square:"
        placeholder = "<:covered_grid:1203810768248643605>"
        empty = "<:empty_grid:1203810769880354987>"

        def __init__(self, interaction: Interaction, user: User, *, timeout: float | None = 180):
            super().__init__(timeout=timeout)
            self.user = user
            self.mineshaft = MiningCog.Mineshaft()
            self.grid = []
            for i in range(5):
                new_col = []
                for j in range(5):
                    new_col.append(self.placeholder)
                self.grid.append(new_col)

            self.cols = []
            for i in range(self.user.get_field("mining")["prestige_level"]):
                self.cols.append(i)
            self.row = 0

            self.loot_list = {}

            self.embed = Cembed(
                title="Welcome to the mines!",
                color=discord.Color.fuchsia(),
                desc="Pick a column to dig out for ores and gems! \
                      \nUpgrade your reactor to dig out more columns.",
                interaction=interaction,
                activity="mining",
            )
            self.embed.add_field(name="Mineshaft", value="")
            self.embed.add_field(name="Loot", value="", inline=True)
            self.update_grid()

        def update_grid(self):
            # Set 5 notches at the top of the field
            header = [self.marker_notch for _ in range(5)]
            
            # Replace the notches with markers for each reactor level
            for col in self.cols:
                header[col] = self.marker
                
            # Set the selection header
            self.embed.set_field_at(0, name="Mineshaft", value="".join(header) + "\n")
            
            # Set the grid in the field
            for row in self.grid:
                value = self.embed.fields[0].value
                self.embed.set_field_at(0, name="Mineshaft", value=value + "".join(row) + "\n")
            
            # Add all the loot we've gotten to the embed on the side
            loot_string = ""
            for loot, amount in self.loot_list.items():
                # If the loot is rare, make it bold
                if loot.rarity >= 5:
                    loot_string += f"\n{loot.emoji} +{amount} **{loot.display_name}**"
                else:
                    loot_string += f"\n{loot.emoji} +{amount} {loot.display_name}"
            self.embed.set_field_at(1, name="Loot", value=loot_string)

        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.grey)
        async def left_button(self, interaction: Interaction, button: discord.Button):
            for i in range(len(self.cols)):
                self.cols[i] -= 1
                if self.cols[i] < 0:
                    self.cols[i] = 4
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

        @discord.ui.button(label="Mine!", style=discord.ButtonStyle.grey)
        async def mine_button(self, interaction: Interaction, button: discord.Button):
            self.left_button.disabled = self.right_button.disabled = True
            for col in self.cols:
                item, amount = self.mineshaft.columns[col][self.row]
                if item:
                    # If we encounter an item, set the grid to it's emoji
                    # and add it to the loot list
                    self.grid[self.row][col] = item.emoji
                    if item in self.loot_list.keys():
                        self.loot_list[item] += amount
                    else:
                        self.loot_list[item] = amount
                else:
                    self.grid[self.row][col] = self.empty

            # After mining out a node, update the grid
            self.update_grid()
            self.row += 1

            # We are at the lowest depth, remove the buttons and add items to inventory
            if self.row > 4:
                self.clear_items()
                for item, amount in self.loot_list.items():
                    await create_item(self.user, item_id=item.item_id, quantity=amount)
            await interaction.response.edit_message(embed=self.embed, view=self)

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey)
        async def right_button(self, interaction: Interaction, button: discord.Button):
            for i in range(len(self.cols)):
                self.cols[i] += 1
                if self.cols[i] > 4:
                    self.cols[i] = 0
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

    @app_commands.command(name="mine")
    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    async def mine(self, interaction: Interaction):
        """Displays your mining profile and all available actions."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        mining = user.get_field("mining")

        skill_xp = mining["xp"]
        skill_level = user.xp_to_lvl(skill_xp)

        embed = Cembed(
            title=f"Mining level: {skill_level}",
            desc=user.create_xp_bar(skill_xp),
            color=discord.Color.blue(),
            interaction=interaction,
            activity="mining",
        )
        embed.add_field(name="Lodes Mined", value=f"**{mining['lodes_mined']}** lodes")

        menu = ParentMenu(embed=embed)
        mine = MiningCog.MiningView(interaction=interaction, user=user)

        class MineButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Mine!", style=discord.ButtonStyle.green)

            async def callback(self, interaction: Interaction) -> Any:
                await interaction.response.edit_message(embed=mine.embed, view=mine)

        menu.add_item(MineButton())
        await interaction.response.send_message(embed=menu.embed, view=menu)


async def setup(bot):
    await bot.add_cog(MiningCog(bot))
