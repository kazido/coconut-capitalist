from cogs.ErrorHandler import registered, own_pet
import pathlib
import discord
from discord.ext import commands
import random
from random import randint
import json

with open('projfiles/pets.json', 'r') as file:
    pets = json.load(file)


class Page:
    pages = []

    def __init__(self, number, embed, cost, rarity):
        self.number = number
        self.embed = embed
        self.cost = cost
        self.rarity = rarity
        self.style = discord.ButtonStyle.grey
        self.can_buy = False
        self.emoji = None
        self.label = "Can't afford"
        self.pages.append(self)


embed_title = "Welcome to the pet shop!"
embed_description = "Pets are companions who you can name, level up, and interact with!\n" \
                    "Different rarities have **higher** health and **better** findings.\n" \
                    "*If you should be able to afford the pet, try withdrawing the amount of bits from your bank.*"
embed1 = discord.Embed(title=embed_title, description=embed_description, color=0xfdffe8) \
    .add_field(name="Random Common Pet", value="**100,000** bits")
embed2 = discord.Embed(title=embed_title, description=embed_description, color=0xc9ff94) \
    .add_field(name="Random Uncommon Pet", value="**500,000** bits")
embed3 = discord.Embed(title=embed_title, description=embed_description, color=0x87c8fa) \
    .add_field(name="Random Rare Pet", value="**1,000,000** bits")
embed4 = discord.Embed(title=embed_title, description=embed_description, color=0x0f53ff) \
    .add_field(name="Random Super Rare Pet", value="**5,000,000** bits")
embed5 = discord.Embed(title=embed_title, description=embed_description, color=0x7300ff) \
    .add_field(name="Random Legendary Pet", value="**10,000,000** bits")
embed6 = discord.Embed(title=embed_title, description=embed_description, color=0xff0000) \
    .add_field(name="The Premium Pet", value="**250,000,000** bits")
page1 = Page(1, embed1, 100000, "common")
page2 = Page(2, embed2, 500000, "uncommon")
page3 = Page(3, embed3, 1000000, "rare")
page4 = Page(4, embed4, 5000000, "super_rare")
page5 = Page(5, embed5, 10000000, "legendary")
page6 = Page(6, embed6, 250000000, "premium")


class Pet:
    def __init__(self, species, rarity, name):
        self.species = species
        self.name = name
        self.rarity = rarity
        self.level = 1
        self.health = pets[self.rarity]["health"]


class PetsCog(commands.Cog, name='Pets'):
    """Purchase, feed, and interact with pets!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @commands.command(name="Purchase Pet", aliases=["purchasepet", "buypet", "petshop"],
                      description="Buy a pet egg and see what you get!", brief="-buypet")
    async def purchase_pet(self, ctx):
        user = User(ctx)
        for x in Page.pages:
            if await user.check_balance("bits") >= x.cost:
                x.can_buy = True
                x.emoji = "💰"
                x.label = "Purchase"
                x.style = discord.ButtonStyle.green

        class PetPaginatorButtons(discord.ui.View):
            def __init__(self, page, *, timeout=180):
                super().__init__(timeout=timeout)
                self.page = page

                purchase_button = self.children[1]
                purchase_button.label = self.page.label
                purchase_button.emoji = self.page.emoji
                purchase_button.disabled = not self.page.can_buy
                purchase_button.style = self.page.style
                purchase_button.custom_id = "purchase"

            async def on_timeout(self):
                for child in self.children:
                    child.disabled = True
                embed = discord.Embed(
                    title="Pet Shop - CLOSED",
                    description="This pet shop sat open for a long time with no customers, so it had to close.",
                    color=discord.Color.red()
                )
                await message.edit(embed=embed, view=self)

            def next_page(self):
                current_page = Page.pages.index(self.page)
                try:
                    self.page = Page.pages[current_page + 1]
                except IndexError:
                    return

                return self.page

            def back_page(self):
                current_page = Page.pages.index(self.page)
                if current_page == 0:
                    return
                self.page = Page.pages[current_page - 1]
                return self.page

            @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.blurple, disabled=True, custom_id="back")
            async def back_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                if self.page.number == len(Page.pages):
                    self.children[2].disabled = False
                self.back_page()
                if self.page == Page.pages[0]:
                    button.disabled = True
                else:
                    button.disabled = False
                self.children[1].label = self.page.label
                self.children[1].emoji = self.page.emoji
                self.children[1].disabled = not self.page.can_buy
                self.children[1].style = self.page.style
                await interaction.response.edit_message(embed=self.page.embed, view=self)

            @discord.ui.button()
            async def purchase_pet_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                # Subtract cost from user balance
                if await user.check_balance("bits") >= self.page.cost:
                    await user.update_balance(-self.page.cost)
                else:
                    button.disabled = True
                    button.label = "Nope, sorry."
                    button.style = discord.ButtonStyle.red
                    button.emoji = "☹️"
                    for buttons in [self.children[0], self.children[1], self.children[2]]:
                        buttons.disabled = True
                    await interaction.response.edit_message(view=self)
                    return
                # Access list of pet names from 'petNames.txt'
                with open("petNames.txt", "r") as f:
                    lines = f.readlines()
                name = random.choice(lines).strip("\n")
                species = random.choice(list(pets[self.page.rarity]["animals"].keys()))
                pet = Pet(species, self.page.rarity, name)
                await ctx.bot.dbpets.update_many({"owner_id": user.user_id}, {"$set": {"active": False}})
                await ctx.bot.dbpets.insert_one(
                    {"owner_id": user.user_id, "name": pet.name, "rarity": pet.rarity,
                     "health": pet.health, "xp": 0, "level": 1,
                     "species": pet.species, "active": True})
                embed = discord.Embed(
                    title="Pet Purchased!",
                    description=f"You received {pet.name}, a {pet.species.replace('_', ' ').replace('face', '')}! "
                                f"Take good care of 'em!\n*To rename your pet, use the rename command*",
                    color=discord.Color.blue()
                )
                await interaction.response.edit_message(embed=embed, view=None)

            @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.blurple, custom_id="next")
            async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                if self.page == Page.pages[0]:
                    self.children[0].disabled = False
                self.next_page()
                if self.page.number == len(Page.pages):
                    button.disabled = True
                else:
                    button.disabled = False
                self.children[1].label = self.page.label
                self.children[1].emoji = self.page.emoji
                self.children[1].disabled = not self.page.can_buy
                self.children[1].style = self.page.style
                await interaction.response.edit_message(embed=self.page.embed, view=self)

            @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="close")
            async def close_button(self, interaction, button):
                if interaction.user != ctx.author:
                    return
                await message.delete()
                await ctx.message.delete()
                self.stop()

        message = await ctx.send(embed=Page.pages[0].embed, view=PetPaginatorButtons(Page.pages[0]))

    @registered()
    @own_pet()
    @commands.command(name="Pet", aliases=['pets', 'animals'], description="Check your pet and their stats.")
    async def pet(self, ctx):
        project_files = pathlib.Path.cwd() / 'projfiles'

        # Check if the user owns a pet, if they don't tell them where they can buy one
        pet_owned = await ctx.bot.dbpets.find_one({"owner_id": ctx.author.id})
        if not pet_owned:
            pet_not_owned_embed = discord.Embed(
                title="You do not own a pet!",
                description="Head over to -petshop to buy one today!",
                color=discord.Color.from_rgb(222, 245, 91)
            )
            await ctx.send(embed=pet_not_owned_embed)
            return
        active_pet = await ctx.bot.dbpets.find_one({"$and": [{"owner_id": ctx.author.id}, {"active": True}]})

        # Setting up embed
        active_pet_embed = discord.Embed(
            title=f"Active Pet: {active_pet['name']}",
            color=pets[active_pet['rarity']]['color']
        )
        # Adding pet sprite to pet menu
        #
        # file = discord.File(project_files / 'sprites' / f'{active_pet["species"]}_sprite.png',
        #                         filename=f'{active_pet["species"]}_sprite.png')
        # active_pet_embed.set_thumbnail(url=f'attachment://{active_pet["species"]}_sprite.png')
        active_pet_embed.add_field(name="Rarity", value=f"{active_pet['rarity'].replace('_', ' ')}")
        active_pet_embed.add_field(name="Species",
                                   value=f"{pets[active_pet['rarity']]['animals'][active_pet['species']]['emoji']}")
        active_pet_embed.add_field(name="Health",
                                   value=f"**{active_pet['health']}/{pets[active_pet['rarity']]['health']}**",
                                   inline=False)
        active_pet_embed.add_field(name="Level", value=f"{active_pet['level']}")

        class PetActionButtons(discord.ui.View):
            def __init__(self):
                super().__init__()

            @discord.ui.button(label="Switch Pet", style=discord.ButtonStyle.blurple)
            async def switch_button(self, switch_interaction: discord.Interaction, button: discord.ui.Button):
                if switch_interaction.user != ctx.author:
                    return

                users_pets = await ctx.bot.dbpets.find({"owner_id": ctx.author.id}).to_list(length=None)
                pet_options = {x["name"]: discord.SelectOption(label=f'{x["name"]}',
                                                               emoji=pets[x['rarity']]['animals'][x['species']][
                                                                   'emoji'],
                                                               value=x['name']) for x in users_pets}
                select_options = [x for x in pet_options.values()]

                class PetSwitcherMenu(discord.ui.View):
                    def __init__(self, *, timeout=180):
                        super().__init__(timeout=timeout)

                    @discord.ui.select(placeholder="Select a pet to switch to", options=select_options)
                    async def selection(self, interaction2: discord.Interaction, select: discord.ui.Select):
                        if interaction2.user != ctx.author:
                            return
                        # Set the old pet to inactive and the new one to active
                        await ctx.bot.dbpets.update_one({"$and": [{"owner_id": ctx.author.id}, {"active": True}]},
                                                        {"$set": {"active": False}})
                        await ctx.bot.dbpets.update_one(
                            {"$and": [{"owner_id": ctx.author.id}, {"name": select.values[0]}]},
                            {"$set": {"active": True}})
                        refreshed_pet = await ctx.bot.dbpets.find_one(
                            {"$and": [{"owner_id": ctx.author.id}, {"active": True}]})
                        refreshed_embed = discord.Embed(title=f"Active Pet: {select.values[0]}",
                                                        color=pets[refreshed_pet['rarity']]['color'])

                        # add necessary fields to refreshed embed
                        # refreshed_pet_file = discord.File(
                        #     project_files / 'sprites' / f'{refreshed_pet["species"]}_sprite.png',
                        #     filename=f'{refreshed_pet["species"]}_sprite.png')
                        # await pet_menu_message.add_files(refreshed_pet_file)
                        # refreshed_embed.set_thumbnail(url=f'attachment://{refreshed_pet["species"]}_sprite.png')
                        refreshed_embed.add_field(name="Rarity", value=f"{refreshed_pet['rarity'].replace('_', ' ')}")
                        refreshed_embed.add_field(name="Species",
                                                  value=f"{pets[refreshed_pet['rarity']]['animals'][refreshed_pet['species']]['emoji']}")
                        refreshed_embed.add_field(name="Health",
                                                  value=f"**{refreshed_pet['health']}/{pets[refreshed_pet['rarity']]['health']}**",
                                                  inline=False)
                        refreshed_embed.add_field(name="Level", value=f"{refreshed_pet['level']}")
                        await switch_interaction.delete_original_message()
                        await switch_interaction.message.edit(embed=refreshed_embed, view=PetActionButtons())

                await switch_interaction.response.send_message("Choose a pet to use as your active pet.",
                                                               view=PetSwitcherMenu())

            @discord.ui.button(label="Rename", style=discord.ButtonStyle.blurple)
            async def rename_button(self, interaction: discord.Interaction, button: discord.Button):
                # Class for renaming your pet
                class PetNameModal(discord.ui.Modal, title="New Pet Name"):
                    pet_name = discord.ui.TextInput(label="Name", placeholder="New pet name", min_length=2,
                                                    max_length=12)

                    def __init__(self, old_name):
                        super().__init__()
                        self.old_name = old_name

                    async def on_submit(self, interaction: discord.Interaction) -> None:
                        refreshed_pet = await ctx.bot.dbpets.find_one(
                            {"$and": [{"owner_id": ctx.author.id}, {"active": True}]})
                        refreshed_embed = discord.Embed(title=f"Active Pet: {self.pet_name}",
                                                        color=pets[active_pet['rarity']]['color'])

                        # add necessary fields to refreshed embed
                        # refreshed_embed.set_thumbnail(url=f'attachment://{refreshed_pet["species"]}_sprite.png')
                        refreshed_embed.add_field(name="Rarity", value=f"{refreshed_pet['rarity'].replace('_', ' ')}")
                        refreshed_embed.add_field(name="Species",
                                                  value=f"{pets[refreshed_pet['rarity']]['animals'][refreshed_pet['species']]['emoji']}")
                        refreshed_embed.add_field(name="Health",
                                                  value=f"**{refreshed_pet['health']}/{pets[refreshed_pet['rarity']]['health']}**", )
                        refreshed_embed.add_field(name="Level", value=f"{refreshed_pet['level']}")
                        await ctx.bot.dbpets.update_one(
                            {"$and": [{"owner_id": ctx.author.id}, {"name": self.old_name}]},
                            {"$set": {"name": str(self.pet_name)}})
                        await interaction.response.edit_message(embed=refreshed_embed, view=PetActionButtons())

                pet_to_rename = await ctx.bot.dbpets.find_one({"$and": [{"owner_id": ctx.author.id}, {"active": True}]})
                await interaction.response.send_modal(PetNameModal(pet_to_rename['name']))

            @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
            async def exit_button(self, interaction: discord.Interaction, button: discord.Button):
                if interaction.user != ctx.author:
                    return
                await pet_menu_message.delete()
                await ctx.message.delete()
                self.stop()

        pet_menu_message = await ctx.send(embed=active_pet_embed, view=PetActionButtons())


async def setup(bot):
    await bot.add_cog(PetsCog(bot))
