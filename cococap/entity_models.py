import discord
import os

from datetime import time, datetime
from pytz import timezone
from typing import Literal
from enum import Enum
from peewee import *

from cococap.constants import URI, DATABASE
from cococap.item_models import DataAreas, DataTools, DataMaster

# Database setup
db_path = os.path.realpath(os.path.join("database", DATABASE))
db = SqliteDatabase(db_path)


class BaseModel(Model):
    # used
    leaderboard_columns: dict

    class Meta:
        database = db

    @classmethod
    def list_columns(cls):
        columns = [field for field in cls._meta.fields]
        return columns


class SkillModel(BaseModel):
    scaling_x: int  # lower value = more xp per level
    scaling_y: int  # higher value = more xp between levels

    @classmethod
    def xp_required_for_next_level(cls, xp):
        current_level = cls.level_from_xp(xp)
        next_level = current_level + 1
        xp_required = cls.xp_required_for_level(next_level)
        return xp_required

    @classmethod
    def level_from_xp(cls, xp):
        level = cls.scaling_x * (xp ** (1 / cls.scaling_y))
        return level

    @classmethod
    def xp_required_for_level(cls, level):
        xp = (level / cls.scaling_x) ** cls.scaling_y
        return xp


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
    area_id = ForeignKeyField(DataAreas, backref="area")
    login_streak = IntegerField(constraints=[SQL("DEFAULT 0")])
    drops_claimed = IntegerField(constraints=[SQL("DEFAULT 0")])

    # Custom
    leaderboard_columns = [purse + bank, login_streak, drops_claimed]


class Farming(SkillModel):
    # Columns
    user_id = ForeignKeyField(
        Users, primary_key=True, backref="farming", on_delete="CASCADE"
    )
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = ForeignKeyField(DataTools, default=None, null=True)
    is_farming = BooleanField(default=False)
    crops_grown = IntegerField(default=0)
    raingod_blessings = IntegerField(default=0)
    anomalies = IntegerField(default=0)
    land_deeds = IntegerField(default=0)
    plots_unlocked = IntegerField(default=1)
    plot1 = TextField(default=None, null=True)
    plot2 = TextField(default="Locked", null=True)
    plot3 = TextField(default="Locked", null=True)
    plot4 = TextField(default="Locked", null=True)
    plot5 = TextField(default="Locked", null=True)
    plot6 = TextField(default="Locked", null=True)
    plot7 = TextField(default="Locked", null=True)
    plot8 = TextField(default="Locked", null=True)
    plot9 = TextField(default="Locked", null=True)

    class Meta:
        table_name = "user_skill_farming"

    # Custom
    leaderboard_columns = [xp, crops_grown]
    scaling_x = 0.07
    scaling_y = 2

    plots = [
        "plot1",
        "plot2",
        "plot3",
        "plot4",
        "plot5",
        "plot6",
        "plot7",
        "plot8",
        "plot9",
    ]


class Combat(SkillModel):
    # Columns
    user_id = ForeignKeyField(
        Users, primary_key=True, backref="combat", on_delete="CASCADE"
    )
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = ForeignKeyField(DataTools, default=None, null=True)
    monsters_slain = IntegerField(constraints=[SQL("DEFAULT 0")])
    bosses_slain = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = "user_skill_combat"

    # Custom
    leaderboard_column = [xp, monsters_slain, bosses_slain]
    emoji = ":crossed_swords:"
    color = discord.Color.dark_red()
    scaling_x = 0.06
    scaling_y = 2


class Mining(SkillModel):
    # Columns
    user_id = ForeignKeyField(
        Users, primary_key=True, backref="mining", on_delete="CASCADE"
    )
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = ForeignKeyField(DataTools, default=None, null=True)
    lodes_mined = IntegerField(constraints=[SQL("DEFAULT 0")])
    core_slot_1 = BooleanField(default=False)
    core_slot_2 = BooleanField(default=False)
    core_slot_3 = BooleanField(default=False)
    core_slot_4 = BooleanField(default=False)
    prestige_level = IntegerField(default=None, null=True)
    bonuses_remaining = IntegerField(constraints=[SQL("DEFAULT 0")])
    bonus_type = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = "user_skill_mining"

    # Custom
    leaderboard_column = [xp, lodes_mined]
    emoji = ":pick:"
    color = discord.Color.dark_orange()
    scaling_x = 0.05
    scaling_y = 2


class Foraging(SkillModel):
    # Columns
    user_id = ForeignKeyField(
        Users, primary_key=True, backref="foraging", on_delete="CASCADE"
    )
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = ForeignKeyField(DataTools, default=None, null=True)
    trees_chopped = IntegerField(constraints=[SQL("DEFAULT 0")])
    double_trees_chopped = IntegerField(constraints=[SQL("DEFAULT 0")])
    releaf_donations = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = "user_skill_foraging"

    # Custom
    leaderboard_column = [xp, trees_chopped, double_trees_chopped, releaf_donations]
    emoji = ":evergreen_tree:"
    color = discord.Color.dark_green()
    scaling_x = 0.07
    scaling_y = 2


class Fishing(SkillModel):
    # Columns
    user_id = ForeignKeyField(
        Users, primary_key=True, backref="fishing", on_delete="CASCADE"
    )
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    tool_id = ForeignKeyField(DataTools, default=None, null=True)
    skiff_level = IntegerField(constraints=[SQL("DEFAULT 1")])
    fish_caught = IntegerField(constraints=[SQL("DEFAULT 0")])
    book_entries = IntegerField(constraints=[SQL("DEFAULT 0")])
    treasures_found = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = "user_skill_fishing"

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
    user = ForeignKeyField(
        column_name="user_id", model=Users, backref="cooldowns", primary_key=True
    )

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


class UserSettings(BaseModel):
    """
    Auto Deposit: automatically deposit your bits from working into the bank\n
    Withdraw Warning: when enabled, a warning appears when you try to withdraw bits\n
    Disable Max Bet: prevents the user from betting everything when enabled\n
    Check-in+: adds work and weekly to the check-in command\n
    More settings to be added soon...
    """

    user = ForeignKeyField(
        column_name="user_id", model=Users, backref="settings", primary_key=True
    )
    auto_deposit = BooleanField(default=False)
    withdraw_warning = BooleanField(default=False)
    disable_max_bet = BooleanField(default=False)
    upgraded_check_in = BooleanField(default=False)

    class Meta:
        table_name = "user_settings"

    ATTRIBUTES = Literal[
        "auto_deposit", "withdraw_warning", "disable_max_bet", "upgraded_check_in"
    ]


class UsersChildTables(Enum):
    combat: Combat = Combat
    mining: Mining = Mining
    foraging: Foraging = Foraging
    fishing: Fishing = Fishing
    farming: Farming = Farming
    settings: UserSettings = UserSettings
    cooldowns: UserCooldowns = UserCooldowns


class Pets(BaseModel):
    owner_id = ForeignKeyField(Users, backref="pets", on_delete="CASCADE")
    pet_id = IntegerField()
    active = BooleanField(default=False)
    level = IntegerField(constraints=[SQL("DEFAULT 1")])
    xp = IntegerField(constraints=[SQL("DEFAULT 0")])
    name = TextField(null=True)

    class Meta:
        table_name = "user_pets"


class MegaDrop(BaseModel):
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
        # TODO: Not sure...
        pass



