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
