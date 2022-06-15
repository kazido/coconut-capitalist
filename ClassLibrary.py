import datetime
import random
from random import randint
import randfacts
import discord
from dataclasses import dataclass
from discord.ext import commands


# Class library for storing all classes necessary for the Economy Bot

def get_role(ctx):
    classes = [peasant, farmer, citizen, educated, wise, expert]
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


@dataclass
class Rank:
    name: str
    wage: int
    work_dialogue: list
    emoji: str
    price: int
    description: str
    perms: list
    raw_perks: list

    def work(self):
        return random.choice(self.work_dialogue)


peasant_responses, peasant_description, peasant_perks, peasant_raw_perks \
    = ["You actually manage to scrape up some bits. How wonderful.",
       "Someone donated a little more than normal. How kind.",
       "You are a peasant. Feel bad."], \
      "Born into the lower class, destined for the upper class.", [None], [None]
farmer_responses, farmer_description, farmer_perks, farmer_raw_perks \
    = ["You toiled hard in the fields, picking... bits?",
       "Your spouse hasn't seen you all day, since you've been farming bits.",
       "You harvested a plentiful amount of bits."], \
      "A hard working farmer.\n Those coconuts aren't going to farm themselves.", \
      ["-pay :money_with_wings:", "-farm :deciduous_tree:"], ["Pay", "Farm", "Plant", "Barn"]
citizen_responses, citizen_description, citizen_perks, citizen_raw_perks \
    = ["You spend the day being a slave to the system.",
       "Work, work, work. 9-5, just killing time.",
       "When is your lunch break?"], "The beginning of a new chapter. Welcome to the real world.", [None], [None]
educated_responses, educated_description, educated_perks, educated_raw_perks \
    = ["Your dad owns a boat.",
       "Yeah, you finished college.",
       "Your dad also owns Microsoft."], "Why not get a 31 on your ACT and get into a pretty nice college?", \
      [None], [None]
wise_responses, wise_description, wise_perks, wise_raw_perks \
    = ["You exit the cave. Look at the sun!.",
       "You preach your dumb philosophy; Plato smiles from above.",
       "You discover that it takes 10,000 bits to get to the center of a lollipop."], "I farm, therefore I am.", \
      [None], [None]
expert_responses, expert_description, expert_perks, expert_raw_perks \
    = ["You deserve this.",
       "Only the finest of people can work this hard.",
       "There's no shot you've been outside lately."], "Master to all. Servant to none. Coconut expert.", [None], [None]

peasant = Rank("Peasant", 2500, peasant_responses, ":palms_up_together:", 0, peasant_description,
               peasant_perks, peasant_raw_perks)
farmer = Rank("Farmer", 10000, farmer_responses, ":basket:", 10, farmer_description, farmer_perks, farmer_raw_perks)
citizen = Rank("Citizen", 25000, citizen_responses, ":busts_in_silhouette:", 45, citizen_description,
               citizen_perks, citizen_raw_perks)
educated = Rank("Educated", 60000, educated_responses, ":book:", 100, educated_description,
                educated_perks, educated_raw_perks)
wise = Rank("Wise", 200000, wise_responses, ":trident:", 400, wise_description, wise_perks, wise_raw_perks)
expert = Rank("Expert", 1000000, expert_responses, ":gem:", 1000, expert_description, expert_perks, expert_raw_perks)


# This class will have methods to update the user's money, statuses, and id.
class User:
    def __init__(self, ctx: discord.ext.commands.Context = None, interaction: discord.Interaction = None):
        if ctx and not interaction:
            self.ctx = ctx
            self.bot = ctx.bot
            self.user_id = ctx.author.id
        elif interaction and not ctx:
            self.user_id = interaction.user.id
            self.bot = interaction.client
            self.interaction = interaction

    async def work(self):
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
            await self.update_balance(work_amount)
            embed = discord.Embed(
                color=discord.Color.blue()
            )
            embed.add_field(name=f"{role.work()}", value=f"You received **{'{:,}'.format(work_amount)}** bits",
                            inline=False)
            embed.add_field(name="Bits",
                            value=f"You have {'{:,}'.format(await self.check_balance('bits'))} bits",
                            inline=False)
            embed.set_footer(text=f"User: {self.ctx.author.name}")
            await self.ctx.send(embed=embed)
            # Methods for checking user's current stats (like money, xp, status, etc.)

    async def daily(self):
        # Calculate timestamp when command will be off cool down
        ct = datetime.datetime.now()
        now = ct.timestamp()
        off_cd = await self.daily_used_last() + 86400
        # Check when daily was last used
        if now <= off_cd:
            # Converting seconds left into an actual cool down formatted properly in HH:MM:SS
            await cool_down_embed(off_cd, self.ctx, now, "daily")
            return
        else:
            await self.bot.dbcooldowns.update_one({"_id": self.user_id}, {"$set": {"daily_used_last": now}})
            daily_amount = 2
            await self.update_coconuts(daily_amount)
            embed = discord.Embed(
                color=discord.Color.blue()
            )
            embed.add_field(name=f"Received {'{:,}'.format(daily_amount)} coconuts",
                            value=f"You have {'{:,}'.format(await self.check_balance('coconuts'))} coconuts",
                            inline=False)
            embed.add_field(name=f"Random Fact", value=f'{randfacts.get_fact()}', inline=False)
            embed.set_footer(text=f"User: {self.ctx.author.name}")
            await self.ctx.send(embed=embed)

    async def check_balance(self, balance_type):
        user_in_database = await self.bot.db.find_one({"_id": self.user_id})
        farm_database = await self.bot.dbfarms.find_one({"_id": f"{str(self.user_id)}"})
        if balance_type == "bits":
            return user_in_database["money"]
        elif balance_type == "coconuts":
            return farm_database["coconuts"]

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

    async def update_coconuts(self, amount):
        await self.bot.dbfarms.update_one({"_id": f"{self.user_id}"}, {"$inc": {"coconuts": amount}})

    async def game_status_to_true(self):
        # When the status's are updated, it also updates self.in_game to True or False
        # Now just self.in_game is required to check status
        await self.bot.db.update_one({"_id": self.user_id}, {"$set": {"in_game": True}})

    async def game_status_to_false(self):
        await self.bot.db.update_one({"_id": self.user_id}, {"$set": {"in_game": False}})

    async def update_xp(self, amount):
        await self.bot.db.update_one({"_id": self.user_id}, {"$inc": {"xp": amount}})

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


class Item:
    def __init__(self, durability, name):
        self.durability = durability
        self.name = name


class Shovel(Item):
    def __init__(self):
        Item.__init__(self, 25, "shovel")


class UnbreakableShovel(Item):
    def __init__(self):
        Item.__init__(self, 1, "SH0V3L")


class Rod(Item):
    def __init__(self):
        Item.__init__(self, 1, "fishing rod")
