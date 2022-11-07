# General python imports
from hashlib import new
import random
from random import randint
import datetime
from tkinter import E
import numpy
from dataclasses import dataclass
from typing import Callable
import asyncio
import json
# Discord imports
import discord
from discord.ext import commands
# Database imports
import peewee as pw
# File import
from Cogs.Pets import pets
from mymodels import database as mmdatabase
import mymodels as mm
# Other imports
import randfacts

"""This file is used for storing classes that I use for the different aspects of the bot."""
# Load the json file where all the rank dialogue is stored
with open('./EconomyBotProjectFiles/ranks.json', 'r') as file:
    ranks = json.load(file)
with open('./EconomyBotProjectFiles/areas.json', 'r') as file:
    areas = json.load(file)


class RequestUser:
    def __init__(self, user_id, interaction) -> None:
        try:  # Establish a connection to the database
            mmdatabase.connect()
        except pw.DatabaseError as error:
            print(f"Error connecting to PGSQL Database.\nError: {error}")

        # If the provided User ID is in the database, fetch all related tables
        self.interaction = interaction
        self.instance, self.created_user = mm.Users.get_or_create(id=user_id)
        self.cooldowns, self.created_cooldowns = mm.Usercooldowns.get_or_create(id=user_id)
        self.farm, self.created_farm = mm.Farms.get_or_create(id=user_id)
        self.pets = UserPets(user_id=user_id)
        self.pet = self.pets.active_pet
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
        off_cooldown = description = title = None

        match check_in_type:  # Match statement to check which type of cooldown we need to test
            case 'work':
                off_cooldown = work_off_cooldown
            case 'daily':
                off_cooldown = daily_off_cooldown

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
                description = f"**{self.rank.capitalize()}** wage\n" \
                              f" :money_with_wings: **+{'{:,}'.format(wage)} bits**"
                if self.pet:
                    work_multiplier = pets[self.pet.rarity]['multipliers']['work']
                    description += f"\n:money_with_wings: **+{'{:,}'.format(int(wage*work_multiplier))} bits** (pet bonus)"
                    self.update_balance(wage*work_multiplier)
                else:
                    self.update_balance(wage)
                self.cooldowns.worked_last = now
            case 'daily':
                wage = areas[str(self.instance.area)]['tokens']
                title = f"Daily Tokens"
                description = f"**{areas[str(self.instance.area)]['name'].capitalize()}** Standard\n" \
                              f"**:coin: +{wage} tokens**"
                if self.pet:
                    daily_multiplier = pets[self.pet.rarity]['multipliers']['daily']
                    description += f"\n:coin: **+{int(wage * daily_multiplier)} tokens** (pet bonus)"
                    self.update_tokens(wage * daily_multiplier)
                else:
                    self.update_tokens(wage)
                self.cooldowns.daily_used_last = now
        check_in_embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        check_in_embed.set_author(name=f"{interaction.user.name} - "
                                       f"{check_in_type}", icon_url=interaction.user.display_avatar)
        if check_in_type == 'daily':
            check_in_embed.add_field(name=f"Random Fact", value=f'{randfacts.get_fact()}', inline=False)
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
        self.instance = mm.Pets.get(pet_id=pet_id)

    def feed(self):
        pass


class UserPets:
    def __init__(self, user_id) -> None:
        self.pets = mm.Pets.select().where(mm.Pets.owner_id == user_id).objects()
        self.active_pet = mm.Pets.select().where((mm.Pets.owner_id == user_id) & mm.Pets.active).get()
        self.pet_embed = discord.Embed(title=f"Active Pet: {self.active_pet.name}",
                                       color=pets[self.active_pet.rarity]['color'])
        self.pet_embed.add_field(name="Rarity", value=f"{self.active_pet.rarity.replace('_', ' ')}")
        self.pet_embed.add_field(name="Species",
                                 value=f"{pets[self.active_pet.rarity]['animals'][self.active_pet.species]['emoji']}")
        self.pet_embed.add_field(name="Health",
                                 value=f"**{self.active_pet.health}/{pets[self.active_pet.rarity]['health']}**",
                                 inline=False)
        self.pet_embed.add_field(name="Level", value=f"{self.active_pet.level}")

    def switch_active_pet(self, pet_id):
        for pet in self.pets:
            if pet.pet_id == pet_id:
                # Set current active pet to inactive
                self.active_pet.active = False
                self.active_pet.save()
                # Update matching pet to be active and to be objects active pet
                pet.active = True
                self.active_pet = pet
                pet.save()

    def rename_pet(self, new_name):
        self.active_pet.name = new_name
        self.active_pet.save()
        return new_name
