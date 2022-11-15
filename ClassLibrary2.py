# General python imports
import random
from random import randint
import datetime
import numpy

import mymodels as mm
import json
# Discord imports
import discord
# Database imports
import peewee as pw
# File import
from mymodels import database as mmdatabase
# Other imports
import randfacts

"""This file is used for storing classes that I use for the different aspects of the bot."""
# Load the json file where all the rank dialogue is stored
with open('projfiles/ranks.json', 'r') as ranks_file:
    ranks = json.load(ranks_file)
with open('projfiles/areas.json', 'r') as areas_file:
    areas = json.load(areas_file)
with open('projfiles/pets.json', 'r') as pets_file:
    pets = json.load(pets_file)
with open('projfiles/megadrop.json', 'r') as megadrop_file:
    megadrop = json.load(megadrop_file)
with open('projfiles/items/axes.json', 'r') as axes_file:
    axes = json.load(axes_file)
with open('projfiles/items/treeitems.json', 'r') as treeitems_file:
    treeitems = json.load(treeitems_file)
with open('projfiles/items/crops.json', 'r') as crops_file:
    crops = json.load(crops_file)


class RequestUser:
    def __init__(self, user_id, interaction) -> None:
        try:  # Establish a connection to the database
            mmdatabase.connect(reuse_if_open=True)
        except pw.DatabaseError as error:
            print(f"Error connecting to Database.\nError: {error}")

        # If the provided User ID is in the database, fetch all related tables
        self.interaction = interaction
        self.instance, self.created_user = mm.Users.get_or_create(id=user_id)
        self.cooldowns, self.created_cooldowns = mm.Usercooldowns.get_or_create(id=user_id)
        self.farm, self.created_farm = mm.Farms.get_or_create(id=user_id)
        self.items = mm.Items.select().where(mm.Items.owner_id == user_id).objects()
        try:
            active_pet = mm.Pets.select().where((mm.Pets.owner_id == user_id) & mm.Pets.active).get()
            self.active_pet = Pet(active_pet.id)
        except mm.DoesNotExist:
            self.active_pet = None
        for rank in ranks:
            role_in_discord = discord.utils.get(interaction.guild.roles, name=rank.capitalize())
            if role_in_discord in interaction.user.roles:
                self.rank = rank

    async def check_ins(self, interaction, check_in_type):
        TWENTY_ONE_HOURS_IN_SECONDS = 75600  # Used for checking seconds between DAILY cooldown
        SIX_HOURS_IN_SECONDS = 21600  # Used for checking seconds between WORK cooldown
        now = datetime.datetime.now().timestamp()  # Current time, used to compare with last used time
        work_off_cooldown = int(self.cooldowns.worked_last) + SIX_HOURS_IN_SECONDS
        daily_off_cooldown = int(self.cooldowns.daily_used_last) + TWENTY_ONE_HOURS_IN_SECONDS
        description = title = None

        off_cooldown = work_off_cooldown if check_in_type == 'work' else daily_off_cooldown

        if int(now) <= int(off_cooldown):  # If it has NOT been enough time since they last used the command
            on_cooldown_embed = discord.Embed(color=discord.Colour.red())
            cd_left_in_seconds = int(off_cooldown - int(now))
            day = cd_left_in_seconds // 86400
            hours = (cd_left_in_seconds - (day * 86400)) // 3600
            minutes = (cd_left_in_seconds - ((day * 86400) + (hours * 3600))) // 60
            seconds = cd_left_in_seconds - ((day * 86400) + (hours * 3600) + (minutes * 60))
            cool_down_left_formatted = datetime.time(hours, minutes, seconds)
            on_cooldown_embed.add_field(name=f"You already collected your {check_in_type}!",
                                        value=f"Next in: **{cool_down_left_formatted}**")
            on_cooldown_embed.set_footer(text=f"User: {interaction.user.name}")
            await interaction.response.send_message(embed=on_cooldown_embed)
            return
        match check_in_type:  # Match statement to check which type of cooldown we need to test
            case 'work':  # If the checkin type is work, set title and description
                wage = ranks[self.rank]['wage']
                title = random.choice(ranks[self.rank]['responses'])
                description = f" :money_with_wings:" \
                              f" **+{'{:,}'.format(wage)} bits** ({self.rank.capitalize()} wage)"
                if self.active_pet:
                    work_multiplier = pets[self.active_pet.instance.rarity]['bonuses']['work']
                    description += f"\n:money_with_wings: " \
                                   f"**+{'{:,}'.format(int(wage * work_multiplier))} bits** (pet bonus)"
                    self.update_balance(wage + wage * work_multiplier)
                else:
                    self.update_balance(wage)
                self.cooldowns.worked_last = now
            case 'daily':
                wage = areas[str(self.instance.area)]['tokens']
                title = f"Daily Tokens"
                description = f"**:coin:" \
                              f" +{wage} tokens** ({areas[str(self.instance.area)]['name'].capitalize()} standard)"
                if self.active_pet:
                    pet_bonus = pets[self.active_pet.instance.rarity]['bonuses']['daily']
                    description += f"\n:coin:" \
                                   f" **+{int(pet_bonus)} tokens** (pet bonus)"
                    self.update_tokens(wage + pet_bonus)
                else:
                    self.update_tokens(wage)
                self.cooldowns.daily_used_last = now
        check_in_embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        check_in_embed.set_author(name=f"{interaction.user.name} - "
                                       f"{check_in_type}", icon_url=interaction.user.display_avatar)
        if check_in_type == 'daily':
            check_in_embed.add_field(name="Your Tokens",
                                     value=f"You have **{'{:,}'.format(self.instance.tokens)}** tokens")
            check_in_embed.add_field(name=f"Random Fact", value=f'{randfacts.get_fact()}', inline=False)
        elif check_in_type == 'work':
            check_in_embed.add_field(name="Your Bits",
                                     value=f"You have **{'{:,}'.format(int(self.instance.money))}** bits in your purse")
        check_in_embed.set_footer(text="Increase your profits by unlocking better pets and ranking up.")
        await interaction.response.send_message(embed=check_in_embed)
        self.cooldowns.save()

    def update_balance(self, amount, bank: bool = False):  # Function to update a user's balance
        if bank:
            self.instance.bank += amount
        else:
            self.instance.money += amount
        self.instance.save()

    def update_tokens(self, amount):  # Function to update a user's tokens
        self.instance.tokens += amount
        self.instance.save()

    def update_game_status(self, in_game: bool):  # Function to set a user's game status to true
        self.instance.in_game = in_game
        self.instance.save()

    def bet_checks(self, bet) -> object:  # Checks to make sure the user isn't betting more than they have or 0
        user_balance = self.instance.money
        if int(bet) > user_balance:  # If they try to bet more than they have in their account.
            return f"You don't have enough to place this bet. Balance: {user_balance} bits", False
        elif int(bet) < 0:  # If their bet is <= 0, stop the code.
            return f"You can't bet a negative amount.", False
        elif bet == 0:
            return "You can't bet 0 bits.", False
        else:
            return "Passed", True

    def __del__(self):  # On cleanup of the object, close the connection to the database
        mmdatabase.close()


class Pet:
    def __init__(self, pet_id) -> None:
        self.instance = mm.Pets.get(id=pet_id)
        self.pet_embed = discord.Embed(title=f"Pet: {self.instance.name}",
                                       color=discord.Color.from_str(pets[self.instance.rarity]['color']))
        self.pet_embed.add_field(name="Rarity", value=f"{self.instance.rarity.replace('_', ' ')}")
        self.pet_embed.add_field(name="Species",
                                 value=f"{pets[self.instance.rarity]['animals'][self.instance.species]['emoji']}")
        self.pet_embed.add_field(name="Health",
                                 value=f"**{self.instance.health}/{pets[self.instance.rarity]['health']}**",
                                 inline=False)
        self.pet_embed.add_field(name="Level", value=f"{self.instance.level}")

    def feed(self, crop):
        pass

    def switch_active_pet(self, pet_id):
        for pet in mm.Pets.select().objects():
            if pet.pet_id == pet_id:  # Set current active pet to inactive
                self.instance.active = False
                self.instance.save()
                pet.active = True  # Update matching pet to be active and to be objects active pet
                pet.save()

    def rename(self, new_name):
        self.instance.name = new_name
        self.instance.save()
        return new_name


class Tree:
    rare_drops = [item for item in treeitems]
    tree_heights = [randint(20, 40), randint(40, 50), randint(50, 60), randint(90, 100)]

    def __init__(self, user1):
        self.height = numpy.random.choice(Tree.tree_heights, p=[0.499, 0.300, 0.200, 0.001])
        self.hitpoints = round(self.height / 2)
        self.rare_drops = Tree.rare_drops
        self.embed = None
        self.user1, self.user2 = user1, None
        self.user1_chopping_power = axes[self.user1.instance.axe.reference_id]['chopping_power']
        self.user2_chopping_power = None

    @property
    def hitpoints(self):
        return self._hitpoints

    @hitpoints.setter
    def hitpoints(self, new_hitpoints):
        if new_hitpoints <= 0:
            self._hitpoints = 0
            self.embed = self.on_chopped_down()
        else:
            self._hitpoints = new_hitpoints

    def on_chopped_down(self):
        chopped_embed = discord.Embed(
            title="Tree chopped! :evergreen_tree:",
            description=f"{self.user1.name} and {self.user2.name} "
                        f"successfully chopped down a **{self.height}ft** tree!",
            color=0x573a26
        )
        return chopped_embed
