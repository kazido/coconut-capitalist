# General python imports
import datetime
import random
from random import randint
import numpy
from dataclasses import dataclass
import json
import sqlite3
# Discord imports
import discord
from discord.ext import commands
# Database imports
# File import
# Other imports
import randfacts

"""This file is used for storing classes that I use for the different aspects of the bot."""


# function to get the discord role from a user: takes in context
def get_role(ctx):
    for rank in list_of_ranks:
        # grabs the corresponding role from discord and returns it
        role_in_discord = discord.utils.get(ctx.guild.roles, name=rank.name.capitalize())
        if role_in_discord in ctx.author.roles:
            return rank


# The primary function of this embed is to calculate the time remaining until command is off cooldown
# and to display it with a red embed
async def cool_down_embed(off_cd, ctx, now, command):
    cd_left_in_seconds = int(off_cd - now)
    day = cd_left_in_seconds // 86400
    hours = (cd_left_in_seconds - (day * 86400)) // 3600
    minutes = (cd_left_in_seconds - ((day * 86400) + (hours * 3600))) // 60
    seconds = cd_left_in_seconds - ((day * 86400) + (hours * 3600) + (minutes * 60))
    cool_down_left_formatted = datetime.time(hours, minutes, seconds)
    embed = discord.Embed(color=discord.Colour.red())
    embed.add_field(name=f"You already collected your {command}", value=f"Next in: **{cool_down_left_formatted}**")
    embed.set_footer(text=f"User: {ctx.author.name}")
    await ctx.send(embed=embed)


# Load the json file where all the rank dialogue is stored
with open('projfiles/ranks.json', 'r') as file:
    ranks = json.load(file)


@dataclass
class Rank:
    name: str
    wage: int
    work_dialogue: list
    emoji: str
    price: int
    description: str
    perms: list

    def work(self):
        return random.choice(self.work_dialogue)


peasant = Rank("Peasant", 2500, ranks['peasant']['responses'], ":palms_up_together:", 0,
               ranks['peasant']['description'], ranks['peasant']['perks'])
farmer = Rank("Farmer", 10000, ranks['farmer']['responses'], ":basket:", 10, ranks['farmer']['description'],
              ranks['farmer']['perks'])
citizen = Rank("Citizen", 25000, ranks['citizen']['responses'], ":busts_in_silhouette:", 45,
               ranks['citizen']['description'], ranks['citizen']['perks'])
educated = Rank("Educated", 60000, ranks['educated']['responses'], ":book:", 100, ranks['educated']['description'],
                ranks['educated']['perks'])
cultured = Rank("Cultured", 130000, ranks['cultured']['responses'], ":money_with_wings:", 250,
                ranks['cultured']['description'], ranks['cultured']['perks'])
weathered = Rank("Weathered", 240000, ranks['weathered']['responses'], ":mountain:", 500,
                 ranks['weathered']['description'], ranks['weathered']['perks'])
wise = Rank("Wise", 375000, ranks['wise']['responses'], ":trident:", 1000, ranks['wise']['description'],
            ranks['wise']['perks'])
expert = Rank("Expert", 1000000, ranks['expert']['responses'], ":gem:", 10000, ranks['expert']['description'],
              ranks['expert']['perks'])

list_of_ranks = [peasant, farmer, citizen, educated, cultured, weathered, wise, expert]


# This class will have methods to update the user's money, statuses, and id.
class User:
    def __init__(self, ctx: discord.ext.commands.Context = None, interaction: discord.Interaction = None):
        if ctx and not interaction:
            self.user_id = ctx.author.id
            self.bot = ctx.bot
            self.ctx = ctx
        elif interaction and not ctx:
            self.user_id = interaction.user.id
            self.bot = interaction.client
            self.interaction = interaction
        try:
            # self.connection = .connect()
            # self.cursor = self.sqliteConnection.cursor()
            print("User object initialized, connected to database.")
        except sqlite3.Error as error:
            print(f"Ran into {error} whilst attempting to connect to the database.")

    async def work(self):
        # Calculates time left until work can be used (6 hour cooldown)
        now = datetime.datetime.now().timestamp()
        work_off_cd = int(await self.worked_last()) + 21600
        # If the command is not ready yet
        if now <= work_off_cd:
            await cool_down_embed(work_off_cd, self.ctx, now, "work")
            return
        else:
            # update the cooldown
            role = get_role(self.ctx)
            embed = discord.Embed(
                color=discord.Color.blue()
            )
            pet_check_statement = """SELECT rarity FROM pets WHERE (owner_id = ? AND active = 1)"""
            self.cursor.execute(pet_check_statement, [self.user_id])
            active_pet_rarity = self.cursor.fetchall()[0][0]
            # If the user has a pet and the bonus isn't 0, send an embed showing the pet bonus
            if active_pet_rarity and role.wage * pets[active_pet_rarity]['multipliers']['work'] != 0:
                work_pet_bonus = role.wage * pets[active_pet_rarity]['multipliers']['work']
                await self.update_balance(role.wage + int(work_pet_bonus))
                embed.add_field(name=f"{role.work()}", value=f"You received **{'{:,}'.format(role.wage)}** bits\n"
                                                             f"Your pet earned you an extra **{'{:,}'.format(int(work_pet_bonus))}** bits",
                                inline=False)
            else:
                await self.update_balance(role.wage)
                embed.add_field(name=f"{role.work()}", value=f"You received **{'{:,}'.format(role.wage)}** bits",
                                inline=False)
            embed.add_field(name="Bits",
                            value=f"You have {'{:,}'.format(await self.check_balance('bits'))} bits",
                            inline=False)
            embed.set_footer(text=f"User: {self.ctx.author.name}")
            await self.ctx.send(embed=embed)
            # UPDATE Work cooldown LAST so there are no errors when it can't be set
            update_work_cooldown = """UPDATE user_cooldowns set worked_last = ? WHERE user_id = ?"""
            self.cursor.execute(update_work_cooldown, (now, self.user_id))
            self.sqliteConnection.commit()

    async def daily(self):
        # Calculate timestamp when command will be off cool down
        ct = datetime.datetime.now()
        now = ct.timestamp()
        off_cd = await self.daily_used_last() + 79200
        # Check when daily was last used
        if now <= off_cd:
            # Converting seconds left into an actual cool down formatted properly in HH:MM:SS
            await cool_down_embed(off_cd, self.ctx, now, "daily")
            return
        else:
            update_daily_cooldown = """UPDATE user_cooldowns set daily_used_last = ? WHERE user_id = ?"""
            self.cursor.execute(update_daily_cooldown, (now, self.user_id))
            self.sqliteConnection.commit()
            daily_amount = 1
            embed = discord.Embed(
                color=discord.Color.blue()
            )
            pet_check_statement = """SELECT rarity FROM pets WHERE (owner_id = ? AND active = 1)"""
            self.cursor.execute(pet_check_statement, [self.user_id])
            active_pet_rarity = self.cursor.fetchall()[0][0]
            if active_pet_rarity and daily_amount * pet_multipliers[active_pet_rarity["rarity"]]["daily"] != 0:
                daily_pet_bonus = daily_amount * pet_multipliers[active_pet_rarity["rarity"]]["daily"]
                await self.update_tokens(daily_amount + daily_pet_bonus)
                embed.add_field(name=f"Received {'{:,}'.format(daily_amount)} + ({'{:,}'.format(daily_pet_bonus)} "
                                     f"*pet bonus*) tokens",
                                value=f"You have {'{:,}'.format(await self.check_balance('tokens'))} tokens",
                                inline=False)
            else:
                await self.update_tokens(daily_amount)
                embed.add_field(name=f"Received {'{:,}'.format(daily_amount)} tokens",
                                value=f"You have {'{:,}'.format(await self.check_balance('tokens'))} tokens",
                                inline=False)
            embed.add_field(name=f"Random Fact", value=f'{randfacts.get_fact()}', inline=False)
            embed.set_footer(text=f"User: {self.ctx.author.name}")
            await self.ctx.send(embed=embed)

    # Function used to check balance. Can input either 'bits' or 'tokens' to check the corresponding database values
    async def check_balance(self, balance_type):
        statement = "SELECT " + balance_type + " FROM users WHERE user_id = ?"
        self.cursor.execute(statement, [self.user_id])
        balance = self.cursor.fetchall()[0][0]
        return balance

    # Function used to xp of given user in the database
    async def check_xp(self):
        statement = "SELECT xp FROM users WHERE user_id = ?"
        self.cursor.execute(statement, [self.user_id])
        user_worked_last = self.cursor.fetchall()[0][0]
        return user_worked_last

    # Function used to get timestamp of last time -daily was used
    async def daily_used_last(self):
        statement = "SELECT daily_used_last FROM user_cooldowns WHERE user_id = ?"
        self.cursor.execute(statement, [self.user_id])
        daily_used_last = self.cursor.fetchall()[0][0]
        return daily_used_last

    # Function used to get timestamp of last time -work was used
    async def worked_last(self):
        statement = "SELECT worked_last FROM user_cooldowns WHERE user_id = ?"
        self.cursor.execute(statement, [self.user_id])
        work_used_last = self.cursor.fetchall()[0][0]
        return work_used_last

    # Function to update a user's balance
    async def update_balance(self, amount, bank: bool = False):
        if bank:
            update_balance = """UPDATE users set bank = bank + ? WHERE user_id = ?"""
            self.cursor.execute(update_balance, [amount, self.user_id])
        else:
            update_balance = """UPDATE users set bits = bits + ? WHERE user_id = ?"""
            self.cursor.execute(update_balance, [amount, self.user_id])
        self.sqliteConnection.commit()

    # Function to update a user's tokens
    async def update_tokens(self, amount):
        update_tokens = """UPDATE users set tokens = tokens + ? WHERE user_id = ?"""
        self.cursor.execute(update_tokens, (amount, self.user_id))
        self.sqliteConnection.commit()

    # Function to set a user's game status to 1 (true)
    async def game_status_to_true(self):
        # When the status's are updated, it also updates self.in_game to True or False
        # Now just self.in_game is required to check status
        game_status_to_true = """UPDATE users set in_game = ? WHERE user_id = ?"""
        self.cursor.execute(game_status_to_true, (1, self.user_id))
        self.sqliteConnection.commit()

    # Function to set a user's game status to 0 (false)
    async def game_status_to_false(self):
        game_status_to_false = """UPDATE users set in_game = ? WHERE user_id = ?"""
        self.cursor.execute(game_status_to_false, (0, self.user_id))
        self.sqliteConnection.commit()

    # Checks to make sure the user isn't betting more than they have or 0
    async def bet_checks(self, bet) -> object:
        statement = "SELECT bits FROM users WHERE user_id = ?"
        self.cursor.execute(statement, [self.user_id])
        user_balance = self.cursor.fetchall()[0][0]
        # If they try to bet more than they have in their account.
        if int(bet) > user_balance:
            return f"You don't have enough to place this bet. Balance: {user_balance} bits", False
        # If their bet is <= 0, stop the code.
        elif int(bet) < 0:
            return f"You can't bet a negative amount.", False
        elif bet == 0:
            return "You can't bet 0 bits.", False
        else:
            return "Passed", True


# class Drop:
#     def __init__(self, bot, amount):
#         self.bot = bot
#         self.amount = amount
#
#     def drop_double(self):
#         odds = random.randint(0, 100)
#         if odds in range(0, 5):
#             message = f"claimed a **double** drop! **+{'{:,}'.format(self.amount * 2)}** bits"
#             color = 0xcc8c16
#             return message, self.amount, True, color
#         else:
#             message = f"claimed the drop! **+{'{:,}'.format(self.amount)}** bits"
#             color = 0xf0b57a
#             return message, self.amount, False, color
#
#     async def prep_claim(self, channel):
#         message, drop_amount, is_double, color = self.drop_double()
#         # Embed for a new drop appearing
#         embed = discord.Embed(
#             title="A drop has appeared! 📦",
#             description=f"This drop contains **{'{:,}'.format(self.amount)}** bits!",
#             color=0x946c44
#         )
#         embed.set_footer(text="React to claim!")
#
#         # Embed for when a drop expires after 1 hour
#         expired_embed = discord.Embed(
#             title="This drop expired :(",
#             description=f"This **{'{:,}'.format(self.amount)}** bit drop has expired.",
#             color=0x484a4a
#         )
#         expired_embed.set_footer(text="Drops happen randomly and last for an hour!")
#
#         class ClaimDropButtons(discord.ui.View):
#             async def on_timeout(self) -> None:
#                 if self.claimed:
#                     return
#                 await drop.edit(embed=expired_embed, view=None)
#
#             bot = self.bot
#
#             def __init__(self, *, timeout=3600):
#                 super().__init__(timeout=timeout)
#                 self.claimed = False
#
#             @discord.ui.button(label="CLAIM", style=discord.ButtonStyle.green)
#             async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
#                 user = User(interaction=interaction)
#                 drops_claimed_statement = """SELECT drops_claimed FROM users WHERE user_id = ?"""
#                 user.cursor.execute(drops_claimed_statement, [user.user_id])
#                 drops_claimed = user.cursor.fetchall()[0][0]
#                 claimed_embed = discord.Embed(
#                     title="This drop has been claimed!",
#                     description=f"{interaction.user.name} {message}\nYou have claimed {drops_claimed}",
#                     color=color
#                 )
#                 claimed_embed.set_footer(text="Drops happen randomly and last for an hour!")
#                 if is_double is True:
#                     await user.update_balance(int(drop_amount * 2))
#                 else:
#                     await user.update_balance(int(drop_amount))
#                 await interaction.response.edit_message(embed=claimed_embed, view=None)
#                 self.claimed = True
#
#         drop = await channel.send(embed=embed, view=ClaimDropButtons())


class Inventory:
    def __init__(self, ctx: discord.ext.commands.Context = None, interaction: discord.Interaction = None):
        if ctx and not interaction:
            self.ctx = ctx
            self.bot = ctx.bot
            self.id = ctx.author.id
        elif interaction and not ctx:
            self.id = interaction.user.id
            self.bot = interaction.client
            self.interaction = interaction
        try:
            self.sqliteConnection = sqlite3.connect('economySQLdatabase.sqlite')
            self.cursor = self.sqliteConnection.cursor()
            print("Inventory object initialized, connected to database.")
        except sqlite3.Error as error:
            print(f"Ran into {error} whilst attempting to connect to the database.")

    def add_item(self, item, quantity: int = 1):
        find_existing_item_statement = """SELECT item_name FROM items WHERE owner_id = ? and item_name = ?"""
        self.cursor.execute(find_existing_item_statement, [self.id, item.name])
        try:
            self.cursor.fetchall()[0][0]
        except IndexError:
            insert_new_item_statement = """INSERT INTO items (durability, owner_id, item_name, quantity, rarity) VALUES (?, ?, ?, ?, ?)"""
            self.cursor.execute(insert_new_item_statement, [item.durability, self.id, item.name, quantity, item.rarity])
            self.sqliteConnection.commit()
        else:
            update_item_statement = """UPDATE items SET quantity = quantity + ? WHERE owner_id = ? and item_name = ?"""
            self.cursor.execute(update_item_statement, [quantity, self.id, item.name])
            self.sqliteConnection.commit()

    def remove_item(self, item, quantity=None):
        if isinstance(quantity, int):
            check_remaining_items_statement = """SELECT quantity FROM items WHERE owner_id = ? and item_name = ?"""
            self.cursor.execute(check_remaining_items_statement, [self.id, item.name])
            remaining_items = self.cursor.fetchall()[0][0]
            if remaining_items - quantity >= 0:
                delete_item_statement = """DELETE FROM items WHERE owner_id = ? and item_name = ?"""
                self.cursor.execute(delete_item_statement, [quantity, self.id, item.name])
            else:
                update_quantity_statement = """UPDATE items SET quantity = quantity - ? WHERE owner_id = ? and item_name = ?"""
                self.cursor.execute(update_quantity_statement, [quantity, self.id, item.name])
            self.sqliteConnection.commit()
        else:
            delete_item_statement = """DELETE FROM items WHERE owner_id = ? and item_name = ?"""
            self.cursor.execute(delete_item_statement, [quantity, self.id, item.name])
            self.sqliteConnection.commit()

    def get(self, item=None):
        if item:
            find_item_statement = """SELECT * FROM items WHERE owner_id = ? and item_name = ?"""
            self.cursor.execute(find_item_statement, [self.id, item])
            items = self.cursor.fetchall()[0][0]
        else:
            find_all_items_statement = """SELECT * FROM items WHERE owner_id = ?"""
            self.cursor.execute(find_all_items_statement, [self.id])
            items = self.cursor.fetchall()
        return items


class Item:
    def __init__(self, name: str, price: int = None, durability: int = None, rarity: str = 'common'):
        self.name = name
        self.price = price
        self.durability = durability
        self.rarity = rarity


# Shovels - has durability, can be repaired and upgraded
shovel_lv1 = Item("basic_shovel", price=25000, durability=25)
shovel_lv2 = Item("reinforced_shovel", durability=50, rarity='uncommon')
shovel_lv3 = Item("steel_shovel", durability=100, rarity='rare')
# Rare drop from digging
unbreakable_shovel = Item("SH0V3L", rarity='legendary')

# Fishing Rods - communal pool that resets every day. collection books
fishing_rod = Item("fishing_rod", price=50000)

# Pickaxes - mines are open for a certain time during the day. better pickaxe = more ores
pickaxe_lv1 = Item("pickaxe", price=100000)
pickaxe_lv2 = Item("premium_pickaxe", price=500000, rarity='uncommon')
pickaxe_lv3 = Item("mining_drill", price=1000000, rarity='rare')

# Usable items - still working on these
golden_ticket = Item("golden_ticket", durability=1, rarity='legendary')
robber_token = Item('robber_token', durability=1)

# Seeds - for growing!
almond_seeds = Item("almond_seed", price=10000, durability=1)
coconut_seeds = Item("coconut_seed", price=80000, durability=1)
cacao_seeds = Item("cacao_seed", price=500000, durability=1)

# # Tree Drops
# fine_bark = Item("fine_bark", rarity='legendary')
#
#
# class Tree:
#     rare_drops = [fine_bark]
#     tree_heights = [randint(20, 40), randint(40, 50), randint(50, 60), randint(90, 100)]
#
#     def __init__(self, user1):
#         self.height = numpy.random.choice(Tree.tree_heights, p=[0.499, 0.300, 0.200, 0.001])
#         self.hitpoints = round(self.height / 2)
#         self.rare_drops = Tree.rare_drops
#         self.embed = None
#         self.user1, self.user2 = user1, None
#
#     @property
#     def hitpoints(self):
#         return self._hitpoints
#
#     @hitpoints.setter
#     def hitpoints(self, new_hitpoints):
#         if new_hitpoints <= 0:
#             self._hitpoints = 0
#             self.embed = self.on_chopped_down()
#         else:
#             self._hitpoints = new_hitpoints
#
#     def on_chopped_down(self):
#         chopped_embed = discord.Embed(
#             title="Tree chopped! :evergreen_tree:",
#             description=f"{self.user1.display_name} and {self.user2.display_name} successfully chopped down a **{self.height}ft** tree!",
#             color=0x573a26
#         )
#         return chopped_embed
