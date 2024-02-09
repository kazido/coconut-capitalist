import discord
import random
import time

from typing import Any, Coroutine, Optional
from discord import Interaction, app_commands
from discord.ext import commands
from logging import getLogger
from discord.interactions import Interaction

from cococap.utils.menus import ParentMenu
from cococap.utils.messages import Cembed, button_check
from cococap.utils.items import get_skill_drops, roll_item, create_item
from cococap.utils.utils import timestamp_to_english
from cococap.user import User
from cococap.constants import DiscordGuilds

log = getLogger(__name__)
log.setLevel(10)


class MiningCog(commands.Cog, name="Mining"):
    """Mine nodes to recieve ores, gems, and bits!
    Upgrade your reactor for increased mining power."""

    def __init__(self, bot):
        self.bot = bot

    marker = ":small_red_triangle_down:"
    marker_notch = ":black_small_square:"
    placeholder = "<:covered_grid:1203810768248643605>"
    empty = "<:empty_grid:1203810769880354987>"
    wyrmhole = "<a:wyrmhole:1204212299804442624>"

    # get the possible drops for mining
    loot_table = get_skill_drops("mining")

    class Mineshaft:
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
            ],
            [
                "copper_ore",
                "iron_ore",
                "gold_ore",
                "sanity_gemstone",
                "rage_gemstone",
                "peace_gemstone",
                "balance_gemstone",
                "oreo_gemstone",
            ],
        ]
        num_rows = 5
        num_cols = 5

        def __init__(self) -> None:
            self.columns = []
            for _ in range(self.num_rows):
                self.columns.append(self.create_column())

        def create_node(self, depth: int):
            # Creates a node with loot based on the passed level
            level = self.levels[depth]
            level.reverse()  # We want to roll the rarest items first
            for item_id in level:
                item = MiningCog.loot_table[item_id]
                quantity = roll_item(item)
                if quantity:
                    return item, quantity
            return None, 0

        def create_column(self):
            # Creates a column of 5 nodes
            nodes = []
            for i in range(self.num_cols):
                node = self.create_node(depth=i)
                nodes.append(node)
            return nodes

    class DeeperMineshaft(Mineshaft):
        item_pool = [["scarab_bomb", "copper_ore", "iron_ore", "gold_ore"]]
        common_items = ["copper_ore", "iron_ore", "gold_ore"]
        num_cols = 5

        def __init__(self) -> None:
            self.nodes = []
            self.implosion_gem_rolled = False
            for _ in range(self.num_cols):
                self.nodes.append(self.create_node())
            self.nodes[random.randint(0, 5)] = (MiningCog.loot_table["implosion_gemstone"], 1)
            print(self.nodes)

        def create_node(self):
            item_pool = self.item_pool[0]
            item_id = random.choice(item_pool)

            item = MiningCog.loot_table[item_id]
            if item_id in self.common_items:
                quantity = item.max_drop * 100
            else:
                quantity = random.randint(item.min_drop, item.max_drop)
            return item, quantity

    class WyrmholeView(discord.ui.View):
        placeholder = "<a:upgraded_grid:1204245792479649863>"

        def __init__(self, interaction: Interaction, user: User, session: dict):
            super().__init__(timeout=180)
            self.user = user
            self.interaction = interaction

            # Chain the data from the session
            self.session = session

            # Mine variables
            self.lodes_mined = 0
            self.loot = {}

            # Create the mineshaft and the grid
            self.mineshaft = MiningCog.DeeperMineshaft()
            self.grid = []
            for j in range(self.mineshaft.num_cols):
                self.grid.append(self.placeholder)

            # Create the header
            self.cols = [2]

            # Create the embed
            self.embed = Cembed(
                title=f"You found a Wyrmhole! {MiningCog.wyrmhole}",
                color=discord.Color.purple(),
                desc="You can only choose one node! Good luck!",
                interaction=interaction,
                activity="mining",
            )
            self.embed.add_field(name="Mineshaft :ladder:", value="")
            self.embed.add_field(name="Loot :moneybag:", value="", inline=True)
            # The reason we don't call these xp methods in update_grid is so that we aren't making
            # a call to the database every time we need to update the grid, just at the start.
            xp, xp_needed = self.user.xp_for_next_level(self.user.get_field("mining")["xp"])
            self.embed.set_footer(text=f"Your mining xp: ({xp:,}/{xp_needed:,} xp)")
            self.update_grid()

        def update_grid(self):
            # Set 5 notches at the top of the field
            header = [MiningCog.marker_notch for _ in range(5)]

            # Replace the notches with markers for each reactor level
            for col in self.cols:
                header[col] = MiningCog.marker

            # Set the selection header
            self.embed.set_field_at(0, name="Mineshaft :ladder:", value="".join(header) + "\n")

            # Set the grid in the field
            for node in self.grid:
                value = self.embed.fields[0].value
                self.embed.set_field_at(0, name="Mineshaft :ladder:", value=value + node)

            # Add all the loot we've gotten to the embed on the side
            loot_string = ""
            for loot, amount in self.session["total_loot"].items():
                # If the loot is rare, make it bold
                if loot.rarity >= 5:
                    loot_string += f"\n{loot.emoji} +{amount} **{loot.display_name}**"
                else:
                    loot_string += f"\n{loot.emoji} +{amount} {loot.display_name}"
            self.embed.set_field_at(1, name="Loot :moneybag:", value=loot_string)

        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.grey)
        async def left_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [interaction.user.id]):
                return
            for i in range(len(self.cols)):
                self.cols[i] -= 1
                if self.cols[i] < 0:
                    self.cols[i] = 4
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

        @discord.ui.button(emoji="⛏️", style=discord.ButtonStyle.blurple)
        async def mine_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [interaction.user.id]):
                return
            # For each marker we have, mine one node
            for col in self.cols:
                # Retrieve the item that was rolled for that node
                item, amount = self.mineshaft.nodes[col]
                if item:
                    # If we encounter an item, set the grid to it's emoji
                    # and add it to the loot list
                    self.grid[col] = item.emoji
                    if item in self.loot.keys():
                        self.loot[item] += amount
                    else:
                        self.loot[item] = amount
                    if item in self.session["total_loot"]:
                        self.session["total_loot"][item] += amount
                    else:
                        self.session["total_loot"][item] = amount
                else:
                    self.grid[col] = MiningCog.empty

            # After mining out a node, update the grid and move down a row
            self.update_grid()

            # We have finished mining the mineshaft, remove the buttons and add items to inventory
            # Add items to the user's inventory
            for item, amount in self.loot.items():
                await create_item(self.user, item_id=item.item_id, quantity=amount)

            # Give the user xp for columns mined
            await self.user.inc_xp(skill="mining", xp=1000, interaction=interaction)
            xp, xp_needed = self.user.xp_for_next_level(self.user.get_field("mining")["xp"])
            self.embed.set_footer(text=f"Your mining xp: ({xp:,}/{xp_needed:,} xp)")

            await interaction.response.edit_message(
                embed=self.embed,
                view=MiningCog.FinishedMiningView(self.user, self),
            )
            return

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey)
        async def right_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [interaction.user.id]):
                return
            for i in range(len(self.cols)):
                self.cols[i] += 1
                if self.cols[i] > 4:
                    self.cols[i] = 0
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

    class MiningView(discord.ui.View):
        def __init__(self, interaction: Interaction, user: User, session: dict):
            super().__init__(timeout=180)
            self.user = user
            self.interaction = interaction

            # Chain the data from the session
            self.session = session

            # Mine variables
            self.lodes_mined = 0
            self.loot = {}

            # Create the mineshaft and the grid
            self.mineshaft = MiningCog.Mineshaft()
            self.grid = []
            wyrmhole = False
            for i in range(self.mineshaft.num_cols):
                new_col = []
                for j in range(self.mineshaft.num_rows):
                    if i > 1 and (random.randint(0, 25000) == 15) and not wyrmhole:
                        new_col.append(MiningCog.wyrmhole)
                        wyrmhole = True
                    else:
                        new_col.append(MiningCog.placeholder)
                self.grid.append(new_col)

            # Create the header
            self.row = 0
            self.cols = []
            col_order = [2, 1, 3, 0, 4]
            for i in range(self.user.get_field("mining")["prestige_level"]):
                self.cols.append(col_order[i])

            # Create the embed
            self.embed = Cembed(
                title=":pick: Welcome back to the mines.",
                color=discord.Color.blue(),
                desc="Pick a column to dig out for ores and gems! \
                      \nUpgrade your reactor to dig out more columns.",
                interaction=interaction,
                activity="mining",
            )
            self.embed.add_field(name="Mineshaft :ladder:", value="")
            self.embed.add_field(name="Loot :moneybag:", value="", inline=True)
            # The reason we don't call these xp methods in update_grid is so that we aren't making
            # a call to the database every time we need to update the grid, just at the start.
            xp, xp_needed = self.user.xp_for_next_level(self.user.get_field("mining")["xp"])
            self.embed.set_footer(text=f"Your mining xp: ({xp:,}/{xp_needed:,} xp)")
            self.update_grid()

        def update_grid(self):
            # Set 5 notches at the top of the field
            header = [MiningCog.marker_notch for _ in range(5)]

            # Replace the notches with markers for each reactor level
            for col in self.cols:
                header[col] = MiningCog.marker

            # Set the selection header
            self.embed.set_field_at(0, name="Mineshaft :ladder:", value="".join(header) + "\n")

            # Set the grid in the field
            for row in self.grid:
                value = self.embed.fields[0].value
                self.embed.set_field_at(0, name="Mineshaft :ladder:", value=value + "".join(row) + "\n")

            # Add all the loot we've gotten to the embed on the side
            loot_string = ""
            for loot, amount in self.session["total_loot"].items():
                # If the loot is rare, make it bold
                if loot.rarity >= 5:
                    loot_string += f"\n{loot.emoji} +{amount} **{loot.display_name}**"
                else:
                    loot_string += f"\n{loot.emoji} +{amount} {loot.display_name}"
            self.embed.set_field_at(1, name="Loot :moneybag:", value=loot_string)

        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.grey)
        async def left_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [interaction.user.id]):
                return
            for i in range(len(self.cols)):
                self.cols[i] -= 1
                if self.cols[i] < 0:
                    self.cols[i] = 4
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

        @discord.ui.button(emoji="⛏️", style=discord.ButtonStyle.blurple)
        async def mine_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [interaction.user.id]):
                return
            # For each marker we have, mine one node
            for col in self.cols:
                if self.grid[self.row][col] == MiningCog.wyrmhole:
                    print("got wyrmhole")
                    # Create a wyrmhole
                    wyrmhole = MiningCog.WyrmholeView(
                        interaction=interaction, user=self.user, session=self.session
                    )
                    await interaction.response.edit_message(embed=wyrmhole.embed, view=wyrmhole)
                    return
                # Retrieve the item that was rolled for that node
                item, amount = self.mineshaft.columns[col][self.row]
                # Increase lodes mined by one
                self.lodes_mined += 1
                if item:
                    # If we encounter an item, set the grid to it's emoji
                    # and add it to the loot list
                    self.grid[self.row][col] = item.emoji
                    if item in self.loot.keys():
                        self.loot[item] += amount
                    else:
                        self.loot[item] = amount
                    if item in self.session["total_loot"]:
                        self.session["total_loot"][item] += amount
                    else:
                        self.session["total_loot"][item] = amount
                else:
                    self.grid[self.row][col] = MiningCog.empty

            # After mining out a node, update the grid and move down a row
            self.update_grid()
            self.row += 1

            if self.row < 5:
                await interaction.response.edit_message(embed=self.embed, view=self)
                return

            # We have finished mining the mineshaft, remove the buttons and add items to inventory
            # Add items to the user's inventory
            for item, amount in self.loot.items():
                await create_item(self.user, item_id=item.item_id, quantity=amount)

            # Update the amount of lodes mined
            self.user.get_field("mining")["lodes_mined"] += self.lodes_mined
            self.session["total_lodes_mined"] += self.lodes_mined
            await self.user.save()

            # Give the user xp for columns mined
            xp = 10 * len(self.cols)
            await self.user.inc_xp(skill="mining", xp=xp, interaction=interaction)
            xp, xp_needed = self.user.xp_for_next_level(self.user.get_field("mining")["xp"])
            self.embed.set_footer(text=f"Your mining xp: ({xp:,}/{xp_needed:,} xp)")

            # Roll for the scarab
            # scarab = random.randint(0, 10000)
            # if scarab != 15:
            await interaction.response.edit_message(
                embed=self.embed,
                view=MiningCog.FinishedMiningView(self.user, self),
            )
            return

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey)
        async def right_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.interaction, [interaction.user.id]):
                return
            for i in range(len(self.cols)):
                self.cols[i] += 1
                if self.cols[i] > 4:
                    self.cols[i] = 0
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

    class FinishedMiningView(discord.ui.View):
        def __init__(self, user: User, parent_view: "MiningCog.MiningView"):
            super().__init__(timeout=180)
            self.user = user
            self.pv = parent_view
            self.pv.stop()

        @discord.ui.button(label="Leave", style=discord.ButtonStyle.gray)
        async def leave(self, interaction: Interaction, button: discord.Button):
            self.pv.embed.title = ":pick: MINE CLOSED."
            self.pv.embed.description = "That's enough for today... Check out those spoils!"
            self.pv.embed.color = discord.Color.dark_gray()
            self.pv.embed.remove_field(0)

            current_time = time.time()
            stats = (
                f"Lodes mined: **{self.pv.session['total_lodes_mined']:,}** lodes!\n"
                f"Time spent: {timestamp_to_english(current_time-self.pv.session['start_time'])}"
            )
            self.pv.embed.add_field(
                name="Stats",
                value=stats,
            )
            self.clear_items()
            self.stop()
            await interaction.response.edit_message(embed=self.pv.embed, view=self)

        @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.blurple)
        async def new_mine(self, interaction: Interaction, button: discord.Button):
            mine = MiningCog.MiningView(
                interaction=interaction, user=self.user, session=self.pv.session
            )
            await interaction.response.edit_message(embed=mine.embed, view=mine)

    @app_commands.command(name="mine")
    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    async def mine(self, interaction: Interaction):
        """Displays your mining profile and all available actions."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        mining = user.get_field("mining")

        skill_xp = mining["xp"]
        skill_level = user.xp_to_level(skill_xp)

        embed = Cembed(
            title=f"Mining level: {skill_level}",
            desc=user.create_xp_bar(skill_xp),
            color=discord.Color.blue(),
            interaction=interaction,
            activity="mining",
        )
        embed.add_field(
            name="Lodes Mined",
            value=f":pick: **{mining['lodes_mined']:,}** lodes",
        )
        reactor_field = (
            f"Core 1: {mining['core_slot1']}"
            f"\nCore 2: {mining['core_slot2']}"
            f"\nCore 3: {mining['core_slot3']}"
            f"\nCore 4: {mining['core_slot4']}"
        )
        embed.add_field(
            name=f"Reactor level: {mining['prestige_level']:,}",
            value=reactor_field,
        )

        menu = ParentMenu(embed=embed)
        mine_view = MiningCog.MiningView(
            interaction=interaction,
            user=user,
            session={"total_loot": {}, "total_lodes_mined": 0, "start_time": time.time()},
        )

        class MineButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Mine!", style=discord.ButtonStyle.grey)

            async def callback(self, interaction: Interaction) -> Any:
                await interaction.response.edit_message(embed=mine_view.embed, view=mine_view)

        class ReactorButton(discord.ui.Button):
            def __init__(self):
                super().__init__(label="Reactor", style=discord.ButtonStyle.grey)

            async def callback(self, reactor_interaction: Interaction) -> Coroutine[Any, Any, Any]:
                if not await button_check(reactor_interaction, [interaction.user.id]):
                    return
                await reactor_interaction.response.edit_message(
                    content="Hello! I'm not done yet.", view=None
                )

        menu.add_item(MineButton())
        menu.add_item(ReactorButton())
        await interaction.response.send_message(embed=menu.embed, view=menu)


async def setup(bot):
    await bot.add_cog(MiningCog(bot))
