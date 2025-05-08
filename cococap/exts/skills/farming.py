# import discord
from discord.ext import commands, tasks

# from discord import app_commands

# from random import randint
# from cococap.user import User
# from cococap.item_models import Master, Crops
# from cococap.models import UserCollection
# from cococap.constants import DiscordGuilds, IMAGES_REPO
# from utils.custom_embeds import Cembed
# from utils.items.items import get_items_from_db


class FarmingCog(commands.Cog, name="Farming"):
    """Special farming cog, allows users to farm for coconuts on plots of land"""

    def __init__(self, bot):
        self.bot = bot


#     async def cog_load(self) -> None:
#         self.farm_task.start()

#     async def cog_unload(self) -> None:
#         self.farm_task.stop()

#     # get the possible drops for farming
#     farming_items = get_items_from_db("farming")

#     # emojis for farming
#     rain_gods_blessing = ":raindrop:"   # REPLACE WITH CUSTOM
#     land_deed = ":ticket:"              # REPLACE WITH CUSTOM
#     empty_plot = ":brown_square:"       # REPLACE WITH CUSTOM

#     farm_plots = [f"plot{i}" for i in range(1, 10)]

#     @tasks.loop(minutes=60)
#     # Checks everyone's ungrown crops and has a chance to grow them
#     async def farm_task(self):
#         query = {
#             "$or": [
#                 {"farming.plot1.crop_id": {"$not": None}},
#                 {"farming.plot2.crop_id": {"$not": None}},
#                 {"farming.plot3.crop_id": {"$not": None}},
#                 {"farming.plot4.crop_id": {"$not": None}},
#                 {"farming.plot5.crop_id": {"$not": None}},
#                 {"farming.plot6.crop_id": {"$not": None}},
#                 {"farming.plot7.crop_id": {"$not": None}},
#                 {"farming.plot8.crop_id": {"$not": None}},
#                 {"farming.plot9.crop_id": {"$not": None}},
#             ]
#         }
#         # for user in UserCollection.find_many(query):
#         #     plots = [user["farming"][plot] for plot in FarmingCog.farm_plots]
#         #     for index, plot in enumerate(plots):
#         #         user_plot = FarmingCog.Plot(plot=plot, num = index+1)
#         #         if user_plot.is_seed():
#         #             if user_plot.grow() == -1:
#         #                 users_farm_dict[f"plot{index+1}"] = grown_crop
#         #                 guild = self.bot.get_guild(856915776345866240)
#         #                 user_in_discord = discord.utils.get(guild.members, id=int(farm.id.id))
#         #                 lucky_farmers.append(user_in_discord.mention)
#         #     farm = phs.dict_to_model(mm.Farms, users_farm_dict)
#         #     farm.save()

#         # Guild to send the farm updates in
#         guild = self.bot.get_guild(856915776345866240)
#         channel = guild.get_channel(966990507689533490)
#         rain_events = [
#             "The rains pour down onto the fields...",
#             "The sun provides ample growth today!",
#             "The winds pass and bring an air of good harvest.",
#             "There's no better time of day to harvest than now!",
#             "It's harvest o'clock somewhere...",
#             "Does the rain ever get tired of providing for these crops?",
#             "Big rain storm approaching!",
#         ]
#         lucky_farmers = list(set(lucky_farmers))
#         if len(lucky_farmers) != 0:
#             await channel.send(
#                 f"*{random.choice(rain_events)}*\nThe lucky farmers are: **{', '.join(lucky_farmers)}**"
#             )

#     async def harvest(info, button: discord.ui.Button, user: User):
#         # roll how many crops should be harvested
#         amount = randint(info["crop"].min_drop, info["crop"].max_drop)
#         items = user.get_field("items")
#         await user.create_item()
#         await user.save()

#         button.disabled = True
#         button.style = discord.ButtonStyle.grey
#         button.label = "Empty!"
#         return amount

#     class Plot:
#         def __init__(self, plot: dict, num: int) -> None:
#             self.plot_number = num
#             if not plot["crop_id"]:
#                 self.item = None
#                 return
#             self.item: Master = Master.get_by_id(plot["crop_id"])
#             self.current_cycle = plot["cycle"]
#             self.imbued = plot["imbued"]
#             # Get the number of cycles we need if it's a crop
#             if self.get_type() == "CROP":
#                 self.cycles: int = Crops.get_by_id(plot["crop_id"]).cycles

#         def is_empty(self):
#             return self.item == None

#         def grow(self):
#             assert not self.is_empty() and self.is_seed()
#             self.current_cycle += 1
#             if self.imbued:
#                 self.current_cycle += 1
#             if self.current_cycle >= self.cycles:
#                 # The crop has grown
#                 # TODO: Switch the
#                 self.item = None
#                 return -1
#             return self.current_cycle

#         def get_type(self):
#             if self.is_empty():
#                 return None
#             return self.item.filter_type

#         def harvest(self):
#             assert self.is_crop()
#             amount = randint(self.item.min_drop, self.item.max_drop)
#             return amount

#         def field_name(self):
#             return f"Plot {self.plot_number} 🌳"

#         def field_value(self):
#             value = "Empty!"
#             if not self.is_empty():
#                 value = ""
#                 ratio = self.current_cycle / self.cycles
#                 plot_size = 5
#                 for _ in range(int(ratio * plot_size)):
#                     value += self.item.emoji or "5"
#                 for _ in range(plot_size - int(ratio * plot_size)):
#                     value += FarmingCog.empty_plot or "0"
#                 return value
#             return self.content

#     class Farm(discord.ui.View):
#         def __init__(self, user: User, interaction: discord.Interaction):
#             super().__init__()
#             self.user = user
#             self.farming = user.get_field("farming")

#             self.embed = Cembed(
#                 title="Your farm",
#                 color=discord.Color.from_str("0xe8cd22"),
#                 interaction=interaction,
#                 activity="farming",
#             )

#             # Get a list of all the plots a user has
#             for plot in FarmingCog.farm_plots:
#                 if self.farming[plot]:
#                     user_plot = FarmingCog.Plot(self.farming[plot])
#                     self.embed.add_field(name=user_plot.field_name(), value=user_plot.field_value())
#                     label = "Empty!"
#                     style = discord.ButtonStyle.gray
#                     disabled = True
#                     if user_plot.is_crop():
#                         label = "Harvest!"
#                         style = discord.ButtonStyle.green
#                         disabled = False
#                     elif user_plot.is_seed():
#                         label = "Growing"
#                     self.add_item(
#                         FarmingCog.HarvestButton(label=label, style=style, disabled=disabled)
#                     )

#             # Add a nice footer!
#             self.embed.set_footer(text="Crops have a chance to grow every hour.")

#             self.add_item(ExitButton())
#             self.add_item(SwitchToBarnButton())
#             self.add_item(SwitchToPlantButton())

#         async def on_timeout(self) -> None:
#             self.farming["is_farming"] = False
#             await self.user.save()
#             try:
#                 await interaction.delete_original_response()
#             except discord.errors.NotFound:
#                 pass

#     class HarvestButton(discord.ui.Button):
#         def __init__(self, label, style, disabled):
#             super().__init__(label=label, style=style, disabled=disabled)

#         async def callback(self, harvest_interacton: discord.Interaction):
#             if harvest_interacton.user != interaction.user:
#                 return
#             harvested_crops = harvest(self.button_dict, self, interaction.user)
#             self.view.farm_module_embed.set_field_at(
#                 self.button_no, name=f"Plot {self.button_no + 1}", value=f"+{harvested_crops}"
#             )
#             users_farm_dict[f"plot{self.button_no+1}"] = "Empty!"
#             button_info = button_refresh(user_farm_dict=users_farm_dict)
#             users_farm = phs.dict_to_model(mm.Farms, users_farm_dict)
#             users_farm.save()
#             await harvest_interacton.response.edit_message(
#                 embed=self.view.farm_module_embed, view=self.view
#             )

#     class ExitButton(discord.ui.Button):
#         def __init__(self, row=1):
#             super().__init__(label="Exit", style=discord.ButtonStyle.red, row=row)

#         async def callback(self, exit_interaction: discord.Interaction):
#             if exit_interaction.user != interaction.user:
#                 return
#             users_farm.has_open_farm = False
#             users_farm.save()
#             await interaction.delete_original_response()
#             self.view.stop()

#     class Barn(discord.ui.View):
#         def __init__(self, timeout=20):
#             super().__init__(timeout=timeout)
#             self.barn_embed = discord.Embed(
#                 title=f"Welcome to the Barn!",
#                 description="Here is *your* inventory of crops and seeds. Happy farming!",
#                 color=0x8C6803,
#             )
#             self.barn_embed.set_author(
#                 name=f"{interaction.user.name} - In the Barn",
#                 icon_url=interaction.user.display_avatar,
#             )
#             for key, value in consumables["CROPS"].items():
#                 crop_quantity = 0
#                 seeds_quantity = 0
#                 crop = mm.Items.get_or_none(
#                     mm.Items.owner_id == interaction.user.id, mm.Items.reference_id == key
#                 )
#                 if crop:
#                     crop_quantity = crop.quantity
#                 seed = mm.Items.get_or_none(
#                     mm.Items.owner_id == interaction.user.id,
#                     mm.Items.reference_id == value["grows_from"],
#                 )
#                 if seed:
#                     seeds_quantity = seed.quantity
#                 # self.barn_embed.description += f"\n{value['emoji']} \u200b **{crop_quantity:,}** {value['name']}s \
#                 #     :seedling: \u200b **{seeds_quantity:,}** seeds"
#                 self.barn_embed.add_field(
#                     name=f"{value['name'].capitalize()}",
#                     value=f"{value['emoji']} \u200b **{crop_quantity:,}** {value['name']}s "
#                     f":seedling: \u200b **{seeds_quantity:,}** seeds",
#                     inline=False,
#                 )
#             self.add_item(ExitButton(0))
#             self.add_item(SwitchToFarmButton(0))
#             self.add_item(SwitchToPlantButton(0))

#         async def on_timeout(self) -> None:
#             users_farm.has_open_farm = False
#             users_farm.save()
#             try:
#                 await interaction.delete_original_response()
#             except discord.errors.NotFound:
#                 pass

#     class Plant(discord.ui.View):
#         def __init__(self, timeout=20):
#             super().__init__(timeout=timeout)
#             self.plant_embed = discord.Embed(
#                 title=f"Plant crops to sell or to feed your pets",
#                 description=f"You can plant various kinds of crops \
#                     which you can *sell* for a **profit** or *feed* to your **pets**.",
#                 color=0x8DB046,
#             )
#             self.plant_embed.set_author(
#                 name=f"{interaction.user.name} - Planting", icon_url=interaction.user.display_avatar
#             )
#             user_plots = [users_farm_dict[x] for x in mm.Farms.plots]
#             plots_full = 0
#             for index, plot in enumerate(user_plots):
#                 if plot != "Empty!":
#                     self.plant_embed.add_field(
#                         name=f"Plot {index+1} 🌳",
#                         value=f"{consumables[plot[0:4]+'S'][plot]['name']}",
#                     )
#                     plots_full += 1
#                 else:
#                     self.plant_embed.add_field(name=f"Plot {index+1} 🌳", value=f"Empty!")

#             if plots_full == len(user_plots):
#                 self.add_item(PlantButton(discord.ButtonStyle.grey, True, label="Plots full!"))
#             else:
#                 for key in consumables["SEEDS"].keys():
#                     seeds_quantity = 0
#                     seeds = mm.Items.get_or_none(
#                         mm.Items.owner_id == interaction.user.id, mm.Items.reference_id == key
#                     )
#                     if seeds:
#                         seeds_quantity = seeds.quantity
#                     if seeds_quantity == 0:
#                         self.add_item(PlantButton(discord.ButtonStyle.grey, True, label="No seeds"))
#                     else:
#                         self.add_item(
#                             PlantButton(discord.ButtonStyle.blurple, False, seed_ref_id=key)
#                         )

#             self.add_item(ExitButton())
#             self.add_item(SwitchToBarnButton())
#             self.add_item(SwitchToFarmButton())

#         async def on_timeout(self) -> None:
#             users_farm.has_open_farm = False
#             users_farm.save()
#             try:
#                 await interaction.delete_original_response()
#             except discord.errors.NotFound:
#                 pass

#     class PlantButton(discord.ui.Button):
#         def __init__(self, button_style, button_disabled, seed_ref_id=None, label: str = None):
#             self.button_style = button_style
#             self.button_disabled = button_disabled
#             self.seed_ref_id = seed_ref_id
#             if label:
#                 button_label = label
#             else:
#                 button_label = consumables["SEEDS"][self.seed_ref_id]["name"]
#             super().__init__(
#                 label=button_label, style=self.button_style, disabled=self.button_disabled
#             )

#         async def callback(self, plant_interaction: discord.Interaction):
#             if plant_interaction.user != interaction.user:
#                 return
#             seeds = mm.Items.get(
#                 mm.Items.owner_id == interaction.user.id, mm.Items.reference_id == self.seed_ref_id
#             )
#             seeds.quantity -= 1
#             seeds.save()
#             if seeds.quantity == 0:
#                 self.disabled = True
#                 self.style = discord.ButtonStyle.grey
#                 self.label = "No seeds"
#             user_plots = [users_farm_dict[x] for x in mm.Farms.plots]
#             for index, plot in enumerate(user_plots):
#                 if plot == "Empty!":
#                     self.view.plant_embed.set_field_at(
#                         index=index,
#                         name="PLANTED!",
#                         value=f"{consumables['SEEDS'][self.seed_ref_id]['name']}",
#                     )
#                     users_farm_dict[f"plot{index+1}"] = self.seed_ref_id
#                     users_farm = phs.dict_to_model(mm.Farms, users_farm_dict)
#                     users_farm.save()
#                     break
#             else:
#                 for button in self.view.children:
#                     if button.row == 1:
#                         button.disabled = False
#                     else:
#                         button.disabled = True
#             self.view.__init__()
#             await plant_interaction.response.edit_message(
#                 embed=self.view.plant_embed, view=self.view
#             )

#     class SwitchToBarnButton(discord.ui.Button):
#         def __init__(self, row=1):
#             super().__init__(label="Barn", style=discord.ButtonStyle.blurple, row=row)

#         async def callback(self, switch_to_barn_interaction: discord.Interaction):
#             if switch_to_barn_interaction.user != interaction.user:
#                 return
#             self.view.stop()
#             await switch_to_barn_interaction.response.edit_message(
#                 embed=Barn().barn_embed, view=Barn()
#             )

#     class SwitchToPlantButton(discord.ui.Button):
#         def __init__(self, row=1):
#             super().__init__(label="Plant", style=discord.ButtonStyle.blurple, row=row)

#         async def callback(self, switch_to_plant_interaction: discord.Interaction):
#             if switch_to_plant_interaction.user != interaction.user:
#                 return
#             self.view.stop()
#             await switch_to_plant_interaction.response.edit_message(
#                 embed=Plant().plant_embed, view=Plant()
#             )

#     class SwitchToFarmButton(discord.ui.Button):
#         def __init__(self, row=1):
#             super().__init__(label="Farm", style=discord.ButtonStyle.blurple, row=row)

#         async def callback(self, s_interaction: discord.Interaction):
#             if s_interaction.user != interaction.user:
#                 return
#             self.view.stop()
#             await s_interaction.response.edit_message(embed=Farm().farm_module_embed, view=Farm())

#     @app_commands.command(name="farm")
#     async def farm(self, interaction: discord.Interaction):
#         """Grow crops to feed your pets and make some money."""
#         # Load the user
#         user = User(interaction.user.id)
#         await user.load()

#         # Get farming data
#         farming = user.get_field("farming")
#         items = user.get_field("items")
#         xp = farming["xp"]
#         level = user.xp_to_level(xp)

#         embed = Cembed(
#             title=f"You are: `Level {level}`",
#             color=discord.Color.from_str("0xe8cd22"),
#             interaction=interaction,
#             activity="farming",
#         )
#         # TODO: Make emojis for rain god's blessings, land deeds
#         balances = ""
#         farming_items = ["rain_gods_blessing", "land_deed"]
#         for item in farming_items:
#             emoji = getattr(FarmingCog, item)
#             name = FarmingCog.farming_items[item].display_name
#             balances += f"{emoji} **{name}**: "
#             try:
#                 item_quantity = items[item]["quantity"]
#                 balances += f"{item_quantity:,}\n"
#             except KeyError:
#                 balances += "0\n"
#         embed.add_field(
#             name="Balances",
#             value=balances,
#         )
#         embed.add_field(
#             name="Crops Grown", value=f":corn: **{farming['crops_grown']:,}** crops", inline=False
#         )

#         # Ugliest line of code you'll ever see xD
#         embed.set_thumbnail(url=f"{IMAGES_REPO}/skills/farming.png")

#         if farming["equipped_tool"]:
#             tool_data = Master.get_by_id(farming["equipped_tool"])

#         # If the user already has an open farm
#         if farming["is_farming"]:
#             embed = Cembed(
#                 title="You already have an open farming module!",
#                 desc="Please close the farming module!",
#                 color=discord.Color.red(),
#                 interaction=interaction,
#                 activity="farming",
#             )
#             return await interaction.response.send_message(embed=embed, ephemeral=True)

#         # farming["is_farming"] = True
#         # await user.save()

#         await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(FarmingCog(bot))
