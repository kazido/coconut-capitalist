import discord
import asyncio
from discord.ext import commands, tasks
from discord import app_commands

from random import randint
from cococap.user import User
from cococap.item_models import Master
from cococap.constants import DiscordGuilds
from cococap.utils.messages import Cembed


def plot_button_refresh(user_farm_dict: dict):
    """For every plot, if its empty, button style is grey,
    if its not, button style is green! Use this to refesh the
    style of the button upon click OR to setup the button."""
    button_info = {}
    plots = []
    for index in range(len(m.Farming.plots)):
        button_info[index] = {
            "label": "Empty!",
            "disabled": True,
            "style": discord.ButtonStyle.grey,
            "crop": None
        }
        plots.append(user_farm_dict[f'plot{index+1}'])
    for index, plot_contents in enumerate(plots):
        if plot_contents.startswith("SEED"):
            button_info[index]['label'] = "Growing"
        elif plot_contents.startswith("CROP"):
            button_info[index]['style'] = discord.ButtonStyle.green
            button_info[index]['label'] = "Harvest!"
            button_info[index]['disabled'] = False
            button_info[index]['crop'] = plot_contents
    return button_info


# def harvest(button_info, button, user: discord.Member):
#     if button_info['crop'] == 'CROP_COCONUT':
#         harvested_crops = 1
#         double = randint(1, 100)
#         if double == 5:
#             harvested_crops = 2
#     else:
#         harvested_crops = randint(consumables['CROPS'][button_info['crop']]['STAT_harvest_low'],
#                                   consumables['CROPS'][button_info['crop']]['STAT_harvest_high'])
#     crop_in_db, created = mm.Items.get_or_create(owner_id=user.id, reference_id=button_info['crop'],
#                                         defaults={'durability': None, 'quantity': harvested_crops})
#     crop_in_db.quantity += harvested_crops
#     crop_in_db.save()
#     button.disabled = True
#     button.style = discord.ButtonStyle.grey
#     button.label = "Empty"
#     return harvested_crops

class Farm(discord.ui.View):
    def __init__(self, *, timeout=30):
        super().__init__(timeout=timeout)
        
        user_plots = [users_farm_dict[x] for x in mm.Farms.plots]
        for count, plot_contents in enumerate(user_plots):
            if plot_contents.startswith("CROP"):
                plot_contents = consumables['CROPS'][plot_contents]['emoji']
            elif plot_contents == 'Empty!':
                plot_contents = plot_contents
            else:
                plot_contents = consumables['SEEDS'][plot_contents]['name']
            self.farm_module_embed.add_field(
                name=f"Plot {count + 1} 🌳", value=plot_contents)
        self.farm_module_embed.set_footer(
            text="Crops have a chance to grow every hour.")
        plot_button_info = plot_button_refresh(user_farm_dict=users_farm_dict)
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
        super().__init__(label=self.button_label,
                            style=self.button_style, disabled=self.button_disabled)

    async def callback(self, harvest_interacton: discord.Interaction):
        if harvest_interacton.user != interaction.user:
            return
        harvested_crops = harvest(
            self.button_dict, self, interaction.user)
        self.view.farm_module_embed.set_field_at(self.button_no, name=f'Plot {self.button_no + 1}',
                                                    value=f"+{harvested_crops}")
        users_farm_dict[f'plot{self.button_no+1}'] = 'Empty!'
        button_info = plot_button_refresh(user_farm_dict=users_farm_dict)
        users_farm = phs.dict_to_model(mm.Farms, users_farm_dict)
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
    def __init__(self, timeout=20):
        super().__init__(timeout=timeout)
        self.barn_embed = discord.Embed(
            title=f"Welcome to the Barn!",
            description="Here is *your* inventory of crops and seeds. Happy farming!",
            color=0x8c6803)
        self.barn_embed.set_author(name=f"{interaction.user.name} - In the Barn",
                                    icon_url=interaction.user.display_avatar)
        for key, value in consumables['CROPS'].items():
            crop_quantity = 0
            seeds_quantity = 0
            crop = mm.Items.get_or_none(mm.Items.owner_id == interaction.user.id, mm.Items.reference_id == key)
            if crop:
                crop_quantity = crop.quantity
            seed = mm.Items.get_or_none(mm.Items.owner_id == interaction.user.id, mm.Items.reference_id == value['grows_from'])
            if seed:
                seeds_quantity = seed.quantity
            # self.barn_embed.description += f"\n{value['emoji']} \u200b **{crop_quantity:,}** {value['name']}s \
            #     :seedling: \u200b **{seeds_quantity:,}** seeds"
            self.barn_embed.add_field(name=f"{value['name'].capitalize()}",
                                        value=f"{value['emoji']} \u200b **{crop_quantity:,}** {value['name']}s "
                                        f":seedling: \u200b **{seeds_quantity:,}** seeds",
                                        inline=False)
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
    def __init__(self, timeout=20):
        super().__init__(timeout=timeout)
        self.plant_embed = discord.Embed(
            title=f"Plant crops to sell or to feed your pets",
            description=f"You can plant various kinds of crops \
                which you can *sell* for a **profit** or *feed* to your **pets**.",
            color=0x8db046)
        self.plant_embed.set_author(name=f"{interaction.user.name} - Planting",
                                    icon_url=interaction.user.display_avatar)
        user_plots = [users_farm_dict[x] for x in mm.Farms.plots]
        plots_full = 0
        for index, plot in enumerate(user_plots):
            if plot != 'Empty!':
                self.plant_embed.add_field(name=f"Plot {index+1} 🌳", value=f"{consumables[plot[0:4]+'S'][plot]['name']}")
                plots_full += 1
            else:
                self.plant_embed.add_field(name=f"Plot {index+1} 🌳", value=f"Empty!")

        if plots_full == len(user_plots):
            self.add_item(PlantButton(
                    discord.ButtonStyle.grey, True, label='Plots full!'))
        else:
            for key in consumables['SEEDS'].keys():
                seeds_quantity = 0
                seeds = mm.Items.get_or_none(mm.Items.owner_id == interaction.user.id, mm.Items.reference_id == key)
                if seeds:
                    seeds_quantity = seeds.quantity
                if seeds_quantity == 0:
                    self.add_item(PlantButton(
                        discord.ButtonStyle.grey, True, label='No seeds'))
                else:
                    self.add_item(PlantButton(
                        discord.ButtonStyle.blurple, False, seed_ref_id=key))

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
    def __init__(self, button_style, button_disabled, seed_ref_id=None, label: str = None):
        self.button_style = button_style
        self.button_disabled = button_disabled
        self.seed_ref_id = seed_ref_id
        if label:
            button_label = label
        else:
            button_label = consumables['SEEDS'][self.seed_ref_id]['name']
        super().__init__(label=button_label,
                            style=self.button_style, disabled=self.button_disabled)

    async def callback(self, plant_interaction: discord.Interaction):
        if plant_interaction.user != interaction.user:
            return
        seeds = mm.Items.get(mm.Items.owner_id==interaction.user.id, mm.Items.reference_id==self.seed_ref_id)
        seeds.quantity -= 1
        seeds.save()
        if seeds.quantity == 0:
            self.disabled = True
            self.style = discord.ButtonStyle.grey
            self.label = "No seeds"
        user_plots = [users_farm_dict[x] for x in mm.Farms.plots]
        for index, plot in enumerate(user_plots):
            if plot == 'Empty!':
                self.view.plant_embed.set_field_at(index=index, name="PLANTED!", value=f"{consumables['SEEDS'][self.seed_ref_id]['name']}")
                users_farm_dict[f'plot{index+1}'] = self.seed_ref_id
                users_farm = phs.dict_to_model(mm.Farms, users_farm_dict)
                users_farm.save()
                break
        else:
            for button in self.view.children:
                if button.row == 1:
                    button.disabled = False
                else:
                    button.disabled = True
        self.view.__init__()
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


class FarmingCog(commands.Cog, name="Farming"):
    """Special farming cog, allows users to farm for coconuts on plots of land"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree
        
    async def cog_load(self) -> None:
        self.farm_task.start()
        return await super().cog_load()

    async def cog_unload(self) -> None:
        self.farm_task.stop()
        return await super().cog_unload()

    @tasks.loop(minutes=60)
    # Checks everyone's ungrown crops and has a chance to grow them
    async def farm_task(self):
        lucky_farmers = []
        farms = mm.Farms.select()
        for farm in farms.objects():
            users_farm_dict = phs.model_to_dict(farm)
            user_plots = [users_farm_dict[x] for x in mm.Farms.plots]

            for index, plot in enumerate(user_plots):
                if plot.startswith('SEED'):
                    should_grow = growth_roll(seed_ref_id=plot)
                    grown_crop = consumables['SEEDS'][plot]['grows_into']
                    if should_grow:  # Applies growth role based on crop without "seeds" at the end, checks if grown
                        users_farm_dict[f'plot{index+1}'] = grown_crop
                        guild = self.bot.get_guild(856915776345866240)
                        user_in_discord = discord.utils.get(guild.members, id=int(farm.id.id))
                        lucky_farmers.append(user_in_discord.mention)
            farm = phs.dict_to_model(mm.Farms, users_farm_dict)
            farm.save()

        # Guild to send the farm updates in
        guild = self.bot.get_guild(856915776345866240)
        channel = guild.get_channel(966990507689533490)
        rain_events = ["The rains pour down onto the fields...", "The sun provides ample growth today!",
                       "The winds pass and bring an air of good harvest.",
                       "There's no better time of day to harvest than now!", "It's harvest o'clock somewhere...",
                       "Does the rain ever get tired of providing for these crops?", "Big rain storm approaching!"]
        lucky_farmers = list(set(lucky_farmers))
        if len(lucky_farmers) != 0:
            await channel.send(f"*{random.choice(rain_events)}*\nThe lucky farmers are: **{', '.join(lucky_farmers)}**")
    
    
    @app_commands.command(name="farm")
    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value)
    async def farm(self, interaction: discord.Interaction):
        """Grow crops to feed your pets and make some money."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        farming = user.get_field('farming')
        
        skill_xp = farming['xp']
        skill_level = user.xp_to_lvl(skill_xp)
        embed = Cembed(
            title=f"Farming level: {skill_level}",
            color=discord.Color.blue(),
            interaction=interaction,
            activity="farming",
        )
    
        if farming['equipped_tool']:
            tool_data = Master.get_by_id(farming['equipped_tool'])
        # If the user already has an open farm
        if farming['is_farming']:  
            embed = Cembed(
                title="You already have an open farming module!",
                desc="Please close the farming module, or wait 20 seconds",
                color=discord.Color.red(),
                interaction=interaction,
                activity="farming")

            await interaction.response.send_message(embed=embed)
            await asyncio.sleep(5)
            await interaction.delete_original_response()
            return
        farming['is_farming'] = True  
        await user.document.save()

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(FarmingCog(bot))
