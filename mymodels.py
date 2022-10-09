from peewee import *
import json

with open('./data.json', 'r') as f:
    data = json.load(f)
    
database = PostgresqlDatabase('discordbotPGDB', **data['postgreSQLparams'])

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class dbUser(BaseModel):
    avatar = CharField(default='None', null=True)
    bank = IntegerField(default=0, null=True)
    id = BigIntegerField(unique=True)
    in_game = BooleanField(default=False, null=True)
    money = IntegerField(default=0, null=True)
    tokens = IntegerField(default=0, null=True)

    class Meta:
        table_name = 'user'

class dbFarms(BaseModel):
    almond_seeds = IntegerField(default=25, null=True)
    almonds = IntegerField(default=0, null=True)
    cacao = IntegerField(default=0, null=True)
    cacao_seeds = IntegerField(default=3, null=True)
    coconut_seeds = IntegerField(default=5, null=True)
    has_open_farm = BooleanField(default=False, null=True)
    id = ForeignKeyField(column_name='id', field='id', model=dbUser, primary_key=True)
    plots = CharField(default='000', null=True)

    class Meta:
        table_name = 'farms'

class dbItems(BaseModel):
    buy_price = IntegerField(default=0, null=True)
    durability = IntegerField(null=True)
    item_id = AutoField()
    item_name = CharField(null=True)
    owner = ForeignKeyField(column_name='owner_id', field='id', model=dbUser, null=True)
    quantity = IntegerField()
    rarity = CharField(null=True)
    sell_value = IntegerField(default=0, null=True)
    tradeable = BooleanField(default=True, null=True)
    useable = BooleanField(default=False, null=True)

    class Meta:
        table_name = 'items'

class dbPets(BaseModel):
    active = BooleanField(default=False, null=True)
    health = IntegerField(null=True)
    level = IntegerField(default=1, null=True)
    name = CharField(null=True)
    owner = ForeignKeyField(column_name='owner_id', field='id', model=dbUser)
    pet_id = AutoField()
    rarity = CharField(null=True)
    species = CharField(null=True)
    xp = IntegerField(default=0, null=True)

    class Meta:
        table_name = 'pets'

class dbUserCooldowns(BaseModel):
    daily_used_last = DoubleField(default=0, null=True)
    id = ForeignKeyField(column_name='id', field='id', model=dbUser, primary_key=True)
    work_used_last = DoubleField(default=0, null=True)

    class Meta:
        table_name = 'user_cooldowns'

