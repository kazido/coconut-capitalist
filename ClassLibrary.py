import datetime
import random
from random import randint
import randfacts
import discord
from dataclasses import dataclass
from discord.ext import commands
from typing import Callable
import asyncio
from Cogs.Pets import pet_multipliers
import json


# Class library for storing all classes necessary for the Economy Bot
def get_role(ctx):
    classes = [peasant, farmer, citizen, educated, cultured, wise, expert]
    for role in classes:
        retrieve_role = discord.utils.get(ctx.guild.roles, name=role.name.capitalize())
        if retrieve_role in ctx.author.roles:
            return role


async def cool_down_embed(off_cd, ctx, now, command):
    cool_down_left_seconds = int(off_cd - now)
    day = cool_down_left_seconds // 86400
    hours = (cool_down_left_seconds - (day * 86400)) // 3600
    minutes = (cool_down_left_seconds - ((day * 86400) + (hours * 3600))) // 60
    seconds = cool_down_left_seconds - ((day * 86400) + (hours * 3600) + (minutes * 60))
    cool_down_left_formatted = datetime.time(hours, minutes, seconds)
    embed = discord.Embed(color=discord.Colour.red())
    embed.add_field(name=f"You already collected your {command}", value=f"Next in: **{cool_down_left_formatted}**")
    embed.set_footer(text=f"User: {ctx.author.name}")
    await ctx.send(embed=embed)

# Load the json file where all the rank dialogue is stored
with open('./EconomyBotProjectFiles/ranks.json', 'r') as file:
    ranks = json.load(file)


@dataclass
class Rank:
    name: str
    wage: int
    work_dialogue: list
    emoji: str
    price: int
    description: str
    perms: list

    def work(self):
        return random.choice(self.work_dialogue)


peasant = Rank("Peasant", 2500, ranks['peasant']['responses'], ":palms_up_together:", 0, ranks['peasant']['description'], ranks['peasant']['perks'])
farmer = Rank("Farmer", 10000, ranks['farmer']['responses'], ":basket:", 10, ranks['farmer']['description'], ranks['farmer']['perks'])
citizen = Rank("Citizen", 25000, ranks['citizen']['responses'], ":busts_in_silhouette:", 45, ranks['citizen']['description'], ranks['citizen']['perks'])
educated = Rank("Educated", 60000, ranks['educated']['responses'], ":book:", 100, ranks['educated']['description'], ranks['educated']['perks'])
cultured = Rank("Cultured", 130000, ranks['cultured']['responses'], ":money_with_wings:", 250, ranks['cultured']['description'], ranks['cultured']['perks'])
weathered = Rank("Weathered", 240000, ranks['weathered']['responses'], ":mountain:", 500, ranks['weathered']['description'], ranks['weathered']['perks'])
wise = Rank("Wise", 375000, ranks['wise']['responses'], ":trident:", 1000, ranks['wise']['description'], ranks['wise']['perks'])
expert = Rank("Expert", 1000000, ranks['expert']['responses'], ":gem:", 10000, ranks['expert']['description'], ranks['expert']['perks'])


# This class will have methods to update the user's money, statuses, and id.
class User:
    def __init__(self, ctx: discord.ext.commands.Context = None, interaction: discord.Interaction = None):
        if ctx and not interaction:
            self.user_id = ctx.author.id
            self.bot = ctx.bot
            self.ctx = ctx
        elif interaction and not ctx:
            self.user_id = interaction.user.id
            self.bot = interaction.client
            self.interaction = interaction

    async def work(self):
        # Calculates time left until work can be used (6 hour cooldown)
        ct = datetime.datetime.now()
        now = ct.timestamp()
        work_off_cd = await self.worked_last() + 21600
        if now <= work_off_cd:
            await cool_down_embed(work_off_cd, self.ctx, now, "work")
            return
        else:
            await self.bot.dbcooldowns.update_one({"_id": self.user_id}, {"$set": {"worked_last": now}})
            role = get_role(self.ctx)
            work_amount = role.wage
            embed = discord.Embed(
                color=discord.Color.blue()
            )
            pet_rarity = await self.bot.dbpets.find_one({"$and": [{"owner_id": self.user_id}, {"active": True}]})
            # If the user has a pet and the bonus isn't 0, send an embed showing the pet bonus
            if pet_rarity and work_amount * pet_multipliers[pet_rarity['rarity']]['work'] != 0:
                work_pet_bonus = work_amount * pet_multipliers[pet_rarity["rarity"]]["work"]
                await self.update_balance(work_amount + int(work_pet_bonus))
                embed.add_field(name=f"{role.work()}", value=f"You received **{'{:,}'.format(work_amount)}** bits\n"
                                                             f"Your pet earned you an extra **{'{:,}'.format(int(work_pet_bonus))}** bits", inline=False)
            else:
                await self.update_balance(work_amount)
                embed.add_field(name=f"{role.work()}", value=f"You received **{'{:,}'.format(work_amount)}** bits", inline=False)
            embed.add_field(name="Bits",
                            value=f"You have {'{:,}'.format(await self.check_balance('bits'))} bits",
                            inline=False)
            embed.set_footer(text=f"User: {self.ctx.author.name}")
            await self.ctx.send(embed=embed)

    async def daily(self):
        # Calculate timestamp when command will be off cool down
        ct = datetime.datetime.now()
        now = ct.timestamp()
        off_cd = await self.daily_used_last() + 79200
        # Check when daily was last used
        if now <= off_cd:
            # Converting seconds left into an actual cool down formatted properly in HH:MM:SS
            await cool_down_embed(off_cd, self.ctx, now, "daily")
            return
        else:
            await self.bot.dbcooldowns.update_one({"_id": self.user_id}, {"$set": {"daily_used_last": now}})
            daily_amount = 1
            embed = discord.Embed(
                color=discord.Color.blue()
            )
            pet_rarity = await self.bot.dbpets.find_one({"$and": [{"owner_id": self.user_id}, {"active": True}]})
            if pet_rarity and daily_amount * pet_multipliers[pet_rarity["rarity"]]["daily"] != 0:
                daily_pet_bonus = daily_amount * pet_multipliers[pet_rarity["rarity"]]["daily"]
                await self.update_tokens(daily_amount + daily_pet_bonus)
                embed.add_field(name=f"Received {'{:,}'.format(daily_amount)} + ({'{:,}'.format(daily_pet_bonus)} "
                                     f"*pet bonus*) tokens",
                                value=f"You have {'{:,}'.format(await self.check_balance('tokens'))} tokens",
                                inline=False)
            else:
                await self.update_tokens(daily_amount)
                embed.add_field(name=f"Received {'{:,}'.format(daily_amount)} tokens",
                                value=f"You have {'{:,}'.format(await self.check_balance('tokens'))} tokens",
                                inline=False)
            embed.add_field(name=f"Random Fact", value=f'{randfacts.get_fact()}', inline=False)
            embed.set_footer(text=f"User: {self.ctx.author.name}")
            await self.ctx.send(embed=embed)

    async def check_balance(self, balance_type):
        user_in_database = await self.bot.db.find_one({"_id": self.user_id})
        if balance_type == "bits":
            return user_in_database["money"]
        elif balance_type == "tokens":
            return user_in_database["tokens"]

    async def check_xp(self):
        user_in_database = await self.bot.db.find_one({"_id": self.user_id})
        return user_in_database["xp"]

    async def daily_used_last(self):
        user_in_database = await self.bot.dbcooldowns.find_one({"_id": self.user_id})
        return user_in_database["daily_used_last"]

    async def worked_last(self):
        user_in_database = await self.bot.dbcooldowns.find_one({"_id": self.user_id})
        return user_in_database["worked_last"]

    # Methods for updating said stats
    async def update_balance(self, amount):
        await self.bot.db.update_one({"_id": self.user_id}, {"$inc": {"money": amount}})

    async def update_tokens(self, amount):
        await self.bot.db.update_one({"_id": self.user_id}, {"$inc": {"tokens": amount}})

    async def game_status_to_true(self):
        # When the status's are updated, it also updates self.in_game to True or False
        # Now just self.in_game is required to check status
        await self.bot.db.update_one({"_id": self.user_id}, {"$set": {"in_game": True}})

    async def game_status_to_false(self):
        await self.bot.db.update_one({"_id": self.user_id}, {"$set": {"in_game": False}})

    # Checks to make sure the user isn't betting more than they have or 0
    async def bet_checks(self, bet) -> object:
        user_in_database = await self.bot.db.find_one({"_id": self.user_id})
        # If they try to bet more than they have in their account.
        if int(bet) > user_in_database['money']:
            return f"You don't have enough to place this bet. Balance: {user_in_database['money']} bits", False
        # If their bet is 0, stop the code.
        elif int(bet) < 0:
            return f"You can't bet a negative amount.", False
        elif bet == 0:
            return "You can't bet 0 bits.", False
        else:
            return "Passed", True


class Drop:
    def __init__(self, bot, amount):
        self.bot = bot
        self.amount = amount

    def drop_double(self):
        odds = random.randint(0, 100)
        if odds in range(0, 5):
            message = f"claimed a **double** drop! **+{'{:,}'.format(self.amount * 2)}** bits"
            color = 0xcc8c16
            return message, self.amount, True, color
        else:
            message = f"claimed the drop! **+{'{:,}'.format(self.amount)}** bits"
            color = 0xf0b57a
            return message, self.amount, False, color

    async def prep_claim(self, channel):
        message, drop_amount, status, color = self.drop_double()
        embed = discord.Embed(
            title="A drop has appeared! 📦",
            description=f"This drop contains **{'{:,}'.format(self.amount)}** bits!",
            color=0x946c44
        )
        embed.set_footer(text="React to claim!")
        expired_embed = discord.Embed(
            title="This drop expired :(",
            description=f"This **{'{:,}'.format(self.amount)}** bit drop has expired.",
            color=0x484a4a
        )
        expired_embed.set_footer(text="Drops happen randomly and last for an hour!")

        class ClaimDropButtons(discord.ui.View):
            async def on_timeout(self) -> None:
                if self.claimed:
                    return
                await drop.edit(embed=expired_embed, view=None)

            bot = self.bot

            def __init__(self, *, timeout=3600):
                super().__init__(timeout=timeout)
                self.claimed = False

            @discord.ui.button(label="CLAIM", style=discord.ButtonStyle.green)
            async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                user = User(interaction=interaction)
                claimed_embed = discord.Embed(
                    title="This drop has been claimed!",
                    description=f"{interaction.user.name} {message}",
                    color=color
                )
                claimed_embed.set_footer(text="Drops happen randomly and last for an hour!")
                if status is True:
                    await user.update_balance(int(drop_amount * 2))
                else:
                    await user.update_balance(int(drop_amount))
                await interaction.response.edit_message(embed=claimed_embed, view=None)
                self.claimed = True

        drop = await channel.send(embed=embed, view=ClaimDropButtons())


class Inventory:
    def __init__(self, ctx: discord.ext.commands.Context = None, interaction: discord.Interaction = None):
        if ctx and not interaction:
            self.ctx = ctx
            self.bot = ctx.bot
            self.id = ctx.author.id
        elif interaction and not ctx:
            self.id = interaction.user.id
            self.bot = interaction.client
            self.interaction = interaction

    async def add_item(self, item, quantity: int = 1, durability=None):
        item_exists = await self.bot.dbitems.find_one({"owner_id": self.id, "item": item})
        if item_exists:
            await self.bot.dbitems.update_one({"owner_id": self.id, "item": item}, {"$inc": {"quantity": quantity}})
        else:
            await self.bot.dbitems.insert_one({"owner_id": self.id, "item": item, "quantity": quantity,
                                               "durability": durability})

    async def remove_item(self, item, quantity=None):
        if isinstance(quantity, int):
            await self.bot.dbitems.update_one({"owner_id": self.id, "item": item}, {"$inc": {"quantity": -quantity}})
            remaining_items = (await self.bot.dbitems.find_one({"owner_id": self.id, "item": item}))["quantity"]
            if remaining_items == 0:
                await self.bot.dbitems.delete_one({"owner_id": self.id, "item": item})
        else:
            await self.bot.dbitems.delete_one({"owner_id": self.id, "item": item})

    async def get(self, item=None):
        if item:
            return await self.bot.dbitems.find_one({"owner_id": self.id, "item": item})
        else:
            items = self.bot.dbitems.find({"owner_id": self.id})
            items = await items.to_list(length=None)
            return items


class Item:
    def __init__(self, name: str, price: int = None, durability: int = None):
        self.name = name
        self.price = price
        self.durability = durability


# Shovels - has durability, can be repaired and upgraded
shovel_lv1 = Item("basic_shovel", price=25000, durability=25)
shovel_lv2 = Item("reinforced_shovel", durability=50)
shovel_lv3 = Item("steel_shovel", durability=100)
# Rare drop from digging
unbreakable_shovel = Item("SH0V3L")

# Fishing Rods - communal pool that resets every day. collection books
fishing_rod = Item("fishing_rod", price=50000)

# Pickaxes - mines are open for a certain time during the day. better pickaxe = more ores
pickaxe_lv1 = Item("pickaxe", price=100000)
pickaxe_lv2 = Item("premium_pickaxe", price=500000)
pickaxe_lv3 = Item("mining_drill", price=1000000)

# Usable items - still working on these
golden_ticket = Item("golden_ticket", durability=1)
robber_token = Item('robber_token', durability=1)

# Seeds - for growing!
almond_seeds = Item("almond_seed", price=10000, durability=1)
coconut_seeds = Item("coconut_seed", price=80000, durability=1)
cacao_seeds = Item("cacao_seed", price=500000, durability=1)
