import random
from random import randint, shuffle
import discord
from discord.ext import commands
from Cogs.ErrorHandler import registered
from ClassLibrary import *
from Cogs.EconomyCog import get_role

common_pets = ["dog", "cat", "mouse", "rabbit", "fox", "bat", "goat", "chicken", "robin"]
uncommon_pets = ["bunny", "cow", "chipmunk", "frog", "pig", "snake", "turtle", "penguin"]
rare_pets = ["owl", "giraffe", "fox", "panda", "horse", "raccoon", "koala", "monkey"]
super_rare_pets = ["polar bear", "octopus", "moose", "eagle", "dolphin", "dodo"]
legendary_pets = ["lion", "dragon", "unicorn", "phoenix", "elephant"]
pets = []
for x in common_pets, uncommon_pets, rare_pets, super_rare_pets, legendary_pets:
    pets.append(x)

rarity_health = {"common": 100,
                 "uncommon": 250,
                 "rare": 500,
                 "super rare": 750,
                 "legendary": 1000}


class Page:
    def __init__(self, number, embed, location="middle"):
        self.number = number
        self.embed = embed
        self.location = location


embed_title = "Welcome to the pet shop!"
embed_description = "Due to current exotic pet laws, you can only own one pet at a time\n"\
                    "Pets are companions who you can name, level up, and interact with!"
embed1 = discord.Embed(title=embed_title, description=embed_description, color=0xfdffe8)\
    .add_field(name="Random Common Pet", value="**100,000** bits")
embed2 = discord.Embed(title=embed_title, description=embed_description, color=0xc9ff94)\
    .add_field(name="Random Uncommon Pet", value="**500,000** bits")
embed3 = discord.Embed(title=embed_title, description=embed_description, color=0x87c8fa)\
    .add_field(name="Random Rare Pet", value="**1,000,000** bits")
embed4 = discord.Embed(title=embed_title, description=embed_description, color=0x0f53ff)\
    .add_field(name="Random Super Rare Pet", value="**5,000,000** bits")
embed5 = discord.Embed(title=embed_title, description=embed_description, color=0x7300ff)\
    .add_field(name="Random Legendary Pet", value="**10,000,000** bits")
embeds = [embed1, embed2, embed3, embed4, embed5]
pages = []
for index, i in enumerate(embeds):
    index = Page(index, i)
    pages.append(index)


class Pet:
    def __init__(self, species, rarity, name=None):
        self.species = species
        self.name = name
        self.rarity = rarity
        self.level = 1
        self.health = self.set_health(rarity)

    async def rename(self, name):
        self.name = name
        return self.name

    async def set_health(self, rarity):
        self.health = rarity_health[rarity]
        return self.health


class PetsCog(commands.Cog, name='Pets'):
    """Purchase, feed, and interact with pets!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @commands.command(name="Purchase Pet", aliases=["purchasepet", "buypet"],
                      description="Buy a pet egg and see what you get!", brief="-buypet")
    async def purchase_pet(self, ctx):
        user = User(ctx)

        class PetPaginatorButtons(discord.ui.View):
            def __init__(self, page, *, timeout=180):
                super().__init__(timeout=timeout)
                self.page = page

            async def on_timeout(self):
                for child in self.children:
                    child.disabled = True
                embed = discord.Embed(
                    title="Pet Shop - CLOSED",
                    description="This pet shop sat open for a long time with no customers, so it had to close.",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed, view=self)

            def purchase_pet(self, cost, rarity):
                pass

            def next_page(self):
                current_page = pages.index(self.page)
                try:
                    self.page = pages[current_page + 1]
                except IndexError:
                    return
                return self.page

            def back_page(self):
                current_page = pages.index(self.page)
                if current_page == 0:
                    return
                self.page = pages[current_page - 1]
                return self.page

            @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.blurple, disabled=True, custom_id="1")
            async def back_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                if self.page.number == len(pages)-1:
                    self.children[1].disabled = False
                self.back_page()
                if self.page == pages[0]:
                    button.disabled = True
                else:
                    button.disabled = False
                await interaction.response.edit_message(embed=self.page.embed, view=self)

            @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.blurple, custom_id="2")
            async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                if self.page == pages[0]:
                    self.children[0].disabled = False
                self.next_page()
                if self.page.number == len(pages)-1:
                    button.disabled = True
                else:
                    button.disabled = False
                await interaction.response.edit_message(embed=self.page.embed, view=self)

        message = await ctx.send(embed=pages[0].embed, view=PetPaginatorButtons(pages[0]))

    @registered()
    @commands.command(name="Dig", description="Dig for unlimited loot! Well, until your shovel breaks that is.")
    async def dig(self, ctx):
        has_shovel = await ctx.bot.dbitems.find_one({'$and': [{"owner_id": ctx.author.id}, {"item_name": "shovel"}]})
        if not has_shovel:
            embed = discord.Embed(
                title="Cannot dig",
                description="You do not own a shovel!",
                colour=discord.Colour.red()
            )
            await ctx.send(embed=embed)
            return
        common_pool = ['almond_seeds', 'bits', 'almonds']
        uncommon_pool = ['coconut_seeds', 'cacao_seeds', 'bits']
        rare_pool = ['iron_ore', 'silver_ore', 'bits', 'coconuts']
        super_rare_pool = ['gold_ore', 'platinum_ore', 'diamond_ore', 'cacao']
        legendary_pool = ['reactor_catalyst', 'SH0V3L', 'golden_ticket']
        dig_roll = randint(1, 1000)
        if dig_roll <= 750:
            pool = common_pool
            color = 0xfffce0
        elif 750 < dig_roll <= 900:
            pool = uncommon_pool
            color = 0xfff8b5
        elif 900 < dig_roll <= 975:
            pool = rare_pool
            color = 0xfff170
        elif 975 < dig_roll <= 998:
            pool = super_rare_pool
            color = 0xffe81c
        else:
            pool = legendary_pool
            color = 0xff1cf7
        item = random.choice(pool)
        if item in ['almonds', 'almond_seeds', 'coconuts', 'coconut_seeds', 'cacao', 'cacao_seeds']:
            await ctx.bot.dbfarms.update_one({"_id": str(ctx.author.id)}, {"$inc": {item: 1}})
        elif item == 'bits':
            amount = 0
            if pool == common_pool:
                amount = randint(500, 1000)
            elif pool == uncommon_pool:
                amount = randint(1000, 5000)
            elif pool == rare_pool:
                amount = randint(10000, 25000)
            user = User(ctx)
            await user.update_balance(amount)
            item = f"{amount} bits"
        else:
            await ctx.bot.dbitems.insert_one({'durability': 1, 'item_name': item,
                                              'owner_id': ctx.author.id, 'quantity': 1})
        embed = discord.Embed(
            title="Dig, dig, dig!",
            description=f"You dug up **{item.replace('_', ' ')}**!",
            color=color
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PetsCog(bot))
