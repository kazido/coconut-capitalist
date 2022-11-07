from peewee import *
import json

with open('./data.json', 'r') as file:
    data = json.load(file)

database = PostgresqlDatabase(database=data['postgreSQLparams']['PGDATABASE'],
                              **{'host': data['postgreSQLparams']['PGHOST'], 'port': data['postgreSQLparams']['PGPORT'],
                                 'user': data['postgreSQLparams']['PGUSER'],
                                 'password': data['postgreSQLparams']['PGPASSWORD']})


class UnknownField(object):
    def __init__(self, *_, **__): pass


class BaseModel(Model):
    class Meta:
        database = database


class Users(BaseModel):
    avatar = CharField(null=True)
    bank = IntegerField(null=True)
    id = BigIntegerField(null=False)
    in_game = BooleanField(null=True)
    money = IntegerField(null=True)
    name = CharField(null=True)
    tokens = IntegerField(null=True)
    xp = IntegerField(null=True, default=100)
    combat_xp = IntegerField(null=True, default=100)
    mining_xp = IntegerField(null=True, default=100)
    foraging_xp = IntegerField(null=True, default=100)
    fishing_xp = IntegerField(null=True, default=100)
    area = SmallIntegerField(default=0)
    weapon = SmallIntegerField(default=0)
    pickaxe = SmallIntegerField(default=0)
    axe = SmallIntegerField(default=0)
    fishing_rod = SmallIntegerField(default=0)

    class Meta:
        table_name = 'users'


class Farms(BaseModel):
    almond_seeds = IntegerField(null=True)
    almonds = IntegerField(null=True)
    cacao_seeds = IntegerField(null=True)
    cacaos = IntegerField(null=True)
    coconut_seeds = IntegerField(null=True)
    coconuts = IntegerField(null=True)
    has_open_farm = BooleanField(null=True)
    id = ForeignKeyField(column_name='id', field='id', model=Users, primary_key=True)
    plot1 = CharField(constraints=[SQL("DEFAULT 'Empty!'::character varying")], null=True)
    plot2 = CharField(constraints=[SQL("DEFAULT 'Empty!'::character varying")], null=True)
    plot3 = CharField(constraints=[SQL("DEFAULT 'Empty!'::character varying")], null=True)

    class Meta:
        table_name = 'farms'


class Items(BaseModel):
    durability = IntegerField(null=True)
    id = UUIDField(constraints=[SQL("DEFAULT gen_random_uuid()")], primary_key=True)
    item = CharField(null=True)
    owner_id = BigIntegerField(null=True)
    quantity = IntegerField(null=True)
    rarity = CharField(max_length=15, null=True)
    useable = BooleanField(default=False)
    tradeable = BooleanField(default=True)
    buy_price = IntegerField(default=0, null=True)
    sell_price = IntegerField(default=0, null=True)

    class Meta:
        table_name = 'items'


class Pets(BaseModel):
    active = BooleanField(null=True)
    health = IntegerField(null=True)
    id = UUIDField(constraints=[SQL("DEFAULT gen_random_uuid()")], primary_key=True)
    level = IntegerField(null=True)
    name = TextField(null=True)
    owner_id = BigIntegerField(null=True)
    rarity = TextField(null=True)
    species = TextField(null=True)
    xp = IntegerField(null=True)

    class Meta:
        table_name = 'pets'


class Usercooldowns(BaseModel):
    daily_used_last = DoubleField(null=True)
    id = ForeignKeyField(column_name='id', field='id', model=Users, primary_key=True)
    worked_last = DoubleField(null=True)

    class Meta:
        table_name = 'user cooldowns'
