import random
import discord
import os
import math

from datetime import time, datetime
from pytz import timezone
from typing import Literal, get_args
from peewee import *
from playhouse.migrate import SqliteMigrator
from logging import getLogger
from discord import utils

from src.data.ranks import ranks
from src.data.pets import pets, pet_stats
from src.data.items.tools import tools
from src.data.items.crops import crops
from src.constants import DATABASE

# Database setup
db_path = os.path.realpath(os.path.join("database", DATABASE))
db = SqliteDatabase(db_path)
# Migrator to edit tables
migrator = SqliteMigrator(db)

log = getLogger(__name__)
log.setLevel(10)


# region Base Model definition

class BaseModel(Model):
    class Meta:
        database = db

    @classmethod
    def list_columns(cls):
        columns = [field for field in cls._meta.fields]
        return columns

# endregion

# region Users class


class Users(BaseModel):
    name = TextField(null=True)
    bank = IntegerField(default=0, null=True)
    money = IntegerField(default=0, null=True)
    tokens = IntegerField(default=0, null=True)
    xp = IntegerField(default=100, null=True)
    in_game = IntegerField(default=0, null=True)
    area = IntegerField(default=401)
    login_streak = IntegerField(default=0)
    drops_claimed = IntegerField(default=0)
    contributions_made = IntegerField(default=0)
    bit_bonus = IntegerField(default=0)

    @classmethod
    def initialize(cls, interaction: discord.Interaction):
        """
        Gets a user object from the User table
        Takes in an interaction argument to handle discord interactions
        Pretty much acts as in init method
        If a user ID is passed, will affect only user with that ID, not command user
        """
        # Attempt to establish a connection to the database
        try:
            db.connect(reuse_if_open=True)
            log.debug("Successfully connected to database.")
        except DatabaseError as error:
            log.error(f"Error connecting to Database.\nError: {error}")

        user, _ = cls.get_or_create(id=interaction.user.id)

        # Update the user's name in the database
        user.name = interaction.user.nick
        log.debug(f"Updated username to {interaction.user.nick}.")
        user.save()

        user.total_balance = user.bank + user.money

        user.pet = Pets.retrieve_pet(interaction.user.id)
        user.rank = Users.retrieve_rank(interaction)

        log.debug(f"User {user} fetched.")
        return user

    @staticmethod
    def retrieve_rank(interaction: discord.Interaction):
        guild_roles = interaction.guild.roles
        for rank in ranks.keys():
            log.debug(f"Checking for {rank}...")
            discord_role = utils.get(guild_roles, name=rank.capitalize())
            # Check to see if the user has any matching role in discord
            if discord_role in interaction.user.roles:
                log.debug(f"Found {rank} rank.")
                return rank
            else:
                return "No rank found"
            
    def increase_balance(self, amount, bank: bool = False):
        if bank:
            self.bank += amount
        else:
            self.money += amount
        self.save()

    def update_tokens(self, amount):
        self.tokens += amount
        self.save()

    def start_game(self):
        self.in_game = True
        log.debug(f"Updating {self.name} status to True.")
        self.save()

    def end_game(self):
        self.in_game = False
        log.debug(f"Updating {self.name} status to False.")
        self.save()

    def check_bet(self, bet):
        balance = self.money
        if int(bet) < 0:
            return f"The oldest trick in the book... Nice try.", False
        elif int(bet) > balance:
            return f"No loans. You have {balance} bits.", False
        elif int(bet) == 0:
            return "What did you think this was going to do?", False
        else:
            return "Passed", True

    def __del__(self):
        db.close()

# endregion

# region Farming skill

class Farming(BaseModel):
    user = ForeignKeyField(Users, backref="farming", on_delete="CASCADE")
    has_open_farm = BooleanField(default=False)
    crops_grown = IntegerField(default=0)
    plots_unlocked = IntegerField(default=3)
    fertilizer_level = IntegerField(default=1)
    tool_id = IntegerField(default=None)
    plot1 = TextField(default=None, null=True)
    plot2 = TextField(default=None, null=True)
    plot3 = TextField(default=None, null=True)
    plot4 = TextField(default=None, null=True)
    plot5 = TextField(default=None, null=True)
    plot6 = TextField(default=None, null=True)
    plot7 = TextField(default=None, null=True)
    plot8 = TextField(default=None, null=True)
    plot9 = TextField(default=None, null=True)
    
    plots = ["plot1", "plot2", "plot3",
             "plot4", "plot5", "plot6",
             "plot7", "plot8", "plot9"]

    def open_farm(self):
        self.has_open_farm = True
        self.save()

    def close_farm(self):
        self.has_open_farm = False
        self.save()
        
    def update_plot(self, plot: int, new_id: int):
        pass

# endregion


class Combat(BaseModel):
    user_id = ForeignKeyField(Users, backref="combat", on_delete="CASCADE")
    xp = IntegerField(default=0)
    weapon_id = IntegerField(default=None, null=True)
    monsters_slain = IntegerField(default=0)
    bosses_slain = IntegerField(default=0)


class Mining(BaseModel):
    user_id = ForeignKeyField(Users, backref="mining", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    lodes_mined = IntegerField(default=0)
    reactor_fragments = IntegerField(default=0)
    core_slot_1 = BooleanField(default=False)
    core_slot_2 = BooleanField(default=False)
    core_slot_3 = BooleanField(default=False)
    core_slot_4 = BooleanField(default=False)
    prestige_level = IntegerField(default=None, null=True)


class Foraging(BaseModel):
    user_id = ForeignKeyField(Users, backref="foraging", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    trees_chopped = IntegerField(default=0)


class Fishing(BaseModel):
    user_id = ForeignKeyField(Users, backref="fishing", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    skiff_level = IntegerField(default=1)
    fish_caught = IntegerField(default=0)
    book_entries = IntegerField(default=0)
    contributions = IntegerField(default=0)

    def give_xp(amount: int):
        pass

    @staticmethod
    def calculate_level(xp):
        # Change up XP scaling here if needed
        level = ((xp / 100) ** (1/math.e)).__floor__()
        return level

    @staticmethod
    def total_xp(xp):
        # Will need fixing if I change XP scaling to be different for each skill!!!
        level = Fishing.calculate_level(xp)
        xp_to_lvl_up = int(((level + 1) ** math.e) * 100)
        return xp_to_lvl_up

# region Users Cooldowns class


class UserCooldowns(BaseModel):
    user = ForeignKeyField(
        Users, backref="cooldowns", primary_key=True, on_delete="CASCADE"
    )
    daily = IntegerField(default=0, null=True, column_name="last_daily")
    work = IntegerField(default=0, null=True, column_name="last_work")
    weekly = IntegerField(default=0, null=True, column_name="last_weekly")

    class Meta:
        table_name = "user_cooldowns"

    COMMAND_TYPES = Literal["daily", "work", "weekly"]

    def set_cooldown(self, command_type: COMMAND_TYPES):
        now = time.time()
        old_value = getattr(self, command_type)
        setattr(self, command_type, now)
        self.save()
        return f"{command_type} updated successfully ({old_value} -> {now})", True

    def check_cooldown(self, command_type: COMMAND_TYPES):
        """
        Checks to see if a command is currently on cooldown
        Returns True if the command is ready and False if it is still on cooldown
        Also returns the a formatted string of the remaining cooldown, if any

        Parameters
        ----------
        user : User
            the user to check the readiness of commands for
        command_type : COMMAND_TYPES
            the type of command to check for
        """
        last_used = getattr(self, command_type)
        cooldown_hours = {"work": 6, "daily": 21, "weekly": 167}

        now = datetime.timestamp(datetime.now)
        seconds_since_last_used = now - last_used
        hours_since_last_used = seconds_since_last_used / 3600

        if hours_since_last_used < cooldown_hours:
            # Cooldown has not yet finished
            off_cooldown = last_used + float(cooldown_hours * 3600)
            seconds_remaining = off_cooldown - now

            def format_time(time):
                if time == 0:
                    time = "00"
                return time

            # Calculate and format the remaining cooldown
            days = int(seconds_remaining // 86400)
            hours = format_time(int((seconds_remaining % 86400) // 3600))
            minutes = format_time(int((seconds_remaining % 3600) // 60))
            seconds = format_time(int(seconds_remaining % 60))

            cooldown = f"{days} days {hours}:{minutes}:{seconds} remaining"
            return False, cooldown  # The check has been failed
        else:
            return True, None  # The check has been passed

# endregion

# region Settings class


class Settings(BaseModel):
    """
    Auto Deposit: automatically deposit your bits from working into the bank\n
    Withdraw Warning: when enabled, a warning appears when you try to withdraw bits\n
    Disable Max Bet: prevents the user from betting everything when enabled\n
    Check-in+: adds work and weekly to the check-in command\n
    More settings to be added soon...
    """

    user = ForeignKeyField(
        Users, backref="settings", unique=True, on_delete="CASCADE", column_name="user"
    )
    auto_deposit = BooleanField(default=False)
    withdraw_warning = BooleanField(default=False)
    disable_max_bet = BooleanField(default=False)
    upgraded_check_in = BooleanField(default=False)

    ATTRIBUTES = Literal[
        "auto_deposit", "withdraw_warning", "disable_max_bet", "upgraded_check_in"
    ]

    def update_value(self, attribute: ATTRIBUTES, value):
        try:
            options = get_args(self.ATTRIBUTES)
            assert attribute in options, f"'{attribute}' is not in {options}"
        except AssertionError as e:
            return str(e), False

        old_value = getattr(self, attribute)
        setattr(self, attribute, value)
        self.save()
        return f"{attribute} updated successfully ({old_value} -> {value})", True

# endregion

# region Items class
class Items(BaseModel):
    user = ForeignKeyField(
        Users, backref="items", on_delete="CASCADE", column_name="user"
    )
    reference_id = TextField()
    quantity = IntegerField(default=1)

    @classmethod
    def get_info(cls, item_id):
        descriptors = tools[item_id]["description"]
        components = tools[item_id]["components"]
        return descriptors, components

    @classmethod
    def get_item(cls, owner: int, item_id: str):
        return Items.get(cls.user == owner, cls.reference_id == item_id)

    @classmethod
    def insert_item(cls, owner: int, item_id: str, quantity: int = 1):
        item, created = cls.get_or_create(
            user=owner, reference_id=item_id, defaults={"quantity": quantity}
        )
        if created:
            return True, f"New item created with quantity: {quantity}."
        else:
            item.quantity += quantity
            item.save()
            return True, f"Item quantity increased by {quantity}"

    @classmethod
    def delete_item(cls, owner: int, item_id: str, quantity: int = None):
        try:
            # Try to decrement quantity of existing item
            item = cls.get(user=owner, reference_id=item_id)
            if quantity:
                item.quantity -= quantity
                if item.quantity <= 0:
                    # If quantity becomes 0 or negative, delete item
                    item.delete_instance()
                    return True, "Item quantity 0 or below, item deleted."
                else:
                    item.save()
                    return True, f"Item quantity reduced by {quantity}"
            else:
                item.delete_instance()
                return True, "Item deleted."

        except cls.DoesNotExist:
            # If item doesn't exist, do nothing
            return False, "This item does not exist."

    @classmethod
    def trade_item(cls, owner: int, new_owner: int, item_id: str, quantity: int = None):
        try:
            # Transfer the ownership of the item if it exists
            item: Items = cls.get(user=owner, reference_id=item_id)
            if quantity:
                if quantity > item.quantity:
                    return False, "User does not own enough of this item."
                # Inserts same item into tradee's inventory
                Items.insert_item(new_owner, item_id, quantity)
                # Removes items from trader's inventory
                Items.delete_item(owner, item_id, quantity)
                return True, f"{quantity} items transferred."
            else:
                # If the entire quantity of the item is being traded, just transfer ownership
                item.user = new_owner
                item.save()
                return True, "Entire item transferred."

            item.save()
        except cls.DoesNotExist:
            # If item doesn't exist, do nothing
            return False, "This item does not exist."

# endregion

# region Pets class


class Pets(BaseModel):
    user = ForeignKeyField(Users, backref="pets", on_delete="CASCADE")
    reference_id = IntegerField()
    active = BooleanField()
    level = IntegerField(default=1)
    xp = IntegerField(default=0)
    name = TextField(null=True)

    @classmethod
    def get_info(cls, pet_id):
        descriptors = pets[pet_id]["description"]
        components = pets[pet_id]["components"]
        return descriptors, components

    @classmethod
    def retrieve_pet(cls, user_id: int):
        try:
            # Look for an active pet with the passed user_id
            query = ((cls.user == user_id) & Pets.active)
            active_pet = Pets.select().where(query)
        except DoesNotExist:
            active_pet = None
            log.debug("Found no active pet, setting pet to None.")
        return active_pet

    def change_name(self, new_name):
        if len(new_name) > 14:
            return "Please refrain from using more than 14 characters."
        self.name = new_name
        self.save()
        return f"Name successfully changed to {new_name}."

    # def set_activity(self, pet_id):
    #     self.active = False


# endregion

# region Megadrop class
class MegaDrop(BaseModel):
    amount = IntegerField(default=0)
    total_drops_missed = IntegerField(default=0)
    total_drops = IntegerField(default=0)
    times_missed = IntegerField(default=0)
    counter = IntegerField(default=0)
    last_winner = TextField()

    fmt = "%m-%d-%Y"  # Put current date into a format
    now_time = datetime.now(timezone("US/Eastern"))
    date_started = TextField(default=now_time.strftime(fmt))

    @classmethod
    def new(cls, bot):
        guild = bot.get_guild(856915776345866240)  # Guild to send the drops in

# endregion


def create_tables():
    tables = [Users, UserCooldowns, Pets, Items, MegaDrop, Mining, Combat, Fishing, Foraging, Farming]
    with db:
        db.create_tables(tables)


create_tables()
