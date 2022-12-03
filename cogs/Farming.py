import asyncio
import discord  # Discord imports
from discord.ext import commands, tasks
from discord import app_commands
import random  # Random imports
from random import randint
from classLibrary import RequestUser, crops  # File imports
from cogs.ErrorHandler import registered
from utils import seconds_until_tasks
import myModels as mm


def growth_roll(crop_type):
    growth_range = range(crops[crop_type + 's']['growth_odds'][0], crops[crop_type + 's']['growth_odds'][1])
    roll = randint(0, 100)
    if roll in growth_range:  # If the roll is in the range for the crop to grow
        return True  # Set function as true, the crop grew
    else:
        return False  # The crop didn't grow


def plot_button_refresh(plots_to_setup):
    """For every plot, if its empty, button style is grey,
    if its not, button style is green! Use this to refesh the
    style of the button upon click OR to setup the button."""
    plot_info = {
        0: {
            "label": "Empty!",
            "disabled": True,
            "style": discord.ButtonStyle.grey,
            "crop": None
        },
        1: {
            "label": "Empty!",
            "disabled": True,
            "style": discord.ButtonStyle.grey,
            "crop": None
        },
        2: {
            "label": "Empty!",
            "disabled": True,
            "style": discord.ButtonStyle.grey,
            "crop": None
        }}
    grown_crops = [plant for plant in crops.keys()]
    seeds = [plant + ' seeds' for plant in crops.keys()]
    for index, content in enumerate(plots_to_setup):
        if content in seeds:
            plot_info[index]['label'] = "Growing"
        elif content in grown_crops:
            plot_info[index]['style'] = discord.ButtonStyle.green
            plot_info[index]['label'] = "Harvest!"
            plot_info[index]['disabled'] = False
            plot_info[index]['crop'] = content
    return plot_info


def harvest(button_number, button, users_farm):
    harvested_crops = None
    if button_number['crop'] == "almonds":
        harvested_crops = randint(3, 20)
    elif button_number['crop'] == "coconuts":
        harvested_crops = randint(2, 3)
    elif button_number['crop'] == "chocolates":
        harvested_crops = randint(1, 2)
    setattr(users_farm, button_number['crop'], getattr(users_farm, button_number['crop']) + harvested_crops)
    users_farm.save()
    button.disabled = True
    button.style = discord.ButtonStyle.grey
    button.label = "Empty"
    return harvested_crops


class FarmingCog(commands.Cog, name="Farming"):
    """Special farming cog, allows users to farm for coconuts on plots of land"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree
        self.farm_task.start()

    @tasks.loop(minutes=60)
    async def farm_task(self):
        lucky_farmers = []
        plots = mm.Farms.select()
        for farm in plots.objects():
            for index, plot in enumerate([farm.plot1, farm.plot2, farm.plot3]):
                if plot.endswith(' seeds'):
                    grown = growth_roll(plot[:len(plot) - 6])
                    grown_crop = plot[:len(plot) - 6] + 's'
                    if grown:  # Applies growth role based on crop without "seeds" at the end, checks if grown
                        if index == 0:
                            farm.plot1 = grown_crop
                        elif index == 1:
                            farm.plot2 = grown_crop
                        elif index == 2:
                            farm.plot3 = grown_crop
                        lucky_farmers.append(farm.id.name)
            farm.save()
        guild = self.bot.get_guild(856915776345866240)  # Guild to send the farm updates in
        channel = guild.get_channel(966990507689533490)
        rain_events = ["The rains pour down onto the fields...", "The sun provides ample growth today!",
                       "The winds pass and bring an air of good harvest.",
                       "There's no better time of day to harvest than now!", "It's harvest o'clock somewhere...",
                       "Does the rain ever get tired of providing for these crops?", "Big rain storm approaching!"]
        lucky_farmers = list(set(lucky_farmers))
        if len(lucky_farmers) != 0:
            await channel.send(f"*{random.choice(rain_events)}*\nThe lucky farmers are: **{', '.join(lucky_farmers)}**")

    @farm_task.before_loop  # Waits until the half or 0 of the hour
    async def before_farm_task(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(seconds_until_tasks())

    @registered()
    @app_commands.guilds(977351545966432306, 856915776345866240)
    @app_commands.command(name="farm", description="grow crops to feed your pets")
    async def farm(self, interaction: discord.Interaction):
        users_farm = mm.Farms.get(id=interaction.user.id)
        if users_farm.has_open_farm:  # If the user already has an open farm

            farm_already_open_embed = discord.Embed(
                title="You already have an open farming module!",
                description="Please close the farming module, or wait 20 seconds",
                color=discord.Color.red())

            await interaction.response.send_message(embed=farm_already_open_embed)
            await asyncio.sleep(5)
            await interaction.delete_original_response()
            return
        users_farm.has_open_farm = True  # so users cannot double harvest crops
        users_farm.save()

        class Farm(discord.ui.View):
            def __init__(self, *, timeout=20):
                super().__init__(timeout=timeout)
                self.farm_module_embed = discord.Embed(
                    title=f"Welcome to the Farm!",
                    description="Collect seeds and plant them in your plots!",
                    color=0xdaebb0)
                self.farm_module_embed.set_author(name=f"{interaction.user.name} - Farming",
                                                  icon_url=interaction.user.display_avatar)

                plots = [users_farm.plot1, users_farm.plot2, users_farm.plot3]
                for count, crop in enumerate(plots):
                    if crop == "coconuts":
                        plot_contents = ":coconut:"
                    elif crop == "almonds":
                        plot_contents = ":chestnut:"
                    elif crop == "chocolates":
                        plot_contents = ":chocolate_bar:"
                    else:
                        plot_contents = crop
                    self.farm_module_embed.add_field(name=f"Plot {count + 1} 🌳", value=plot_contents)
                self.farm_module_embed.set_footer(text="Crops have a chance to grow every hour.")
                plot_button_info = plot_button_refresh(plots)
                for number, plot in enumerate(plot_button_info):
                    self.add_item(HarvestButton(plot_button_info[plot]['label'],
                                                plot_button_info[plot]['style'],
                                                plot_button_info[plot]['disabled'],
                                                plot_button_info[plot], number))
                self.add_item(ExitButton())
                self.add_item(SwitchToBarnButton())
                self.add_item(SwitchToPlantButton())

            async def on_timeout(self) -> None:
                users_farm.has_open_farm = False
                users_farm.save()
                try:
                    await interaction.delete_original_response()
                except discord.errors.NotFound:
                    pass

        class HarvestButton(discord.ui.Button):
            def __init__(self, label, style, disabled, button_dict, button_no):
                self.button_label = label
                self.button_style = style
                self.button_disabled = disabled
                self.button_dict = button_dict
                self.button_no = button_no
                super().__init__(label=self.button_label, style=self.button_style, disabled=self.button_disabled)

            async def callback(self, harvest_interacton: discord.Interaction):
                if harvest_interacton.user != interaction.user:
                    return
                harvested_crops = harvest(self.button_dict, self, users_farm)
                self.view.farm_module_embed.set_field_at(self.button_no, name=f'Plot {self.button_no + 1}',
                                                         value=f"+{harvested_crops}")
                plots = [users_farm.plot1, users_farm.plot2, users_farm.plot3]
                if self.button_no == 0:
                    users_farm.plot1 = 'Empty!'
                elif self.button_no == 1:
                    users_farm.plot2 = 'Empty!'
                elif self.button_no == 2:
                    users_farm.plot3 = 'Empty!'
                plot_button_refresh(plots)
                users_farm.save()
                await harvest_interacton.response.edit_message(embed=self.view.farm_module_embed, view=self.view)

        class ExitButton(discord.ui.Button):
            def __init__(self, row=1):
                super().__init__(label="Exit", style=discord.ButtonStyle.red, row=row)

            async def callback(self, exit_interaction: discord.Interaction):
                if exit_interaction.user != interaction.user:
                    return
                users_farm.has_open_farm = False
                users_farm.save()
                await interaction.delete_original_response()
                self.view.stop()

        class Barn(discord.ui.View):
            def __init__(self):
                super().__init__()
                users_barn = mm.Farms.get(id=interaction.user.id)
                self.barn_embed = discord.Embed(
                    title=f"Welcome to the Barn!",
                    description="Here is *your* inventory of crops and seeds. Happy farming!",
                    color=0x8c6803)
                self.barn_embed.set_author(name=f"{interaction.user.name} - In the Barn",
                                           icon_url=interaction.user.display_avatar)
                barn_crops = []
                for crop in crops:
                    barn_crops.append(crop)
                barn = {"coconuts": {"emoji": ":coconut:",
                                     "count": users_barn.coconuts},
                        "chocolates": {"emoji": ":chocolate_bar:",
                                       "count": users_barn.chocolates},
                        "almonds": {"emoji": ":chestnut:",
                                    "count": users_barn.almonds},
                        "coconut seeds": {
                            "count": users_barn.coconuts_seeds
                        },
                        "chocolate seeds": {
                            "count": users_barn.chocolates_seeds
                        },
                        "almond seeds": {
                            "count": users_barn.almonds_seeds
                        }
                        }
                for crop in barn_crops:
                    self.barn_embed.add_field(name=f"{crop.capitalize()}",
                                              value=f"{barn[crop]['emoji']} \u200b **{barn[crop]['count']:,}**\n"
                                                    f":seedling: \u200b **{barn[crop[:-1] + ' seeds']['count']:,}** seeds",
                                              inline=True)
                if interaction.user.is_on_mobile():
                    self.barn_embed = discord.Embed(
                        title=f"{interaction.user.name}'s Barn",
                        description="Here is your inventory of crops and seeds. Happy farming!",
                        color=0x8c6803
                    )
                    self.barn_embed.add_field(name="Almonds", value=f"`{barn['almonds']['count']}`\n"
                                                                    f"*`({barn['almond seeds']['count']} seeds)`*")
                    self.barn_embed.add_field(name="Coconuts", value=f"`{barn['coconuts']['count']}`\n"
                                                                     f"*`({barn['coconut seeds']['count']} seeds)`*")
                    self.barn_embed.add_field(name="Cacaos", value=f"`{barn['chocolates']['count']}`\n"
                                                                   f"*`({barn['chocolate seeds']['count']} seeds)`*")
                self.add_item(ExitButton(0))
                self.add_item(SwitchToFarmButton(0))
                self.add_item(SwitchToPlantButton(0))

            async def on_timeout(self) -> None:
                users_farm.has_open_farm = False
                users_farm.save()
                try:
                    await interaction.delete_original_response()
                except discord.errors.NotFound:
                    pass

        class Plant(discord.ui.View):
            def __init__(self):
                super().__init__()
                names = []
                for crop in crops.keys():
                    names.append(crop)
                self.plant_embed = discord.Embed(
                    title=f"Plant crops to feed your pets",
                    description=f"You can plant various kinds of crops:\n{', '.join(names)}",
                    color=0x8db046
                )
                self.plant_embed.set_author(name=f"{interaction.user.name} - Planting",
                                            icon_url=interaction.user.display_avatar)
                seeds = [users_farm.almonds_seeds, users_farm.coconuts_seeds, users_farm.chocolates_seeds]
                if (users_farm.plot1 != 'Empty!') and (users_farm.plot2 != 'Empty!') and (users_farm.plot3 != 'Empty!'):
                    for x in range(3):
                        self.add_item(PlantButton("Plots full!", discord.ButtonStyle.grey, True, None, None, None))
                else:
                    for number, seed in enumerate(seeds):
                        if seed == 0:
                            self.add_item(PlantButton("No seeds", discord.ButtonStyle.grey, True, seed, number,
                                                      list(crops.keys())[number]))
                        else:
                            self.add_item(PlantButton(names[number], discord.ButtonStyle.blurple, False, seed, number,
                                                      list(crops.keys())[number]))
                self.add_item(ExitButton())
                self.add_item(SwitchToBarnButton())
                self.add_item(SwitchToFarmButton())

            async def on_timeout(self) -> None:
                users_farm.has_open_farm = False
                users_farm.save()
                try:
                    await interaction.delete_original_response()
                except discord.errors.NotFound:
                    pass

        class PlantButton(discord.ui.Button):
            def __init__(self, button_label, button_style, button_disabled, seed, seed_no, crop_name):
                self.button_label = button_label
                self.button_style = button_style
                self.button_disabled = button_disabled
                self.seed = seed
                self.seed_no = seed_no
                self.crop_name = crop_name
                super().__init__(label=self.button_label, style=self.button_style, disabled=self.button_disabled)

            async def callback(self, plant_interaction: discord.Interaction):
                if plant_interaction.user != interaction.user:
                    return
                self.seed -= 1
                if self.seed_no == 0:
                    users_farm.almonds_seeds -= 1
                elif self.seed_no == 1:
                    users_farm.coconuts_seeds -= 1
                elif self.seed_no == 2:
                    users_farm.chocolates_seeds -= 1
                users_farm.save()
                if self.seed == 0:
                    self.disabled = True
                    self.style = discord.ButtonStyle.grey
                    self.label = "No seeds"
                planted_in = None
                if users_farm.plot1 == "Empty!":
                    users_farm.plot1 = self.crop_name[:-1] + ' seeds'
                    planted_in = "Plot 1"
                elif users_farm.plot2 == "Empty!":
                    users_farm.plot2 = self.crop_name[:-1] + ' seeds'
                    planted_in = "Plot 2"
                elif users_farm.plot3 == "Empty!":
                    users_farm.plot3 = self.crop_name[:-1] + ' seeds'
                    planted_in = "Plot 3"
                self.view.plant_embed.add_field(name="Planted!", value=f"{self.crop_name[:-1]} seeds\n{planted_in}")
                users_farm.save()
                if (users_farm.plot1 != 'Empty!') and (users_farm.plot2 != 'Empty!') and (users_farm.plot3 != 'Empty!'):
                    for button in self.view.children:
                        if button.row == 1:
                            button.disabled = False
                        else:
                            button.disabled = True
                await plant_interaction.response.edit_message(embed=self.view.plant_embed, view=self.view)

        class SwitchToBarnButton(discord.ui.Button):
            def __init__(self, row=1):
                super().__init__(label="Barn", style=discord.ButtonStyle.blurple, row=row)

            async def callback(self, switch_to_barn_interaction: discord.Interaction):
                if switch_to_barn_interaction.user != interaction.user:
                    return
                self.view.stop()
                await switch_to_barn_interaction.response.edit_message(embed=Barn().barn_embed, view=Barn())

        class SwitchToPlantButton(discord.ui.Button):
            def __init__(self, row=1):
                super().__init__(label="Plant", style=discord.ButtonStyle.blurple, row=row)

            async def callback(self, switch_to_plant_interaction: discord.Interaction):
                if switch_to_plant_interaction.user != interaction.user:
                    return
                self.view.stop()
                await switch_to_plant_interaction.response.edit_message(embed=Plant().plant_embed, view=Plant())

        class SwitchToFarmButton(discord.ui.Button):
            def __init__(self, row=1):
                super().__init__(label="Farm", style=discord.ButtonStyle.blurple, row=row)

            async def callback(self, switch_to_farm_interaction: discord.Interaction):
                if switch_to_farm_interaction.user != interaction.user:
                    return
                self.view.stop()
                await switch_to_farm_interaction.response.edit_message(embed=Farm().farm_module_embed, view=Farm())

        await interaction.response.send_message(embed=Farm().farm_module_embed, view=Farm())


async def setup(bot):
    await bot.add_cog(FarmingCog(bot))
