import os

from cococap.constants import DATABASE

from enum import Enum
from peewee import (
    SqliteDatabase,
    Model,
    IntegerField,
    TextField,
    ForeignKeyField,
    DoesNotExist,
    SQL,
)
from logging import getLogger


# Database setup
db_path = os.path.realpath(os.path.join("database", DATABASE))
db = SqliteDatabase(db_path)

log = getLogger(__name__)
log.setLevel(10)


class BaseModel(Model):
    class Meta:
        database = db

    @classmethod
    def get_display_name(cls, entity_id):
        """Retrieve the display name or name of the entity."""
        try:
            entity = cls.get_by_id(entity_id)
            display_name = getattr(entity, "display_name", None)
            return display_name
        except DoesNotExist:
            print(f"No entity found with ID {entity_id}")
            return None


# region Item data classes
class Master(BaseModel):
    item_id = TextField(primary_key=True)
    price = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    description = TextField(null=True)
    wiki = TextField(null=True)
    display_name = TextField(null=True)
    drop_rate = IntegerField(null=True)
    max_drop = IntegerField(null=True)
    min_drop = IntegerField(null=True)
    rarity = IntegerField(null=True)
    sell_price = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    skill = TextField(null=True)
    filter_type = TextField(null=True)
    emoji = TextField(null=True)

    class Meta:
        table_name = "data_master"

class Crops(BaseModel):
    item_id = ForeignKeyField(
        column_name="item_id",
        model=Master,
        backref="crop_data",
        null=True,
        primary_key=True,
    )
    grows_from = TextField(null=True)
    pet_xp = IntegerField(null=True)
    cycles = IntegerField(null=True)

    class Meta:
        table_name = "data_crops"


class Tools(BaseModel):
    item_id = ForeignKeyField(
        column_name="item_id",
        model=Master,
        backref="tool_data",
        null=True,
        primary_key=True,
    )
    power = IntegerField(constraints=[SQL("DEFAULT 1")], null=True)

    class Meta:
        table_name = "data_tools"


class Pets(BaseModel):
    item_id = ForeignKeyField(
        column_name="item_id",
        model=Master,
        backref="pet_data",
        null=True,
        primary_key=True,
    )
    display_name = TextField(null=True)
    description = TextField(null=True)
    rarity = IntegerField(null=True)
    price = IntegerField(null=True)
    daily_bonus = IntegerField(null=True)
    max_level = IntegerField(null=True)
    work_bonus = IntegerField(null=True)
    emoji = TextField(null=True)

    class Meta:
        table_name = "data_pets"


class Ranks(BaseModel):
    rank_id = IntegerField(null=True, primary_key=True)
    color = TextField(null=True)
    description = TextField(null=True)
    display_name = TextField(null=True)
    emoji = TextField(null=True)
    token_price = IntegerField(null=True)
    wage = IntegerField(null=True)

    class Meta:
        table_name = "data_ranks"


class ItemType(Enum):
    CROP = Crops
    PET = Pets
    RANK = Ranks
    TOOL = Tools
    master = Master


# endregion
