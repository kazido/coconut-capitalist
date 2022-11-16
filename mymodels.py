from peewee import *
import json

with open('././config.json', 'r') as file:
    data = json.load(file)

database = SqliteDatabase(database=data['sqlite_path'])


class UnknownField(object):
    def __init__(self, *_, **__): pass


class BaseModel(Model):
    class Meta:
        database = database


class Users(BaseModel):
    area = IntegerField(constraints=[SQL("DEFAULT 0")])
    avatar = TextField(null=True)
    axe = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    bank = IntegerField(null=True)
    combat_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    fishing_rod = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    fishing_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    foraging_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    in_game = IntegerField(null=True)
    mining_xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    money = IntegerField(null=True)
    name = TextField(null=True)
    pickaxe = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    tokens = IntegerField(null=True)
    weapon = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    xp = IntegerField(constraints=[SQL("DEFAULT 100")], null=True)
    drops_claimed = IntegerField(constraints=[SQL("DEFAULT 0")])

    class Meta:
        table_name = 'users'


class Farms(BaseModel):
    almond_seeds = IntegerField(null=True)
    almond = IntegerField(null=True)
    cacao_seeds = IntegerField(null=True)
    cacao = IntegerField(null=True)
    coconut_seeds = IntegerField(null=True)
    coconut = IntegerField(null=True)
    has_open_farm = IntegerField(constraints=[SQL("DEFAULT 0")], null=True)
    id = ForeignKeyField(column_name='id', model=Users, primary_key=True)
    plot1 = TextField(constraints=[SQL("DEFAULT 'Empty!'")], null=True)
    plot2 = TextField(constraints=[SQL("DEFAULT 'Empty!'")], null=True)
    plot3 = TextField(constraints=[SQL("DEFAULT 'Empty!'")], null=True)

    class Meta:
        table_name = 'farms'


class Items(BaseModel):
    durability = IntegerField(null=True)
    item_name = TextField(null=True)
    owner_id = IntegerField(null=True)
    quantity = IntegerField(null=True, default=1)
    reference_id = IntegerField(null=True)
    item_type = TextField(null=True)

    class Meta:
        table_name = 'items'


class Pets(BaseModel):
    active = IntegerField(null=True)
    health = IntegerField(null=True)
    level = IntegerField(null=True)
    name = TextField(null=True)
    owner_id = IntegerField(null=True)
    rarity = TextField(null=True)
    species = TextField(null=True)
    xp = IntegerField(null=True)

    class Meta:
        table_name = 'pets'


class SqliteSequence(BaseModel):
    name = BareField(null=True)
    seq = BareField(null=True)

    class Meta:
        table_name = 'sqlite_sequence'
        primary_key = False


class Usercooldowns(BaseModel):
    daily_used_last = IntegerField(null=True)
    id = ForeignKeyField(column_name='id', model=Users, primary_key=True)
    worked_last = IntegerField(null=True)

    class Meta:
        table_name = 'user cooldowns'


class Megadrop(BaseModel):
    id = IntegerField(primary_key=True, default=1)
    amount = IntegerField(default=0)
    total_drops_missed = IntegerField(default=0)
    total_drops = IntegerField(default=0)
    date_started = TextField()
    times_missed = IntegerField(default=0)
    COUNTER = IntegerField(default=0)
    last_winner = TextField()

    class Meta:
        table_name = 'megadrop'
