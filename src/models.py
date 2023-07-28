import discord
import os

from datetime import time, datetime
from pytz import timezone
from typing import Literal
from enum import Enum
from peewee import *
from logging import getLogger

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

    def get_field(self, field_name):
        return getattr(self, field_name)

    def set_field(self, field_name, value):
        setattr(self, field_name, value)

    @classmethod
    def list_columns(cls):
        columns = [field for field in cls._meta.fields]
        return columns


class SkillModel(BaseModel):
    # Lower scaling_x = more XP required per level
    # Higher scaling_y = larger gaps between levels
    scaling_x: int
    scaling_y: int

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
    bank = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    purse = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    tokens = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    in_game = BooleanField(default=False)
    party_id = IntegerField(null=True)
    party_channel_id = IntegerField(null=True)
    area_id = IntegerField(constraints=[SQL("DEFAULT 1")])
    login_streak = IntegerField(constraints=[SQL("DEFAULT 0")])
    drops_claimed = IntegerField(constraints=[SQL("DEFAULT 0")])

    # Custom
    leaderboard_columns = [purse + bank, login_streak, drops_claimed]
    emoji = ":money_with_wings:"
    color = discord.Color.blue()
# endregion

# region Backrefs class
class Farming(SkillModel):
    # Columns
    user_id = ForeignKeyField(Users, primary_key=True,
                              backref="farming", on_delete="CASCADE")
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = IntegerField(default=None, null=True)
    is_farming = BooleanField(default=False)
    crops_grown = IntegerField(constraints=[SQL("DEFAULT 0")])
    plots_unlocked = IntegerField(default=3)
    fertilizer_level = IntegerField(constraints=[SQL("DEFAULT 1")])
    plot1 = TextField(default=None, null=True)
    plot2 = TextField(default=None, null=True)
    plot3 = TextField(default=None, null=True)
    plot4 = TextField(default=None, null=True)
    plot5 = TextField(default=None, null=True)
    plot6 = TextField(default=None, null=True)
    plot7 = TextField(default=None, null=True)
    plot8 = TextField(default=None, null=True)
    plot9 = TextField(default=None, null=True)

    class Meta:
        table_name = 'skill_farming'

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
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = IntegerField(default=None, null=True)
    monsters_slain = IntegerField(constraints=[SQL("DEFAULT 0")])
    bosses_slain = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = 'skill_combat'

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
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = IntegerField(default=None, null=True)
    lodes_mined = IntegerField(constraints=[SQL("DEFAULT 0")])
    core_slot_1 = BooleanField(default=False)
    core_slot_2 = BooleanField(default=False)
    core_slot_3 = BooleanField(default=False)
    core_slot_4 = BooleanField(default=False)
    prestige_level = IntegerField(default=None, null=True)
    bonuses_remaining = IntegerField(constraints=[SQL("DEFAULT 0")])
    bonus_type = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = 'skill_mining'

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
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = IntegerField(default=None, null=True)
    trees_chopped = IntegerField(constraints=[SQL("DEFAULT 0")])
    double_trees_chopped = IntegerField(constraints=[SQL("DEFAULT 0")])
    releaf_donations = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = 'skill_foraging'

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
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = IntegerField(default=None, null=True)
    skiff_level = IntegerField(constraints=[SQL("DEFAULT 1")])
    fish_caught = IntegerField(constraints=[SQL("DEFAULT 0")])
    book_entries = IntegerField(constraints=[SQL("DEFAULT 0")])
    treasures_found = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = 'skill_fishing'

    # Custom
    leaderboard_name = "FISHING LEADERBOARD"
    leaderboard_column = [xp, fish_caught, book_entries, treasures_found]
    emoji = ":fishing_pole_and_fish:"
    color = discord.Color.dark_blue()
    scaling_x = 0.06
    scaling_y = 2


class UserCooldowns(BaseModel):
    last_daily = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    last_weekly = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    last_work = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    user = ForeignKeyField(column_name='user_id', model=Users,
                           backref="cooldowns",  primary_key=True)

    class Meta:
        table_name = 'user_cooldowns'

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


class Settings(BaseModel):
    """
    Auto Deposit: automatically deposit your bits from working into the bank\n
    Withdraw Warning: when enabled, a warning appears when you try to withdraw bits\n
    Disable Max Bet: prevents the user from betting everything when enabled\n
    Check-in+: adds work and weekly to the check-in command\n
    More settings to be added soon...
    """

    user = ForeignKeyField(column_name='user_id', model=Users,
                           backref='settings', primary_key=True)
    auto_deposit = BooleanField(default=False)
    withdraw_warning = BooleanField(default=False)
    disable_max_bet = BooleanField(default=False)
    upgraded_check_in = BooleanField(default=False)

    ATTRIBUTES = Literal["auto_deposit", "withdraw_warning",
                         "disable_max_bet", "upgraded_check_in"]
    
class Backrefs(Enum):
    combat: Combat
    mining: Mining
    foraging: Foraging
    fishing: Fishing
    farming: Farming
    settings: Settings
    cooldowns: UserCooldowns
    
BACKREFS = Literal["combat", "mining", 
                   "foraging", "fishing", 
                   "farming", "settings", 
                   "cooldowns"]

# endregion

# region Pets class
class Pets(BaseModel):
    owner_id = ForeignKeyField(Users, backref="pets", on_delete="CASCADE")
    pet_id = IntegerField()
    active = BooleanField(default=False)
    level = IntegerField(constraints=[SQL("DEFAULT 1")])
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    name = TextField(null=True)


# endregion

# region Item data classes
class DataMaster(BaseModel):
    item_id = TextField(primary_key=True)
    price = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    consumable = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    description = TextField(null=True)
    display_name = TextField(null=True)
    drop_rate = IntegerField(null=True)
    is_material = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    max_drop = IntegerField(null=True)
    min_drop = IntegerField(null=True)
    rarity = IntegerField(null=True)
    sell_price = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    skill = TextField(null=True)
    type = TextField(null=True)

    class Meta:
        table_name = 'data_master'


class DataSeeds(BaseModel):
    item_id = ForeignKeyField(column_name='item_id', model=DataMaster,
                              backref='seed_data', null=True, primary_key=True)
    grows_into = TextField(null=True)
    growth_odds = IntegerField(null=True)

    class Meta:
        table_name = 'data_seeds'


class DataCrops(BaseModel):
    item_id = ForeignKeyField(column_name='item_id', model=DataMaster,
                              backref='crop_data', null=True, primary_key=True)
    grows_from = TextField(null=True)
    max_harvest = IntegerField(null=True)
    min_harvest = IntegerField(null=True)
    pet_xp = IntegerField(null=True)

    class Meta:
        table_name = 'data_crops'


class DataTools(BaseModel):
    item_id = ForeignKeyField(column_name='item_id', model=DataMaster,
                              backref='tool_data', null=True, primary_key=True)
    power = IntegerField(constraints=[SQL("DEFAULT 1")], null=True)

    class Meta:
        table_name = 'data_tools'


class DataPets(BaseModel):
    pet_id = TextField(null=True, primary_key=True)
    daily_bonus = IntegerField(null=True)
    display_name = TextField(null=True)
    max_level = IntegerField(null=True)
    price = IntegerField(null=True)
    rarity = IntegerField(null=True)
    work_bonus = IntegerField(null=True)

    class Meta:
        table_name = 'data_pets'


class DataRanks(BaseModel):
    rank_id = IntegerField(null=True, primary_key=True)
    color = TextField(null=True)
    description = TextField(null=True)
    display_name = TextField(null=True)
    emoji = TextField(null=True)
    next_rank_id = IntegerField(null=True)
    token_price = IntegerField(null=True)
    wage = IntegerField(null=True)

    class Meta:
        table_name = 'data_ranks'


class DataAreas(BaseModel):
    area_id = TextField(null=True, primary_key=True)
    description = TextField(null=True)
    difficulty = IntegerField(null=True)
    display_name = TextField(null=True)
    fuel_amount = IntegerField(null=True)
    fuel_requirement = TextField(null=True)
    token_bonus = IntegerField(null=True)

    class Meta:
        table_name = 'data_areas'
        

class DataTables(Enum):
    areas = DataAreas
    crops = DataCrops
    pets = DataPets
    ranks = DataRanks
    seeds = DataSeeds
    tools = DataTools
    master = DataMaster
    
DATATABLES = Literal["areas", "crops",
                     "pets", "ranks",
                     "seeds", "tools",
                     "master"]
# endregion

# region Megadrop class
class MegaDrop(BaseModel):
    # Columns
    amount = IntegerField(constraints=[SQL("DEFAULT 0")])
    total_drops_missed = IntegerField(constraints=[SQL("DEFAULT 0")])
    total_drops = IntegerField(constraints=[SQL("DEFAULT 0")])
    times_missed = IntegerField(constraints=[SQL("DEFAULT 0")])
    counter = IntegerField(constraints=[SQL("DEFAULT 0")])
    last_winner = TextField()
    fmt = "%m-%d-%Y"  # Put current date into a format
    now_time = datetime.now(timezone("US/Eastern"))
    date_started = TextField(default=now_time.strftime(fmt))

    @classmethod
    def new(cls, bot):
        guild = bot.get_guild(856915776345866240)  # Guild to send the drops in
# endregion

# region Items class
class Items(BaseModel):
    owner = ForeignKeyField(column_name='owner_id',
                            model=Users, backref='items')
    item_id = ForeignKeyField(column_name='item_id',
                              model=DataMaster, backref='data')
    enchantment = TextField(null=True)
    quantity = IntegerField()
    star_level = IntegerField(null=True)

    class Meta:
        table_name = 'items'

# endregion


def create_tables():
    tables = [Users, UserCooldowns, Pets, Items, MegaDrop,
              Mining, Combat, Fishing, Foraging, Farming]
    with db:
        db.create_tables(tables)


create_tables()
