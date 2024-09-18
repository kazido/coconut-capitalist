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
from cococap.constants import DiscordGuilds, IMAGES_REPO, Categories

log = getLogger(__name__)
log.setLevel(10)


class MiningCog(commands.Cog, name="Mining"):
    """Mine nodes to recieve ores, gems, and bits!
    upgrade your reactor for increased mining power."""

    def __init__(self, bot):
        self.bot = bot

    # gets all items from the sqlite database that have the tag 'mining'
    mining_items = get_items_from_db("mining")

    # emojis that get displayed during the mining minigame
    selected_column_emoji = ":small_red_triangle_down:"  # selecting column to mine
    notch_emoji = ":black_small_square:"  # placeholder for the marker emoji
    cell_emoji = "<:cell:1280658009306959893>"  # a mineable cell with its contents hidden
    cell_empty_emoji = "<:cell_empty:1280658029703860244>"  # a mined cell that is empty
    wyrmhole_emoji = "<a:wyrmhole:1280656910290260038>"  # a wyrmhole

    # reactor slots
    core_slots = ["core_slot1", "core_slot2", "core_slot3", "core_slot4"]

    class Mineshaft:
        """the structure of the mineshaft. just lists of nodes with items and quantities."""

        levels = [
            [
                "copper_ore",
            ],
            [
                "iron_ore",
            ],
            [
                "gold_ore",
                "weathered_seed",
            ],
            [
                "sanity_gemstone",
                "rage_gemstone",
                "peace_gemstone",
                "balance_gemstone",
            ],
            [
                "oreo_gemstone",
            ],
        ]
        num_rows = 5
        num_cols = 5

        def __init__(self) -> None:
            self.columns = []  # columns that hold 5 nodes each
            for _ in range(self.num_cols):
                # for each row, generate a column and add it to the list
                self.columns.append([self.create_node(depth=i) for i in range(self.num_rows)])

        def create_node(self, depth: int):
            # creates a node with loot based on the passed level
            level = []
            for i in range(depth, -1, -1):
                level.extend(self.levels[i])
            for item_id in level:
                item = MiningCog.mining_items[item_id]
                quantity = roll_item(item)
                if quantity:
                    return item, quantity
            # if nothing was rolled, return no item and no quantity
            return None, 0

    class DeeperMineshaft(Mineshaft):
        """the structure of the wyrmhole mineshaft. just lists of nodes with items and quantities and an implosion gemstone."""

        item_pool = {
            "scarab_bomb": 20,
            "copper_ore": 1000,
            "iron_ore": 300,
            "gold_ore": 100,
        }
        num_cols = 5

        def __init__(self) -> None:
            self.nodes = []
            for _ in range(self.num_cols):
                self.nodes.append(self.create_node())
            # always add 1 implosion gem to the nodes
            self.nodes[random.randint(0, 4)] = (
                MiningCog.mining_items["implosion_gemstone"],
                1,
            )

        def create_node(self):
            # choose a random item from the wyrmhole item pool
            item_id = random.choice(self.item_pool.keys())
            item = MiningCog.mining_items[item_id]
            quantity = self.item_pool[item_id]
            return item, quantity

    class MiningView(discord.ui.View):
        """
        this view is the "backend" of the mining minigame.
        essentially, when the minigame is started, this view is created and acts
        as the logical flow of the game.
        """

        def __init__(self, session: dict):
            super().__init__(timeout=120)
            # chain the data from the session
            # this allows us to track items mined if they continue to mine
            self.session = session
            self.user: User = session["user"]

            # create a new mineshaft
            self.mineshaft = MiningCog.Mineshaft()
            # create grid which stores the emojis for the discord embed
            self.grid = []

            # give the user a higher chance to find wyrmholes based on gemstones in core slots
            has_implosion = (
                True if "implosion_gemstone" in self.user.get_field("items").keys() else False
            )
            gem_bonus = 0
            for slot in MiningCog.core_slots:
                # give the user a bigger bonus if they don't have an implosion gemstone already
                if self.user.get_field("mining")[slot]:
                    gem_bonus += 500 if has_implosion else 5000

            # roll for a wyrmhole everytime we make a grid
            wyrmhole_odds = 25000 - gem_bonus
            for depth in range(self.mineshaft.num_rows):
                column_of_emojis = []
                for _ in range(self.mineshaft.num_cols):
                    # if we are in the 3rd depth or lower
                    if depth > 1 and (random.randint(0, wyrmhole_odds) == 15):
                        column_of_emojis.append(MiningCog.wyrmhole_emoji)
                    else:
                        column_of_emojis.append(MiningCog.cell_emoji)
                self.grid.append(column_of_emojis)

            # create the header for the embed
            # todo: this code needs refactoring -- currently it adds a new selector per prestige level
            # this needs to be fixed to properly scale with level or add some kind of unlock for it
            self.selected_row = 0
            self.column_cursors = []
            col_order = [2, 1, 3, 0, 4]
            for depth in range(self.user.get_field("mining")["prestige_level"]):
                self.column_cursors.append(col_order[depth])

            # create the embed
            self.embed = Cembed(
                title=":pick: Welcome back to the mines.",
                color=discord.Color.blue(),
                desc="Pick a column to dig out for ores and gems! \
                      \nupgrade your reactor to dig out more columns.",
                interaction=self.session["interaction"],
                activity="mining",
            )
            # we add these fields now so they can be dynamically updated as the user mines.
            self.embed.add_field(name="Mineshaft :ladder:", value="")
            self.embed.add_field(name="Loot :moneybag:", value="", inline=True)

            # the reason we don't call these xp methods in update_grid is so that we aren't making
            # a call to the database every time we need to update the grid, just at the start.
            xp = self.user.get_field("mining")["xp"]
            overflow_xp, xp_needed = self.user.xp_for_next_level(xp)
            self.embed.add_field(
                name=f"level {self.user.xp_to_level(xp)} - {overflow_xp:,}/{xp_needed:,} xp",
                value=self.user.create_xp_bar(xp),
                inline=False,
            )
            self.embed.set_footer(text="Mine all the way down to recieve xp!")
            self.update_grid()

        async def on_timeout(self) -> Coroutine[any, any, None]:
            embed = discord.embed(
                title=":zzz: Mine closed.",
                description="Did you... fall asleep?",
                color=discord.Color.dark_gray(),
            )
            # Clear the buttons and stop the view for no more errors :)
            self.clear_items()
            self.stop()

            await self.session["interaction"].edit_original_response(embed=embed, view=None)

        def update_grid(self):
            # Set 5 notches at the top of the field
            grid_header = [MiningCog.notch_emoji for _ in range(5)]

            # Replace the notches with markers for each reactor level
            for cursor in self.column_cursors:
                grid_header[cursor] = MiningCog.selected_column_emoji

            # Set the selection header
            self.embed.set_field_at(0, name="Mineshaft :ladder:", value="".join(grid_header) + "\n")

            # Set the grid in the field
            for row in self.grid:
                value = self.embed.fields[0].value
                self.embed.set_field_at(
                    0, name="Mineshaft :ladder:", value=value + "".join(row) + "\n"
                )

            # Add all the loot we've gotten to the embed on the side
            loot_string = ""
            for loot, amount in self.session["total_loot"].items():
                # If the loot is rare, make it bold
                loot_string += f"\n{loot.emoji} +{amount}"
                if loot.rarity >= 5:
                    loot_string += f" **{loot.display_name}**"
                else:
                    loot_string += f" {loot.display_name}"
            self.embed.set_field_at(1, name="Loot :moneybag:", value=loot_string)

        @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.grey)
        async def left_button(self, interaction: Interaction, button: discord.Button):
            # Go left xD
            if not await button_check(self.session["interaction"], [interaction.user.id]):
                return
            for i in range(len(self.column_cursors)):
                self.column_cursors[i] -= 1
                if self.column_cursors[i] < 0:
                    self.column_cursors[i] = 4
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

        @discord.ui.button(emoji="⛏️", style=discord.ButtonStyle.blurple)
        async def mine_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.session["interaction"], [interaction.user.id]):
                return
            # For each marker we have, mine one node
            for col in self.column_cursors:
                if self.grid[self.selected_row][col] == MiningCog.wyrmhole_emoji:
                    # If we get a wyrmhole, create one and immediately exit the mine
                    wyrmhole = MiningCog.WyrmholeView(session=self.session)
                    await interaction.response.edit_message(embed=wyrmhole.embed, view=wyrmhole)
                    return

                # If there's no wyrmhole, retrieve the item that was rolled for that node
                item, amount = self.mineshaft.columns[col][self.selected_row]
                self.session["total_lodes_mined"] += 1
                # If we encounter an item, set the grid to it's emoji
                # and add it to the loot list
                if item:
                    self.grid[self.selected_row][col] = item.emoji
                    if item in self.session["total_loot"]:
                        self.session["total_loot"][item] += amount
                    else:
                        self.session["total_loot"][item] = amount
                else:
                    self.grid[self.selected_row][col] = MiningCog.cell_empty_emoji

            # After mining out a node, update the grid and move down a row
            self.update_grid()
            self.selected_row += 1
            # If we haven't reached the bottom, update the message and exit this function
            if self.selected_row < 5:
                await interaction.response.edit_message(embed=self.embed, view=self)
                return

            # Give the user xp for columns mined
            rewarded_xp = 10 * len(self.column_cursors)
            pet_data = await self.user.inc_xp(
                skill="mining", xp=rewarded_xp, interaction=interaction
            )
            xp = self.user.get_field("mining")["xp"]
            overflow_xp, xp_needed = self.user.xp_for_next_level(xp)
            self.embed.set_field_at(
                2,
                name=f"Level {self.user.xp_to_level(xp)} - {overflow_xp:,}/{xp_needed:,} xp {pet_data.emoji if pet_data else ''}",
                value=self.user.create_xp_bar(xp),
                inline=False,
            )
            choices = [
                "a wyrmhole",
                "a gemstone",
                "an oreore",
                "some friends lol",
                "the spirit of the mines",
            ]
            self.embed.set_footer(text=f"What's one more? Might find {random.choice(choices)}!")

            # Roll for the scarab
            # TODO: Make the scarab work xD
            scarab = random.randint(0, 50)
            if scarab == 15:
                pass

            await interaction.response.edit_message(
                embed=self.embed,
                view=MiningCog.FinishedMiningView(self.user, self),
            )
            return

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey)
        async def right_button(self, interaction: Interaction, button: discord.Button):
            # Go right xD
            if not await button_check(self.session["interaction"], [interaction.user.id]):
                return
            for i in range(len(self.column_cursors)):
                self.column_cursors[i] += 1
                if self.column_cursors[i] > 4:
                    self.column_cursors[i] = 0
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

    class WyrmholeView(discord.ui.View):
        """Discord structure to hold the wyrmhole"""

        placeholder = "<a:upgraded_grid:1204245792479649863>"

        def __init__(self, session: dict):
            super().__init__(timeout=600)
            # Chain the data from the session
            self.session = session
            self.user = session["user"]

            # Create the mineshaft and the grid
            self.mineshaft = MiningCog.DeeperMineshaft()
            self.grid = []
            for _ in range(self.mineshaft.num_cols):
                self.grid.append(self.placeholder)

            # Create the header
            self.cols = [2]

            # Create the embed
            self.embed = Cembed(
                title=f"You found a Wyrmhole! {MiningCog.wyrmhole_emoji}",
                color=discord.Color.purple(),
                desc="You can only choose one node! Good luck!",
                interaction=self.session["interaction"],
                activity="mining",
            )
            self.embed.add_field(name="Mineshaft :ladder:", value="")
            self.embed.add_field(name="Loot :moneybag:", value="", inline=True)
            # The reason we don't call these xp methods in update_grid is so that we aren't making
            # a call to the database every time we need to update the grid, just at the start.
            xp = self.user.get_field("mining")["xp"]
            overflow_xp, xp_needed = self.user.xp_for_next_level(xp)
            self.embed.add_field(
                name=f"Level {self.user.xp_to_level(xp)} - {overflow_xp:,}/{xp_needed:,} xp",
                value=self.user.create_xp_bar(xp),
                inline=False,
            )
            self.embed.set_footer(text="Don't tilt too hard if you don't get it, okay?")
            self.update_grid()

        def update_grid(self):
            # Set 5 notches at the top of the field
            header = [MiningCog.notch_emoji for _ in range(5)]

            # Replace the notches with markers for each reactor level
            for col in self.cols:
                header[col] = MiningCog.selected_column_emoji

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
            if not await button_check(self.session["interaction"], [interaction.user.id]):
                return
            for i in range(len(self.cols)):
                self.cols[i] -= 1
                if self.cols[i] < 0:
                    self.cols[i] = 4
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

        @discord.ui.button(emoji="⛏️", style=discord.ButtonStyle.blurple)
        async def mine_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.session["interaction"], [interaction.user.id]):
                return
            # For each marker we have, mine one node
            for col in self.cols:
                # Retrieve the item that was rolled for that node
                item, amount = self.mineshaft.nodes[col]
                if item:
                    # If we encounter an item, set the grid to it's emoji
                    # and add it to the loot list
                    self.grid[col] = item.emoji
                    if item in self.session["total_loot"]:
                        self.session["total_loot"][item] += amount
                    else:
                        self.session["total_loot"][item] = amount
                else:
                    self.grid[col] = MiningCog.cell_empty_emoji

            # After mining out a node, update the grid and move down a row
            self.update_grid()

            # We have finished mining the mineshaft, remove the buttons and add items to inventory
            # Add items to the user's inventory
            self.embed.set_footer(text="Better luck next time.")

            # Give the user xp for columns mined
            xp = self.user.get_field("mining")["xp"]
            overflow_xp, xp_needed = self.user.xp_for_next_level(xp)
            self.embed.set_field_at(
                2,
                name=f"Level {self.user.xp_to_level(xp)} - {overflow_xp:,}/{xp_needed:,} xp",
                value=self.user.create_xp_bar(xp),
                inline=False,
            )

            await interaction.response.edit_message(
                embed=self.embed,
                view=MiningCog.FinishedMiningView(self.user, self),
            )
            return

        @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.grey)
        async def right_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(self.session["interaction"], [interaction.user.id]):
                return
            for i in range(len(self.cols)):
                self.cols[i] += 1
                if self.cols[i] > 4:
                    self.cols[i] = 0
            self.update_grid()
            await interaction.response.edit_message(embed=self.embed, view=self)

    class FinishedMiningView(discord.ui.View):
        def __init__(self, user: User, parent_view: "MiningCog.MiningView"):
            super().__init__()
            self.user = user
            self.pv = parent_view
            self.pv.stop()

        @discord.ui.button(label="Leave", style=discord.ButtonStyle.gray)
        async def leave(self, interaction: Interaction, button: discord.Button):
            session = self.pv.session
            lodes = session["total_lodes_mined"]

            # We have finished the session, so add items to inventory
            for item, amount in session["total_loot"].items():
                await self.user.create_item(item_id=item.item_id, quantity=amount)

            # Update the amount of lodes mined
            self.user.get_field("mining")["lodes_mined"] += lodes
            await self.user.save()

            self.pv.embed.title = ":pick: Mine Left"
            if lodes > 100:
                desc = "Here's what you got in your mini-mining-session."
            elif lodes > 1000:
                desc = "What a grind! Get anything good?"
            elif lodes > 10000:
                desc = "YO ping me if you ever see this. I doubt anyone ever will other than Zennor. Maybe..."
            else:
                desc = "Quick pitstop."
            self.pv.embed.description = desc
            self.pv.embed.color = discord.Color.dark_gray()
            self.pv.embed.remove_field(0)

            # Add in the juicy stats as the footer
            current_time = time.time()
            time_spent = timestamp_to_english(current_time - self.pv.session["start_time"])
            self.pv.embed.set_footer(text=f"You spent {time_spent} mining {lodes} lodes.")

            # Clear the view and stop it so it don't time out, you feel?
            self.clear_items()
            self.stop()
            await interaction.response.edit_message(embed=self.pv.embed, view=self)

        @discord.ui.button(emoji="🔄", style=discord.ButtonStyle.blurple)
        async def new_mine(self, interaction: Interaction, button: discord.Button):
            mine = MiningCog.MiningView(session=self.pv.session)
            await interaction.response.edit_message(embed=mine.embed, view=mine)

    class Reactor(Menu):
        def __init__(self, handler: MenuHandler, user: User, interaction: Interaction):
            super().__init__(handler, "Reactor")
            self.user = user
            self.user_mining = user.get_field("mining")
            self.reactor_level = self.user_mining["prestige_level"]
            self.embed = Cembed(
                title=f"Reactor Level: 🌟 {self.reactor_level:,}",
                description="Level up your reactor for passive mining and to mine more nodes!",
                color=discord.Color.from_str("0x0408dd"),
                interaction=interaction,
                activity="reactor",
            )

            # Generate the text for the core slots based on what gems the user has
            reactor_field = ""
            for core in MiningCog.core_slots:
                # If there is no item in the user's core slots
                item_in_slot = self.user_mining[core]
                emoji = MiningCog.cell_empty_emoji
                if item_in_slot:
                    emoji = MiningCog.mining_items[item_in_slot].emoji
                reactor_field += f"{emoji} "

            self.embed.add_field(name="Cores", value=reactor_field)

            if self.reactor_level < 2:
                # User hasn't unlocked the auto-miner
                return

            # AUTO-MINER
            # Fetch the time to see how many lodes should be generated
            seconds_since_last_mine = int(time.time() - self.user_mining["last_auto_mine"])
            lodes_generated = seconds_since_last_mine / 360
            self.lodes_generated = int(lodes_generated)
            self.embed.add_field(
                name=f"Auto-Miner™ {discord.PartialEmoji.from_str('<a:auto_miner:1280743049781051463>')}",
                value=f"You have **{self.lodes_generated:,}** lodes to claim!",
                inline=False,
            )
            self.embed.add_field(
                name="Lodes Auto-mined",
                value=f":pick: **{self.user_mining['lodes_auto_mined']:,}** lodes",
            )

        # TODO: Get working
        @discord.ui.button(label="Insert Gems", disabled=True, style=discord.ButtonStyle.gray)
        async def insert_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(interaction, [interaction.user.id]):
                return
            await interaction.response.edit_message()

        @discord.ui.button(label="Claim", disabled=False, style=discord.ButtonStyle.green)
        async def claim_button(self, interaction: Interaction, button: discord.Button):
            if not await button_check(interaction, [interaction.user.id]):
                return
            auto_mined_lodes = {}
            # Choose a depth to mine at based on reactor level
            depth = self.reactor_level
            depth = 4 if depth > 4 else depth
            level = MiningCog.Mineshaft.levels[depth]
            for i in range(depth, -1, -1):
                level.extend(MiningCog.Mineshaft.levels[i])

            for _ in range(0, self.lodes_generated):
                # We want to roll the rarest items first
                level.reverse()
                for item_id in level:
                    item = MiningCog.mining_items[item_id]
                    quantity = roll_item(item)
                    if quantity:
                        auto_mined_lodes[item] = auto_mined_lodes.get(item, 0) + quantity
                        break  # Stop trying to roll for items
            results = ""
            for item, quantity in auto_mined_lodes.items():
                results += f"{item.emoji} x{quantity}\n"
                await self.user.create_item(item_id=item.item_id, quantity=quantity)

            self.user_mining["last_auto_mine"] = time.time()
            self.user_mining["lodes_auto_mined"] += self.lodes_generated
            await self.user.save()

            self.embed.set_field_at(1, name="Auto-Miner™", value=results)
            self.embed.set_field_at(
                2,
                name="Lodes Auto-Mined™",
                value=f":pick: **{self.user_mining['lodes_auto_mined'] + self.lodes_generated:,}** lodes",
                inline=False,
            )

            self.remove_item(self.claim_button)
            return await interaction.response.edit_message(embed=self.embed, view=None)

    @app_commands.command(name="mine")
    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    async def mine(self, interaction: Interaction):
        """Displays your mining profile and all available actions."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        # Load the user's items and mining data
        user_items = user.get_field("items")
        user_mining = user.get_field("mining")

        # Create the mine view with a fresh session
        mine_view = MiningCog.MiningView(
            session={
                "total_loot": {},
                "total_lodes_mined": 0,
                "start_time": time.time(),
                "interaction": interaction,
                "user": user,
            },
        )

        # Initialize a menu handler, allowing us to move back and forth between menu pages
        handler = MenuHandler(interaction=interaction)

        # Main menu view when you type /mine
        class MineMenu(Menu):
            def __init__(self, handler: MenuHandler):
                super().__init__(handler, "Home")
                MiningCog.Reactor(
                    handler, user=user, interaction=interaction
                )  # Create the reactor menu when the Main Menu is made

                # GENERAL CREATION OF THE EMBED!! COPY THIS AS A TEMPLATE FOR OTHER SKILLS!
                self.embed = Cembed(
                    title=f"Level: 🌟 {user.xp_to_level(user_mining['xp']):,}",
                    color=discord.Color.from_str(Categories.MINING.color),
                    interaction=interaction,
                    activity="mining",
                )
                balances = ""
                for ore_type in ["copper_ore", "iron_ore", "gold_ore"]:
                    item: dict = user_items[ore_type]
                    emoji = MiningCog.mining_items[ore_type].emoji
                    balances += f"{emoji} x{item.get('quantity', 0):,}\n"

                self.embed.add_field(
                    name="Ores",
                    value=balances,
                ).add_field(
                    name="Lodes Mined",
                    value=f":pick: **{user_mining['lodes_mined']:,}** lodes",
                    inline=False,
                ).set_thumbnail(url=f"{IMAGES_REPO}/skills/mining.png")

            @discord.ui.button(label="Mine", style=discord.ButtonStyle.gray)
            async def mine(self, interaction: Interaction, button: discord.Button) -> Any:
                await interaction.response.edit_message(
                    embed=mine_view.embed,
                    view=mine_view,
                )

        mine_menu = MineMenu(handler=handler)
        await interaction.response.send_message(embed=mine_menu.embed, view=mine_menu)


async def setup(bot):
    await bot.add_cog(MiningCog(bot))
