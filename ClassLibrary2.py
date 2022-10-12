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
from mymodels import *
# Other imports
import randfacts

"""This file is used for storing classes that I use for the different aspects of the bot."""
class Rank:
    ranks = []

    def __init__(self, name, wage, work_dialogue, emoji, token_price, rank_description, permissions) -> None:
        self.name = name
        self.wage = wage
        self.work_dialogue = work_dialogue
        self.emoji = emoji
        self.token_price = token_price
        self.rank_description = rank_description
        self.permissions = permissions
        Rank.ranks.append(self)
        
    def __repr__(self) -> str:
        return f"Rank: {self.name}\n" \
               f"Wage: {self.wage}\n" \
               f"Price: {self.token_price}"
            
class RequestUser:
    def __init__(self, user_id) -> None:
        # Establish a connection to the database
        try:
            mmdatabase.connect()
            print("Successfully connected!")
        except peewee.DatabaseError as error:
            print(f"Error connecting to PGSQL Database.\nError: {error}")
            
        # If the provided User ID is in the database, fetch all related tables
        self.instance, self.created_user = dbUser.get_or_create(id=user_id)
        self.cooldowns, self.created_cooldowns = dbUserCooldowns.get_or_create(id=user_id)
        self.farm, self.created_farm = dbFarms.get_or_create(id=user_id)
        self.pets = UserPets(user_id=user_id)
                
    def work(self, ctx):
        SIX_HOURS_IN_SECONDS = 21600 # Six hours in seconds
        work_used_last = self.cooldowns.work_used_last
        now = datetime.datetime.now().timestamp()
        work_off_cooldown = int(work_used_last) + SIX_HOURS_IN_SECONDS
        if now <= work_off_cooldown:
            # If it has NOT been 6 hours since they last used the work command
            work_on_cooldown_embed = discord.Embed(color=discord.Colour.red())
            work_on_cooldown_embed.add_field(name=f"You already collected your work!", value=f"Next in: **{work_off_cooldown-now}**")
            work_on_cooldown_embed.set_footer(text=f"User: {ctx.author.name}")
            return work_on_cooldown_embed
        else:
            placeholder_embed = discord.Embed(title="Success", color=discord.Colour.blue())
            return placeholder_embed
            
    
    def daily(self, ctx):
        TWENTY_ONE_HOURS_IN_SECONDS = 75600
        daily_used_last = self.cooldowns.daily_used_last
        now = datetime.datetime.now().timestamp()
        daily_off_cooldown = int(daily_used_last) + TWENTY_ONE_HOURS_IN_SECONDS
        if now <= daily_off_cooldown:
            # If it has NOT been 6 hours since they last used the work command
            work_on_cooldown_embed = discord.Embed(color=discord.Colour.red())
            work_on_cooldown_embed.add_field(name=f"You already collected your work!", value=f"Next in: **{daily_off_cooldown-now}**")
            work_on_cooldown_embed.set_footer(text=f"User: {ctx.author.name}")
            return work_on_cooldown_embed
        else:
            placeholder_embed = discord.Embed(title="Success", color=discord.Colour.blue())
            return placeholder_embed

    # Function to update a user's balance
    def update_balance(self, amount, bank: bool = False):
        if bank:
            self.instance.bank += amount
        else:
            self.instance.money += amount
        self.instance.save()
        
    # Function to update a user's tokens
    def update_tokens(self, amount):
        self.instance.tokens += amount
        self.instance.save()
        
    # Function to set a user's game status to 1 (true)
    def update_game_status(self, in_game: bool):
        # When the status's are updated, it also updates self.in_game to True or False
        # Now just self.in_game is required to check status
        self.instance.in_game = in_game
        self.instance.save()
        
    # Checks to make sure the user isn't betting more than they have or 0
    def bet_checks(self, bet) -> object:
        user_balance = self.instance.money
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
            
    # On cleanup of the object, close the connection to the database
    def __del__(self):
        mmdatabase.close()
        print("Closed connection.")
        
class Pet:
    def __init__(self, pet_id) -> None:
        self.instance = dbPets.get(pet_id=pet_id)
        
    def feed(self):
        pass
        
    

class UserPets:
    def __init__(self, user_id) -> None:
        self.pets = dbPets.select().where(dbPets.owner == user_id).objects()
        self.active_pet: dbPets = dbPets.get(dbPets.owner == user_id and dbPets.active == True)
        self.pet_embed = discord.Embed(title=f"Active Pet: {self.active_pet.name}", color=pets[self.active_pet.rarity]['color'])
        self.pet_embed.add_field(name="Rarity", value=f"{self.active_pet.rarity.replace('_', ' ')}")
        self.pet_embed.add_field(name="Species", value=f"{pets[self.active_pet.rarity]['animals'][self.active_pet.species]['emoji']}")
        self.pet_embed.add_field(name="Health", value=f"**{self.active_pet.health}/{pets[self.active_pet.rarity]['health']}**", inline=False)
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
