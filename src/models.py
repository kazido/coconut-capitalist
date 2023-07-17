import discord
import os

from datetime import time, datetime
from pytz import timezone
from typing import Literal
from peewee import *
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

log = getLogger(__name__)
log.setLevel(10)

# region Base Model definitions


class BaseModel(Model):
    leaderboard_columns: dict
    color: discord.Color
    emoji: str

    class Meta:
        database = db

    @classmethod
    def list_columns(cls):
        columns = [field for field in cls._meta.fields]
        return columns


class SkillModel(BaseModel):
    # Lower scaling_x = more XP required per level
    # Higher scaling_y = larger gaps between levels
    scaling_x: int
    scaling_y: int

    def set_xp(self, amount: int):
        self.xp = amount

    def get_xp(self):
        return self.xp

    def xp_required_for_next_level(self):
        current_level = self.level_from_xp(self.xp)
        next_level = current_level + 1
        xp_required = self.xp_required_for_level(next_level)
        return xp_required

    @classmethod
    def level_from_xp(cls, xp):
        level = cls.scaling_x * (xp**(1/cls.scaling_y))
        return level

    @classmethod
    def xp_required_for_level(cls, level):
        xp = (level/cls.scaling_x)**cls.scaling_y
        return xp


# endregion

# region Users class


class Users(BaseModel):
    # Columns
    user_id = IntegerField(primary_key=True)
    name = TextField(null=True)
    bank = IntegerField(default=0, null=True)
    purse = IntegerField(default=0, null=True)
    tokens = IntegerField(default=0, null=True)
    in_game = BooleanField(default=False)
    party_id = IntegerField(null=True)
    area_id = IntegerField(default=1)
    login_streak = IntegerField(default=0)
    drops_claimed = IntegerField(default=0)

    # Custom
    leaderboard_columns = [purse + bank, login_streak, drops_claimed]
    emoji = ":money_with_wings:"
    color = discord.Color.blue()
# endregion


class Farming(SkillModel):
    # Columns
    user_id = ForeignKeyField(Users, primary_key=True,
                              backref="farming", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    is_farming = BooleanField(default=False)
    crops_grown = IntegerField(default=0)
    plots_unlocked = IntegerField(default=3)
    fertilizer_level = IntegerField(default=1)
    plot1 = TextField(default=None, null=True)
    plot2 = TextField(default=None, null=True)
    plot3 = TextField(default=None, null=True)
    plot4 = TextField(default=None, null=True)
    plot5 = TextField(default=None, null=True)
    plot6 = TextField(default=None, null=True)
    plot7 = TextField(default=None, null=True)
    plot8 = TextField(default=None, null=True)
    plot9 = TextField(default=None, null=True)

    # Custom
    leaderboard_columns = [xp, crops_grown]
    emoji = ":corn:"
    color = discord.Color.green()
    scaling_x = 0.07
    scaling_y = 2

    plots = ["plot1", "plot2", "plot3",
             "plot4", "plot5", "plot6",
             "plot7", "plot8", "plot9"]

    def open_farm(self):
        self.is_farming = True
        self.save()

    def close_farm(self):
        self.is_farming = False
        self.save()

    def update_plot(self, plot: int, new_id: int):
        pass


class Combat(SkillModel):
    # Columns
    user_id = ForeignKeyField(Users, primary_key=True,
                              backref="combat", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    monsters_slain = IntegerField(default=0)
    bosses_slain = IntegerField(default=0)

    # Custom
    leaderboard_column = [xp, monsters_slain, bosses_slain]
    emoji = ":crossed_swords:"
    color = discord.Color.dark_red()
    scaling_x = 0.06
    scaling_y = 2


class Mining(SkillModel):
    # Columns
    user_id = ForeignKeyField(Users, primary_key=True,
                              backref="mining", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    lodes_mined = IntegerField(default=0)
    core_slot_1 = BooleanField(default=False)
    core_slot_2 = BooleanField(default=False)
    core_slot_3 = BooleanField(default=False)
    core_slot_4 = BooleanField(default=False)
    prestige_level = IntegerField(default=None, null=True)
    bonuses_remaining = IntegerField(default=0)
    bonus_type = IntegerField(default=0)

    # Custom
    leaderboard_column = [xp, lodes_mined]
    emoji = ":pick:"
    color = discord.Color.dark_orange()
    scaling_x = 0.05
    scaling_y = 2


class Foraging(SkillModel):
    # Columns
    user_id = ForeignKeyField(Users, primary_key=True,
                              backref="foraging", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    trees_chopped = IntegerField(default=0)
    double_trees_chopped = IntegerField(default=0)
    releaf_donations = IntegerField(default=0)

    # Custom
    leaderboard_column = [xp, trees_chopped,
                          double_trees_chopped, releaf_donations]
    emoji = ":evergreen_tree:"
    color = discord.Color.dark_green()
    scaling_x = 0.07
    scaling_y = 2


class Fishing(SkillModel):
    # Columns
    user_id = ForeignKeyField(Users, primary_key=True,
                              backref="fishing", on_delete="CASCADE")
    xp = IntegerField(default=0)
    tool_id = IntegerField(default=None, null=True)
    skiff_level = IntegerField(default=1)
    fish_caught = IntegerField(default=0)
    book_entries = IntegerField(default=0)
    treasures_found = IntegerField(default=0)

    # Custom
    leaderboard_name = "FISHING LEADERBOARD"
    leaderboard_column = [xp, fish_caught, book_entries, treasures_found]
    emoji = ":fishing_pole_and_fish:"
    color = discord.Color.dark_blue()
    scaling_x = 0.06
    scaling_y = 2

# region Users Cooldowns class


class UserCooldowns(BaseModel):
    user_id = ForeignKeyField(
        Users, backref="cooldowns", primary_key=True, on_delete="CASCADE")
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

    user_id = ForeignKeyField(
        Users, backref="settings", primary_key=True, on_delete="CASCADE")
    auto_deposit = BooleanField(default=False)
    withdraw_warning = BooleanField(default=False)
    disable_max_bet = BooleanField(default=False)
    upgraded_check_in = BooleanField(default=False)

    ATTRIBUTES = Literal["auto_deposit", "withdraw_warning",
                         "disable_max_bet", "upgraded_check_in"]

# endregion

# region Items class


class Items(BaseModel):
    owner_id = ForeignKeyField(Users, backref="items", on_delete="CASCADE")
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
    # Columns
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
    tables = [Users, UserCooldowns, Pets, Items, MegaDrop,
              Mining, Combat, Fishing, Foraging, Farming]
    with db:
        db.create_tables(tables)


create_tables()
