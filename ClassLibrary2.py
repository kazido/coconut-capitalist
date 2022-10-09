# General python imports
from cgi import parse_multipart
import datetime
from lib2to3.pgen2 import token
import random
from random import randint
from tkinter import E
import numpy
from dataclasses import dataclass
from typing import Callable
import asyncio
import json
import sqlite3
# Discord imports
import discord
from discord.ext import commands
# Database imports
import psycopg2
import sqlalchemy
import peewee as pw
# File import
from Cogs.Pets import pet_multipliers
from mymodels import *
# Other imports
import randfacts

"""This file is used for storing classes that I use for the different aspects of the bot."""
# Necesarry for setting up connection to the database

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
            
class User2:
    def __init__(self, discord_id) -> None:
        if dbUser.get(dbUser.id == discord_id):
            self.dbinstance = dbUser.get(dbUser.id == discord_id)
        else:
            self.dbinstance = dbUser.create(id=discord_id)