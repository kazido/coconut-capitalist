from peewee import *
import json
import os

current = os.path.dirname(os.path.realpath(__file__))
ROOT_DIRECTORY = os.path.dirname(current)
with open(f'{ROOT_DIRECTORY}\config.json', 'r') as file:
    data = json.load(file)

database = SqliteDatabase(database=data['sqlite_path'])


class UnknownField(object):
    def __init__(self, *_, **__): pass


class BaseModel(Model):
    class Meta:
        database = database


class Users(BaseModel):
    avatar = TextField(constraints=[SQL("DEFAULT 'None'")], null=True)
    bank = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    in_game = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    money = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    tokens = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    name = TextField(null=True)
    xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    combat_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    mining_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    foraging_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    fishing_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    area = IntegerField(constraints=[SQL("DEFAULT 0")])
    weapon = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    pickaxe = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    axe = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    fishing_rod = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    drops_claimed = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = 'users'


class Farms(BaseModel):
    id = ForeignKeyField(column_name='id', model=Users, primary_key=True)
    almonds_seeds = IntegerField(constraints=[SQL("DEFAULT 25")], null=True)
    almonds = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    chocolates_seeds = IntegerField(constraints=[SQL("DEFAULT 3")], null=True)
    chocolates = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    coconuts_seeds = IntegerField(constraints=[SQL("DEFAULT 5")], null=True)
    coconuts = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    has_open_farm = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    plot1 = TextField(constraints=[SQL("DEFAULT 'Empty!'")], null=True)
    plot2 = TextField(constraints=[SQL("DEFAULT 'Empty!'")], null=True)
    plot3 = TextField(constraints=[SQL("DEFAULT 'Empty!'")], null=True)
    plots = [plot1, plot2, plot3]

    class Meta:
        table_name = 'farms'




class Items(BaseModel):
    durability = IntegerField(null=True)
    owner_id = IntegerField(null=True)
    quantity = IntegerField(constraints=[SQL("DEFAULT 1")], null=True)
    reference_id = IntegerField(null=True)

    class Meta:
        table_name = 'items'


class Pets(BaseModel):
    active = IntegerField(null=True)
    health = IntegerField(null=True)
    level = IntegerField(constraints=[SQL("DEFAULT 1")], null=True)
    name = TextField(null=True)
    owner_id = IntegerField(null=True)
    rarity = TextField(null=True)
    species = TextField(null=True)
    xp = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)

    class Meta:
        table_name = 'pets'


class SqliteSequence(BaseModel):
    name = BareField(null=True)
    seq = BareField(null=True)

    class Meta:
        table_name = 'sqlite_sequence'
        primary_key = False


class Usercooldowns(BaseModel):
    id = ForeignKeyField(column_name='id', model=Users, primary_key=True)
    daily_used_last = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    worked_last = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)

    class Meta:
        table_name = 'user cooldowns'


class Megadrop(BaseModel):
    id = IntegerField(constraints=[SQL("DEFAULT 1")], primary_key=True)
    amount = IntegerField(constraints=[SQL("DEFAULT 0")])
    total_drops_missed = IntegerField(constraints=[SQL("DEFAULT 0")])
    total_drops = IntegerField(constraints=[SQL("DEFAULT 0")])
    date_started = TextField()
    times_missed = IntegerField(constraints=[SQL("DEFAULT 0")])
    COUNTER = IntegerField(constraints=[SQL("DEFAULT 0")])
    last_winner = TextField()

    class Meta:
        table_name = 'megadrop'


def create_tables():
    with database:
        database.create_tables([Users, Usercooldowns, Farms, Pets, Items, Megadrop])
