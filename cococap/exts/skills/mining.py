import discord
import random
import time
import math

from typing import Any, Coroutine, Optional
from discord import Interaction, app_commands
from discord.ext import commands
from logging import getLogger
from discord.interactions import Interaction

from cococap.utils.menus import MenuHandler, Menu
from cococap.utils.messages import Cembed, button_check
from cococap.utils.items import get_skill_drops, roll_item, create_item
from cococap.utils.utils import timestamp_to_english
from cococap.user import User
from cococap.constants import DiscordGuilds, IMAGES_REPO

log = getLogger(__name__)
log.setLevel(10)


class MiningCog(commands.Cog, name="Mining"):
    """Mine nodes to recieve ores, gems, and bits!
    Upgrade your reactor for increased mining power."""

    def __init__(self, bot):
        self.bot = bot

    # get the possible drops for mining
    loot_table = get_skill_drops("mining")

    # emojis for mining
    marker = ":small_red_triangle_down:"
    marker_notch = ":black_small_square:"
    placeholder = "<:covered_grid:1203810768248643605>"
    empty = "<:empty_grid:1203810769880354987>"
    wyrmhole = "<a:wyrmhole:1204212299804442624>"

    copper = loot_table["copper_ore"].emoji
    iron = loot_table["iron_ore"].emoji
    gold = loot_table["gold_ore"].emoji

    # Reactor slots
    core_slots = ["core_slot1", "core_slot2", "core_slot3", "core_slot4"]

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
        item_pool = {"scarab_bomb": 20, "copper_ore": 1000, "iron_ore": 300, "gold_ore": 100}
        common_items = ["copper_ore", "iron_ore", "gold_ore"]
        num_cols = 5

        def __init__(self) -> None:
            self.nodes = []
            self.implosion_gem_rolled = False
            for _ in range(self.num_cols):
                self.nodes.append(self.create_node())
            # Always add 1 implosion gem to the nodes
            self.nodes[random.randint(0, 4)] = (MiningCog.loot_table["implosion_gemstone"], 1)

        def create_node(self):
            item_pool = self.item_pool
            item_id = random.choice(item_pool.keys())

            item = MiningCog.loot_table[item_id]
            quantity = item_pool[item_id]
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
            self.embed.set_footer(text="Better luck next time.")
            for item, amount in self.loot.items():
                await create_item(self.user, item_id=item.item_id, quantity=amount)
                if item.item_id == "implosion_gemstone":
                    self.embed.set_footer(text="Congratulations!")

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

            # Roll for a wyrmhole everytime we make a grid
            wyrmhole = False
            gem_bonus = 0
            for slot in MiningCog.core_slots:
                if user.get_field("mining")[slot]:
                    if "implosion_gemstone" in user.get_field("items").keys():
                        gem_bonus += 500
                    else:
                        gem_bonus += 5000
            wyrmhole_odds = 25000 - gem_bonus
            for i in range(self.mineshaft.num_cols):
                new_col = []
                for j in range(self.mineshaft.num_rows):
                    if i > 1 and (random.randint(0, wyrmhole_odds) == 15) and not wyrmhole:
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
            xp = self.user.get_field("mining")["xp"]
            overflow_xp, xp_needed = self.user.xp_for_next_level(xp)
            self.embed.add_field(
                name=f"Level {self.user.xp_to_level(xp)} - {overflow_xp:,}/{xp_needed:,} xp",
                value=self.user.create_xp_bar(xp),
                inline=False,
            )
            self.embed.set_footer(text="Mine all the way down to recieve xp!")
            self.update_grid()

        async def on_timeout(self) -> Coroutine[Any, Any, None]:
            embed = discord.Embed(
                title=":zzz: MINE CLOSED.",
                description="Did you... fall asleep? Anyway, check out those spoils!",
                color=discord.Color.dark_gray(),
            )
            embed.add_field(name="Loot :moneybag:", value="", inline=True)

            # Add all the loot we've gotten to the embed on the side
            loot_string = ""
            for loot, amount in self.session["total_loot"].items():
                # If the loot is rare, make it bold
                if loot.rarity >= 5:
                    loot_string += f"\n{loot.emoji} +{amount} **{loot.display_name}**"
                else:
                    loot_string += f"\n{loot.emoji} +{amount} {loot.display_name}"
            embed.set_field_at(0, name="Loot :moneybag:", value=loot_string)

            current_time = time.time()
            stats = (
                f"Lodes mined: **{self.session['total_lodes_mined']:,}** lodes!\n"
                f"Time spent: {timestamp_to_english(current_time-self.session['start_time'])}"
            )
            embed.add_field(
                name="Stats",
                value=stats,
            )
            self.clear_items()
            self.stop()

            await self.interaction.edit_original_response(embed=embed, view=None)

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
                self.embed.set_field_at(
                    0, name="Mineshaft :ladder:", value=value + "".join(row) + "\n"
                )

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
            rewarded_xp = 10 * len(self.cols)
            await self.user.inc_xp(skill="mining", xp=rewarded_xp, interaction=interaction)
            xp = self.user.get_field("mining")["xp"]
            overflow_xp, xp_needed = self.user.xp_for_next_level(xp)
            self.embed.set_field_at(
                2,
                name=f"Level {self.user.xp_to_level(xp)} - {overflow_xp:,}/{xp_needed:,} xp",
                value=self.user.create_xp_bar(xp),
                inline=False,
            )
            choices = ["a wyrmhole", "a gemstone", "an oreore", "some friends lol"]
            self.embed.set_footer(text=f"What's one more? Might find {random.choice(choices)}!")

            # Roll for the scarab
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
            lodes = self.pv.session["total_lodes_mined"]

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
        items = user.get_field("items")
        xp = mining["xp"]
        level = user.xp_to_level(xp)

        # Initialize a menu handler
        handler = MenuHandler()

        embed = Cembed(
            title=f"You are: `Level {level}`",
            color=discord.Color.from_str("0xe82f22"),
            interaction=interaction,
            activity="mining",
        )
        balances = (
            f"{MiningCog.copper} **COPPER**: {items['copper_ore']['quantity']:,}\n"
            f"{MiningCog.iron} **IRON**: {items['iron_ore']['quantity']:,}\n"
            f"{MiningCog.gold} **GOLD**: {items['gold_ore']['quantity']:,}"
        )
        embed.add_field(
            name="Balances",
            value=balances,
        )
        embed.add_field(
            name="Lodes Mined", value=f":pick: **{mining['lodes_mined']:,}** lodes", inline=False
        )

        # Ugliest line of code you'll ever see xD
        embed.set_thumbnail(url=f"{IMAGES_REPO}/skills/mining.png")

        mine_view = MiningCog.MiningView(
            interaction=interaction,
            user=user,
            session={"total_loot": {}, "total_lodes_mined": 0, "start_time": time.time()},
        )

        class MainMenu(Menu):
            def __init__(self, handler: MenuHandler, embed=None):
                super().__init__(handler, embed)
                self.handler.add_menu(Reactor(self.handler))

            @discord.ui.button(label="Mine", style=discord.ButtonStyle.gray)
            async def mine(self, interaction: Interaction, button: discord.Button) -> Any:
                await interaction.response.edit_message(
                    embed=mine_view.embed,
                    view=mine_view,
                )

            @discord.ui.button(label="Reactor", style=discord.ButtonStyle.gray)
            async def reactor(self, reactor_interaction: Interaction, button: discord.Button):
                if not await button_check(reactor_interaction, [interaction.user.id]):
                    return
                self.handler.move_forward()
                menu = self.handler.get_current()
                await reactor_interaction.response.edit_message(embed=menu.embed, view=menu)

        class Reactor(Menu):
            def __init__(self, handler: MenuHandler):
                super().__init__(handler)
                self.mining = user.get_field("mining")
                self.reactor_level = mining["prestige_level"]
                self.embed = Cembed(
                    title=f"Reactor: {self.reactor_level:,}",
                    description="Level up your reactor for passive mining and to mine more nodes!",
                    color=discord.Color.from_str("0x0408dd"),
                    interaction=interaction,
                    activity="Reactor",
                )

                # Show the core slots for the reactor
                reactor_field = ""
                for i, core in enumerate(MiningCog.core_slots):
                    if not mining[core]:
                        reactor_field += f"Core `{i+1}`: {MiningCog.empty}\n"
                        self.insert_button.disabled = False
                        self.insert_button.style = discord.ButtonStyle.gray
                    else:
                        reactor_field += (
                            f"Core `{i+1}`: {MiningCog.loot_table[mining[core]].emoji}\n"
                        )
                self.embed.add_field(name="Cores", value=reactor_field)
                self.embed.add_field(
                    name="Auto-miner", value=f"You have {mining['reactor_lodes_mined']} many lodes."
                )
                self.embed.add_field(
                    name="Lodes Auto-mined",
                    value=f":pick: **{mining['reactor_lodes_mined']:,}** lodes",
                    inline=False,
                )

            @discord.ui.button(label="Insert Gems", disabled=True, style=discord.ButtonStyle.gray)
            async def insert_button(self, interaction: Interaction, button: discord.Button):
                pass

            @discord.ui.button(label="Claim", disabled=False, style=discord.ButtonStyle.gray)
            async def claim_button(self, interaction: Interaction, button: discord.Button):
                last_mined = mining["last_auto_mine"]
                now = time.time()
                times_mined = int((now - last_mined / 60) / 30)
                auto_mined_lodes = ""
                for _ in range(0, self.reactor_level * times_mined):
                    # Choose a depth to mine at based on reactor level
                    depth = math.ceil(self.reactor_level / 5) - 1
                    depth = 4 if depth > 4 else depth
                    level = MiningCog.Mineshaft.levels[depth]

                    # We want to roll the rarest items first
                    level.reverse()
                    for item_id in level:
                        item = MiningCog.loot_table[item_id]
                        quantity = roll_item(item)
                        if quantity:
                            item, quantity
                        else:
                            MiningCog.loot_table["copper_ore"], 5
                    auto_mined_lodes += f"{MiningCog.loot_table[item_id].emoji}"

                self.embed.set_field_at(1, name="Auto-miner", value="")
                self.embed.set_field_at(
                    2,
                    name="Lodes Auto-mined",
                    value=f":pick: **{mining['reactor_lodes_mined']:,}** lodes",
                    inline=False,
                )
                mining["last_auto_mine"] = time.time()
                await user.save()

        class Shop(Menu):
            def __init__(self, handler: MenuHandler, embed=None):
                super().__init__(handler, embed)
                self.embed = Cembed(title=f"Shop!")

        mine_menu = MainMenu(handler=handler, embed=embed)
        await interaction.response.send_message(embed=mine_menu.embed, view=mine_menu)


async def setup(bot):
    await bot.add_cog(MiningCog(bot))
