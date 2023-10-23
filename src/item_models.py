import discord
import os

from enum import Enum
from peewee import *
from logging import getLogger

from src.constants import DATABASE

# Database setup
db_path = os.path.realpath(os.path.join("database", DATABASE))
db = SqliteDatabase(db_path)

log = getLogger(__name__)
log.setLevel(10)


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

    @classmethod
    def get_display_name(cls, entity_id):
        """Retrieve the display name or name of the entity."""
        try:
            entity = cls.get_by_id(entity_id)
            display_name = getattr(entity, "display_name", None)
            name = getattr(entity, "name", None)
            return display_name or name
        except DoesNotExist:
            print(f"No entity found with ID {entity_id}")
            return None


# region Item data classes
class DataMaster(BaseModel):
    item_id = TextField(primary_key=True)
    price = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    consumable = BooleanField(constraints=[SQL("DEFAULT 0")], null=True)
    description = TextField(null=True)
    display_name = TextField(null=True)
    drop_rate = IntegerField(null=True)
    is_material = BooleanField(constraints=[SQL("DEFAULT 0")], null=True)
    max_drop = IntegerField(null=True)
    min_drop = IntegerField(null=True)
    rarity = IntegerField(null=True)
    sell_price = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    skill = TextField(null=True)
    item_type = TextField(null=True)

    class Meta:
        table_name = "data_master"


class DataSeeds(BaseModel):
    item_id = ForeignKeyField(
        column_name="item_id",
        model=DataMaster,
        backref="seed_data",
        null=True,
        primary_key=True,
    )
    grows_into = TextField(null=True)
    growth_odds = IntegerField(null=True)

    class Meta:
        table_name = "data_seeds"


class DataCrops(BaseModel):
    item_id = ForeignKeyField(
        column_name="item_id",
        model=DataMaster,
        backref="crop_data",
        null=True,
        primary_key=True,
    )
    grows_from = TextField(null=True)
    max_harvest = IntegerField(null=True)
    min_harvest = IntegerField(null=True)
    pet_xp = IntegerField(null=True)

    class Meta:
        table_name = "data_crops"


class DataTools(BaseModel):
    item_id = ForeignKeyField(
        column_name="item_id",
        model=DataMaster,
        backref="tool_data",
        null=True,
        primary_key=True,
    )
    power = IntegerField(constraints=[SQL("DEFAULT 1")], null=True)

    class Meta:
        table_name = "data_tools"


class DataPets(BaseModel):
    item_id = ForeignKeyField(
        column_name="item_id",
        model=DataMaster,
        backref="pet_data",
        null=True,
        primary_key=True,
    )
    daily_bonus = IntegerField(null=True)
    max_level = IntegerField(null=True)
    work_bonus = IntegerField(null=True)

    class Meta:
        table_name = "data_pets"


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
        table_name = "data_ranks"


class DataAreas(BaseModel):
    area_id = TextField(null=True, primary_key=True)
    description = TextField(null=True)
    difficulty = IntegerField(null=True)
    display_name = TextField(null=True)
    fuel_amount = IntegerField(null=True)
    fuel_requirement = TextField(null=True)
    token_bonus = IntegerField(null=True)

    class Meta:
        table_name = "data_areas"


field_formats = {
    # General fields section
    "item_id": {"text": "**Item ID**: *{:}*"},
    "item_type": {"text": "**Type**: *{:}*"},
    "rarity": {"text": "**Rarity**: *{:}*", "shop_field": True, "rarity": True},
    "consumable": {"text": "**Single Use**: *{:}*"},
    "is_material": {"text": "**Material**: *{:}*"},
    "skill": {"text": "**Category**: *{:}*"},
    "drop_rate": {"text": "**Drop Rate**: 1/*{:,}*"},
    "min_drop": {"text": "**Min Roll**: *{:,}*"},
    "max_drop": {"text": "**Max Roll**: *{:,}*"},
    # Crop specific section
    "pet_xp": {"text": "**Pet XP**: *{:,}*", "shop_field": True},
    "min_harvest": {"text": "**Min Harvest**: *{:,}*"},
    "max_harvest": {"text": "**Max Harvest**: *{:,}*"},
    "grows_from": {
        "text": "**Grows From**: *{:}*",
        "shop_field": True,
        "get_display_name": True,
    },
    # Seed specific section
    "growth_odds": {"text": "**Growth Time**: ~*{:,}* cycles", "shop_field": True},
    "grows_into": {
        "text": "**Grows Into**: *{:}*",
        "shop_field": True,
        "get_display_name": True,
    },
    # Tool specific section
    "power": {"text": "**Power**: *{:,}*", "shop_field": True},
    # Pet specific section
    "max_level": {"text": "**Max Level**: *{:,}*", "shop_field": True},
    "work_bonus": {"text": "**Work Bonus**: *{:,}* bits", "shop_field": True},
    "daily_bonus": {"text": "**Daily Bonus**: *{:,}* tokens", "shop_field": True},
    # Rank specific section
    "emoji": {"text": "**Emoji**: *{:}*"},
    "token_price": {"text": "**Price**: *{:,}* tokens", "shop_field": True},
    "wage": {"text": "**Wage**: *{:,}* bits", "shop_field": True},
    "next_rank_id": {"text": "**Next Rank**: *{:}*", "shop_field": True},
    # Area specific section
    "difficulty": {"text": "**Difficulty**: *{:,}* :star:"},
    "token_bonus": {"text": "**Daily Bonus**: *{:,}* tokens"},
    "fuel_requriement": {"text": "**Fuel Type**: *{:}*"},
    "fuel_amount": {"text": "**Req. Fuel**: *{:,}*"},
    # Bottom formatting
    "price": {"text": "**Price**: *{:,}*", "shop_field": True},
    "sell_price": {"text": "**Sell Price**: *{:,}*"},
}


class ItemType(Enum):
    AREA = DataAreas
    CROP = DataCrops
    PET = DataPets
    RANK = DataRanks
    SEED = DataSeeds
    TOOL = DataTools
    master = DataMaster


# endregion
