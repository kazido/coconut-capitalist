# import asyncio
# import discord
# import random

from discord.ext import commands

# from discord import app_commands, Interaction

# from cococap.user import User
# from utils.messages import Cembed
# from utils.menus import Menu, MenuHandler
# from cococap.item_models import Pets
# from cococap.constants import Rarities


class PetsCog(commands.Cog, name="Pets"):
    """Purchase, feed, and interact with pets!"""

    def __init__(self, bot):
        self.bot = bot


#     desc = """Pets are companions who you can name, level up, and interact with!\n
#         Different rarities have **higher** health and **better** findings.\n"""

#     shop_embed = Cembed(title="Welcome to the pet shop!", desc=desc, color=discord.Color.green())

#     embeds = {}

#     for pet in Pets.select():
#         pet: Pets
#         rarity = Rarities.from_value(pet.rarity)
#         embeds[pet.item_id] = Cembed(
#             title=pet.display_name,
#             description=f"Purchase a {pet.display_name}.\n" f"Cost: **{pet.price:,}** bits\n",
#             color=discord.Color.from_str(rarity.color),
#         )
#         embeds[pet].add_field(
#             name="Stats",
#             value=f"Max Level: **{pet.max_level:,}**\n",
#             inline=False,
#         )
#         embeds[pet].add_field(
#             name="Pet Perks",
#             value=f"Work: **+{pet.work_bonus:,}%** bits\n"
#             f"Daily: **+{pet.daily_bonus:,}** tokens",
#             inline=False,
#         )
#         embeds[pet].set_footer(text="These bonuses are in effect at the pets max level.")

#     def update_purchase_button_values(view, page, user):
#         page.__init__(page.embed, page.pet_rarity, user)
#         view.children[1].disabled = page.button_disabled
#         view.children[1].label = page.button_label
#         view.children[1].style = page.button_style
#         view.children[1].emoji = page.button_emoji

#     @app_commands.command(name="petshop", description="Purchase a pet for various bonuses!")
#     async def purchase_pet(self, interaction: discord.Interaction):
#         # Load the user
#         user = User(interaction.user.id)
#         await user.load()
#         PetsCog.Page(embed=embeds["common"], pet_rarity="common", user=user)
#         PetsCog.Page(embed=embeds["uncommon"], pet_rarity="uncommon", user=user)
#         PetsCog.Page(embed=embeds["rare"], pet_rarity="rare", user=user)
#         PetsCog.Page(embed=embeds["super_rare"], pet_rarity="super_rare", user=user)
#         PetsCog.Page(embed=embeds["legendary"], pet_rarity="legendary", user=user)
#         PetsCog.Page(embed=embeds["premium"], pet_rarity="premium", user=user)
#         await interaction.response.send_message(
#             embed=pet_shop_embed, view=PetsCog.PetShop(interaction.user, user)
#         )

#     class PetShop(discord.ui.View):
#         pages = []  # list of all pages in the Pet Shop

#         def __init__(self, shopper: discord.User, user: RequestUser):
#             super().__init__()
#             self.page_number = 1
#             self.discordUser = shopper
#             self.user = user
#             self.add_item(PetsCog.GotItButton())

#     class Page:
#         def __init__(self, embed: discord.Embed, pet_rarity, user: RequestUser):
#             user_can_buy = True if user.instance.money >= pets[pet_rarity]["cost"] else False
#             self.embed: discord.Embed = embed
#             self.pet_rarity = pet_rarity
#             self.pets_info: dict = pets[self.pet_rarity]
#             self.button_style = (
#                 discord.ButtonStyle.green if user_can_buy else discord.ButtonStyle.grey
#             )
#             self.button_emoji = "💰" if user_can_buy else None
#             self.button_label = "Purchase" if user_can_buy else "Can't afford"
#             self.button_disabled = not user_can_buy
#             PetsCog.PetShop.pages.append(self)

#     class NextPageButton(discord.ui.Button):
#         def __init__(self):
#             super().__init__(
#                 emoji=discord.PartialEmoji.from_str("<:right_arrow:1050633322813993000>"),
#                 style=discord.ButtonStyle.blurple,
#                 custom_id="next",
#             )

#         async def callback(self, next_page_interaction: discord.Interaction):
#             assert self.view is not None
#             view: PetsCog.PetShop = self.view
#             if next_page_interaction.user != view.discordUser:
#                 return
#             if view.page_number == len(view.pages):  # If we are on the last page, don't continue
#                 view.page_number = 1
#             else:
#                 view.page_number += 1
#             update_purchase_button_values(view, view.pages[view.page_number - 1], view.user)

#             await next_page_interaction.response.edit_message(
#                 embed=view.pages[view.page_number - 1].embed, view=view
#             )

#     class PreviousPageButton(discord.ui.Button):
#         def __init__(self):
#             super().__init__(
#                 emoji=discord.PartialEmoji.from_str("<:left_arrow:1050633298667389008>"),
#                 style=discord.ButtonStyle.blurple,
#                 custom_id="back",
#             )

#         async def callback(self, previous_page_interaction: discord.Interaction):
#             assert self.view is not None
#             view: PetsCog.PetShop = self.view
#             if previous_page_interaction.user != view.discordUser:
#                 return
#             if view.page_number == 1:  # If we are on the first page, don't continue
#                 view.page_number = len(view.pages)
#             else:
#                 view.page_number -= 1
#             update_purchase_button_values(view, view.pages[view.page_number - 1], view.user)
#             await previous_page_interaction.response.edit_message(
#                 embed=view.pages[view.page_number - 1].embed, view=view
#             )

#     class PurchasePetButton(discord.ui.Button):
#         def __init__(self, view):
#             page = view.pages[view.page_number - 1]
#             super().__init__(label="None", style=discord.ButtonStyle.grey)

#         async def callback(self, purchase_interaction: discord.Interaction):
#             assert self.view is not None
#             view: PetsCog.PetShop = self.view
#             page = view.pages[view.page_number - 1]
#             if purchase_interaction.user != view.discordUser:
#                 return
#             if view.user.instance.money < page.pets_info["cost"]:
#                 self.disabled = True
#                 self.label = "Nope, sorry."
#                 self.style = discord.ButtonStyle.red
#                 self.emoji = "☹️"
#                 for button in view.children:
#                     button.disabled = True
#                 await purchase_interaction.response.edit_message(view=view)
#                 await asyncio.sleep(1)
#                 await purchase_interaction.delete_original_response()
#                 return
#             with open(
#                 "projfiles/petNames.txt", "r"
#             ) as f:  # Access list of pet names from 'petNames.txt'
#                 lines = f.readlines()
#             name = random.choice(lines).strip("\n")
#             species = random.choice(list(page.pets_info["animals"].keys()))
#             query = mm.Pets.update(active=0).where(mm.Pets.owner_id == purchase_interaction.user.id)
#             query.execute()
#             query = mm.Pets.insert(
#                 active=1,
#                 health=page.pets_info["health"],
#                 species=species,
#                 name=name,
#                 owner_id=purchase_interaction.user.id,
#                 rarity=page.pet_rarity,
#                 level=1,
#                 xp=0,
#             )
#             query.execute()
#             view.user.update_balance(-page.pets_info["cost"])
#             embed = discord.Embed(
#                 title="Pet Purchased!",
#                 description=f"You received {name}, a {species}! " f"Take good care of 'em!",
#                 color=discord.Color.blue(),
#             )
#             await purchase_interaction.response.edit_message(embed=embed, view=None)

#     class CloseShopButton(discord.ui.Button):
#         def __init__(self):
#             super().__init__(label="Close", style=discord.ButtonStyle.red, custom_id="close")

#         async def callback(self, close_interaction: discord.Interaction):
#             assert self.view is not None
#             view: PetsCog.PetShop = self.view
#             if close_interaction.user != view.discordUser:
#                 return
#             closed_embed = discord.Embed(
#                 title="Thanks for shopping!",
#                 description="Come again soon!",
#                 colour=discord.Color.green(),
#             )
#             await close_interaction.response.edit_message(embed=closed_embed, view=None)
#             await asyncio.sleep(1)
#             await close_interaction.delete_original_response()

#     class GotItButton(discord.ui.Button):
#         def __init__(self):
#             super().__init__(label="Got It", emoji="✅", style=discord.ButtonStyle.green)

#         async def callback(self, got_it_interaction: discord.Interaction):
#             assert self.view is not None
#             view: PetsCog.PetShop = self.view
#             if got_it_interaction.user != view.discordUser:
#                 return
#             buttons = [
#                 PetsCog.PreviousPageButton(),
#                 PetsCog.PurchasePetButton(self.view),
#                 PetsCog.NextPageButton(),
#                 PetsCog.CloseShopButton(),
#             ]
#             for button in buttons:
#                 view.add_item(button)
#             view.remove_item(view.children[0])
#             update_purchase_button_values(view, view.pages[view.page_number - 1], view.user)
#             await got_it_interaction.response.edit_message(embed=embeds["common"], view=view)


# @commands.command(name="Pet", aliases=["pets", "animals"])
# async def pet(self, interaction: Interaction):
#     """Check your pet and their stats."""
#     # Check if the user owns a pet, if they don't tell them where they can buy one
#     user = User(interaction.user.id)
#     await user.load()

#     active_pet, pet_data = user.get_active_pet()
#     rarity = Rarities.from_value(pet_data.rarity)
#     if not active_pet:
#         no_embed = discord.Embed(
#             title="You do not own a pet!",
#             description="Head over to /petshop to buy one today!",
#             color=discord.Color.from_str("0xdef55b"),
#         )
#         return await interaction.response.send_message(embed=no_embed)

#     # Setting up embed
#     pet_embed = discord.Embed(
#         title=f"Active Pet: {active_pet['name']}", color=Pets.get_by_id(rarity.color)
#     )
#     pet_embed.add_field(name="Rarity", value=f"{rarity.name}")
#     pet_embed.add_field(name="Species", value=f"{pet_data.emoji}")
#     pet_embed.add_field(name="Level", value=f"{active_pet['level']}")
#     pet_embed.add_field(name="XP", value=f"{active_pet['xp']}")

#     class PetActionButtons(discord.ui.View):
#         def __init__(self):
#             super().__init__()

#         @discord.ui.button(label="Switch Pet", style=discord.ButtonStyle.blurple)
#         async def switch_button(self, switch_interaction: Interaction, button: discord.ui.Button):
#             if switch_interaction.user != interaction.user:
#                 return

#             users_pets = user.get_field("pets")
#             pet_options = {
#                 x["name"]: discord.SelectOption(
#                     label=f'{x["name"]}', emoji=Pets.get_by_id(x["pet_id"]).emoji, value=x["pet_id"]
#                 )
#                 for x in users_pets
#             }
#             select_options = [x for x in pet_options.values()]

#             class PetSwitcherMenu(discord.ui.View):
#                 def __init__(self):
#                     super().__init__()

#                 @discord.ui.select(placeholder="Select a pet to switch to", options=select_options)
#                 async def selection(self, s_interaction: Interaction, select: discord.ui.Select):
#                     if s_interaction.user != interaction.user:
#                         return
#                     # Set the old pet to inactive and the new one to active
#                     users_pets["active"] = users_pets[select.values[0]]
#                     refreshed_embed = discord.Embed(
#                         title=f"Active Pet: {select.values[0]}",
#                         color=pets[refreshed_pet["rarity"]]["color"],
#                     )

#                     # add necessary fields to refreshed embed
#                     # refreshed_pet_file = discord.File(
#                     #     project_files / 'sprites' / f'{refreshed_pet["species"]}_sprite.png',
#                     #     filename=f'{refreshed_pet["species"]}_sprite.png')
#                     # await pet_menu_message.add_files(refreshed_pet_file)
#                     # refreshed_embed.set_thumbnail(url=f'attachment://{refreshed_pet["species"]}_sprite.png')
#                     refreshed_embed.add_field(
#                         name="Rarity", value=f"{refreshed_pet['rarity'].replace('_', ' ')}"
#                     )
#                     refreshed_embed.add_field(
#                         name="Species",
#                         value=f"{pets[refreshed_pet['rarity']]['animals'][refreshed_pet['species']]['emoji']}",
#                     )
#                     refreshed_embed.add_field(
#                         name="Health",
#                         value=f"**{refreshed_pet['health']}/{pets[refreshed_pet['rarity']]['health']}**",
#                         inline=False,
#                     )
#                     refreshed_embed.add_field(name="Level", value=f"{refreshed_pet['level']}")
#                     await switch_interaction.delete_original_message()
#                     await switch_interaction.message.edit(
#                         embed=refreshed_embed, view=PetActionButtons()
#                     )

#             await switch_interaction.response.send_message(
#                 "Choose a pet to use as your active pet.", view=PetSwitcherMenu()
#             )

#         @discord.ui.button(label="Rename", style=discord.ButtonStyle.blurple)
#         async def rename_button(self, interaction: discord.Interaction, button: discord.Button):
#             # Class for renaming your pet
#             class PetNameModal(discord.ui.Modal, title="New Pet Name"):
#                 pet_name = discord.ui.TextInput(
#                     label="Name", placeholder="New pet name", min_length=2, max_length=12
#                 )

#                 def __init__(self, old_name):
#                     super().__init__()
#                     self.old_name = old_name

#                 async def on_submit(self, interaction: discord.Interaction) -> None:
#                     refreshed_pet = await ctx.bot.dbpets.find_one(
#                         {"$and": [{"owner_id": ctx.author.id}, {"active": True}]}
#                     )
#                     refreshed_embed = discord.Embed(
#                         title=f"Active Pet: {self.pet_name}",
#                         color=pets[active_pet["rarity"]]["color"],
#                     )

#                     # add necessary fields to refreshed embed
#                     # refreshed_embed.set_thumbnail(url=f'attachment://{refreshed_pet["species"]}_sprite.png')
#                     refreshed_embed.add_field(
#                         name="Rarity", value=f"{refreshed_pet['rarity'].replace('_', ' ')}"
#                     )
#                     refreshed_embed.add_field(
#                         name="Species",
#                         value=f"{pets[refreshed_pet['rarity']]['animals'][refreshed_pet['species']]['emoji']}",
#                     )
#                     refreshed_embed.add_field(
#                         name="Health",
#                         value=f"**{refreshed_pet['health']}/{pets[refreshed_pet['rarity']]['health']}**",
#                     )
#                     refreshed_embed.add_field(name="Level", value=f"{refreshed_pet['level']}")
#                     await ctx.bot.dbpets.update_one(
#                         {"$and": [{"owner_id": ctx.author.id}, {"name": self.old_name}]},
#                         {"$set": {"name": str(self.pet_name)}},
#                     )
#                     await interaction.response.edit_message(
#                         embed=refreshed_embed, view=PetActionButtons()
#                     )

#             pet_to_rename = await ctx.bot.dbpets.find_one(
#                 {"$and": [{"owner_id": ctx.author.id}, {"active": True}]}
#             )
#             await interaction.response.send_modal(PetNameModal(pet_to_rename["name"]))

#         @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
#         async def exit_button(self, interaction: discord.Interaction, button: discord.Button):
#             if interaction.user != ctx.author:
#                 return
#             await pet_menu_message.delete()
#             await ctx.message.delete()
#             self.stop()

#     pet_menu_message = await ctx.send(embed=pet_embed, view=PetActionButtons())


async def setup(bot):
    await bot.add_cog(PetsCog(bot))
