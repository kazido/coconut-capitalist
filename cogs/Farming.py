import asyncio
import discord  # Discord imports
from discord.ext import commands, tasks
from discord import app_commands
import random  # Random imports
from random import randint
from ClassLibrary2 import RequestUser, crops  # File imports
from cogs.ErrorHandler import registered
from utils import seconds_until_tasks
import mymodels as mm


def growth_roll(crop_type):
    growth_range = range(crops[crop_type]['growth_odds'][0], crops[crop_type]['growth_odds'][1])
    roll = randint(0, 100)
    if roll in growth_range:  # If the roll is in the range for the crop to grow
        return True  # Set function as true, the crop grew
    else:
        return False  # The crop didn't grow


async def plot_check(ctx, user_id, seed):
    database = await ctx.bot.dbfarms.find_one({"_id": user_id})
    planted_in = None
    if database['plot1'] == "Empty!":
        await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"plot1": seed.replace('_', ' ')}})
        planted_in = "p1"
    elif database['plot2'] == "Empty!":
        await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"plot2": seed.replace('_', ' ')}})
        planted_in = "p2"
    elif database['plot3'] == "Empty!":
        await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"plot3": seed.replace('_', ' ')}})
        planted_in = "p3"
    return planted_in


async def end_plot_check(ctx, user_id):
    database = await ctx.bot.dbfarms.find_one({"_id": user_id})
    if database['plot1'] != "Empty!" and database['plot2'] != "Empty!" and database['plot3'] != "Empty!":
        return True


async def button_function(self, embed, unembed, options, ctx, interaction, button, user_id, crop):
    if interaction.user != ctx.author:
        return
    await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$inc": {crop.seed: -1}})
    updated_seeds = await ctx.bot.dbfarms.find_one({"_id": user_id})
    if updated_seeds[crop.seed] == 0:
        button.disabled = True
        button.style = discord.ButtonStyle.grey
        button.label = "No seeds"
    planted_in = await plot_check(ctx, user_id, crop.seed)
    embed.add_field(name="Planted!", value=f"{crop.type[:-1]} seeds\n{options[planted_in]}")
    unembed.add_field(name="Planted!", value=f"{crop.type[:-1]} seeds\n{options[planted_in]}")
    if await end_plot_check(ctx, user_id):
        for x in self.children:
            if x.label == "Exit":
                x.disabled = False
            else:
                x.disabled = True
        await interaction.response.edit_message(embed=unembed, view=self)
        return
    await interaction.response.edit_message(embed=embed, view=self)


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
    if button_number['crop'] == "almond":
        harvested_crops = randint(3, 20)
    elif button_number['crop'] == "coconut":
        harvested_crops = randint(2, 3)
    elif button_number['crop'] == "cacao":
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
            if farm.plot1.endswith(' seeds'):
                grown = growth_roll(farm.plot1[:len(farm.plot1) - 6])
                if grown:
                    farm.plot1 = farm.plot1[:len(farm.plot1) - 6]
                    lucky_farmers.append(farm.id.name)
            if farm.plot2.endswith(' seeds'):
                grown = growth_roll(farm.plot2[:len(farm.plot2) - 6])
                if grown:
                    farm.plot2 = farm.plot2[:len(farm.plot2) - 6]
                    lucky_farmers.append(farm.id.name)
            if farm.plot3.endswith(' seeds'):
                grown = growth_roll(farm.plot3[:len(farm.plot3) - 6])
                if grown:
                    farm.plot3 = farm.plot3[:len(farm.plot3) - 6]
                    lucky_farmers.append(farm.id.name)
            farm.save()
        guild = self.bot.get_guild(856915776345866240)  # Guild to send the drops in
        channel = guild.get_channel(966990507689533490)
        rain_events = ["The rains pour down onto the fields...", "The sun provides ample growth today!",
                       "The winds pass and bring an air of good harvest.",
                       "There's no better time of day to harvest than now!", "It's harvest o'clock somewhere...",
                       "Does the rain ever get tired of providing for these crops?", "Big rain storm approaching!"]
        lucky_farmers = list(set(lucky_farmers))
        if len(lucky_farmers) != 0:
            await channel.send(f"*{random.choice(rain_events)}*\nThe lucky farmers are: **{', '.join(lucky_farmers)}**")

    @farm_task.before_loop
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

        farm_module_embed = discord.Embed(
            title=f"{interaction.user.name}'s Farm",
            description="Collect seeds and plant them in your plots!\nCustomizations coming soon!",
            color=0x1adb24)

        plots = [users_farm.plot1, users_farm.plot2, users_farm.plot3]
        for count, crop in enumerate(plots):
            if crop == "coconut":
                plot_contents = ":coconut:"
            elif crop == "almond":
                plot_contents = ":chestnut:"
            elif crop == "cacao":
                plot_contents = ":chocolate_bar:"
            else:
                plot_contents = crop
            farm_module_embed.add_field(name=f"Plot {count + 1} 🌳", value=plot_contents)
        farm_module_embed.set_footer(text="Crops have a chance to grow once every 30 minutes.")

        plot_button_info = plot_button_refresh(plots)
        button_1 = plot_button_info[0]
        button_2 = plot_button_info[1]
        button_3 = plot_button_info[2]

        class FarmButtons(discord.ui.View):
            def __init__(self, *, timeout=20):
                super().__init__(timeout=timeout)

            async def on_timeout(self) -> None:
                users_farm.has_open_farm = False
                await interaction.delete_original_response()

            @discord.ui.button(label=button_1['label'], style=button_1['style'], disabled=button_1['disabled'])
            async def plot_1_button(self, button1interaction: discord.Interaction, button: discord.ui.Button):
                if button1interaction.user != interaction.user:
                    return
                harvested_crops = harvest(button_1, button, users_farm)
                users_farm.plot1 = 'Empty!'
                farm_module_embed.set_field_at(0, name="Plot 1 🌳", value=f"+{harvested_crops}")
                plot_button_refresh(plots)
                await button1interaction.response.edit_message(embed=farm_module_embed, view=self)

            @discord.ui.button(label=button_2['label'], style=button_2['style'], disabled=button_3['disabled'])
            async def plot_2_button(self, button2interaction: discord.Interaction, button: discord.ui.Button):
                if button2interaction.user != interaction.user:
                    return
                harvested_crops = harvest(button_2, button, users_farm)
                users_farm.plot2 = 'Empty!'
                farm_module_embed.set_field_at(1, name="Plot 2 🌳", value=f"+{harvested_crops}")
                plot_button_refresh(plots)
                await button2interaction.response.edit_message(embed=farm_module_embed, view=self)

            @discord.ui.button(label=button_3['label'], style=button_3['style'], disabled=button_3['disabled'])
            async def plot_3_button(self, button3interaction: discord.Interaction, button: discord.ui.Button):
                if button3interaction.user != interaction.user:
                    return
                harvested_crops = harvest(button_3, button, users_farm)
                users_farm.plot3 = 'Empty!'
                farm_module_embed.set_field_at(2, name="Plot 3 🌳", value=f"+{harvested_crops}")
                plot_button_refresh(plots)
                await button3interaction.response.edit_message(embed=farm_module_embed, view=self)

            @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
            async def exit_button(self, exit_button_interaction: discord.Interaction, button: discord.ui.Button):
                if exit_button_interaction.user != interaction.user:
                    return
                users_farm.has_open_farm = False
                users_farm.save()
                await interaction.delete_original_response()
                self.stop()

        await interaction.response.send_message(embed=farm_module_embed, view=FarmButtons())

    # @registered()
    # @commands.command(name="Plant", description="Plant some seeds and grow some crops!", brief="-plant")
    # async def plant(self, ctx):
    #     if users_farm['plot1'] != "Empty!" and users_farm['plot2'] != "Empty!" and users_farm['plot3'] != "Empty!":
    #         embed = discord.Embed(
    #             title="Your farm is currently full.",
    #             description="Use -farm to see your plots.",
    #             color=discord.Color.red()
    #         )
    #         await ctx.send(embed=embed)
    #         return
    #     await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": True}})
    #     names = []
    #     for x in crops:
    #         names.append(x.type)
    #     plant_embed = discord.Embed(
    #         title="What type of crop would you like to plant?",
    #         description=f"You can plant whatever crops you have seeds for: {', '.join(names)}",
    #         color=0x1adb24
    #     )
    #     unavailable_embed = discord.Embed(
    #         title="You have planted seeds in all your plots!",
    #         color=discord.Color.dark_grey()
    #     )
    #     plant_embed.set_footer(text="Tip: check the amount of seeds you have in -barn")
    #     unavailable_embed.set_footer(text="Tip: check the amount of seeds you have in -barn")
    #     seeds = [users_farm[almond.seed], users_farm[coconut.seed], users_farm[cacao.seed]]
    #
    #     def seed_check():
    #         styles = {}
    #         labels = {}
    #         disabled = {1: False,
    #                     2: False,
    #                     3: False}
    #         for count, x in enumerate(seeds):
    #             if x == 0:
    #                 styles[count + 1] = discord.ButtonStyle.grey
    #                 labels[count + 1] = "No seeds"
    #                 disabled[count + 1] = True
    #             else:
    #                 styles[count + 1] = discord.ButtonStyle.blurple
    #                 labels[count + 1] = names[count]
    #         return styles, disabled, labels
    #
    #     styles, disabled, labels = seed_check()
    #     options = {"p1": "Plot 1", "p2": "Plot 2", "p3": "Plot 3"}
    #
    #     class PlantButtons(discord.ui.View):
    #         def __init__(self, *, timeout=20):
    #             super().__init__(timeout=timeout)
    #
    #         async def on_timeout(self) -> None:
    #             await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": False}})
    #             await plant_message.delete()
    #
    #         @discord.ui.button(label=labels[1], style=styles[1], disabled=disabled[1])
    #         async def coconut_seed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #             await button_function(self, plant_embed, unavailable_embed, options, ctx, interaction, button, user_id,
    #                                   almond)
    #
    #         @discord.ui.button(label=labels[2], style=styles[2], disabled=disabled[2])
    #         async def cacao_seed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #             await button_function(self, plant_embed, unavailable_embed, options, ctx, interaction, button, user_id,
    #                                   coconut)
    #
    #         @discord.ui.button(label=labels[3], style=styles[3], disabled=disabled[3])
    #         async def almond_seed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #             await button_function(self, plant_embed, unavailable_embed, options, ctx, interaction, button, user_id,
    #                                   cacao)
    #
    #         @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
    #         async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #             if interaction.user != ctx.author:
    #                 return
    #             await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": False}})
    #             await plant_message.delete()
    #             await ctx.message.delete()
    #             self.stop()
    #
    #     plant_message = await ctx.send(embed=plant_embed, view=PlantButtons())
    #
    # @registered()
    # @commands.command(name="Barn", description="Check your stock of crops and seeds.", brief="-bard")
    # async def barn(self, interaction: discord.Interaction):
    #     users_farm = mm.Farms.get(id=interaction.user.id)
    #     embed = discord.Embed(
    #         title=f"{interaction.user.name}'s Barn",
    #         description="Here is your inventory of crops and seeds. Happy farming!",
    #         color=0x8c6803)
    #     barn_crops = []
    #     for x in crops:
    #         barn_crops.append(x.type)
    #     for x in crops:
    #         barn_crops.append(x.seed.replace('_', ' '))
    #     barn = {"coconuts": {"emoji": ":coconut:",
    #                          "count": users_farm['coconuts']},
    #             "cacaos": {"emoji": ":chocolate_bar:",
    #                        "count": users_farm['cacaos']},
    #             "almonds": {"emoji": ":chestnut:",
    #                         "count": users_farm['almonds']},
    #             "coconut seeds": {"emoji": ":coconut: seeds",
    #                               "count": users_farm['coconut_seeds']},
    #             "cacao seeds": {"emoji": ":chocolate_bar: seeds",
    #                             "count": users_farm['cacao_seeds']},
    #             "almond seeds": {"emoji": ":chestnut: seeds",
    #                              "count": users_farm['almond_seeds']},
    #             }
    #     for x in barn_crops:
    #         embed.add_field(name=barn[x]['emoji'], value=barn[x]['count'], inline=True)
    #     embed.set_footer(text="Use -plant and -farm to plant and view your crops!")
    #     if not ctx.author.is_on_mobile():
    #         await ctx.send(embed=embed)
    #     else:
    #         mobile_embed = discord.Embed(
    #             title=f"{ctx.author.name}'s Barn",
    #             description="Here is your inventory of crops and seeds. Happy farming!",
    #             color=0x8c6803
    #         )
    #         mobile_embed.add_field(name="Almonds", value=f"`{barn['almonds']['count']}`\n"
    #                                                      f"*`({barn['almond seeds']['count']} seeds)`*")
    #         mobile_embed.add_field(name="Coconuts", value=f"`{barn['coconuts']['count']}`\n"
    #                                                       f"*`({barn['coconut seeds']['count']} seeds)`*")
    #         mobile_embed.add_field(name="Cacaos", value=f"`{barn['cacaos']['count']}`\n"
    #                                                     f"*`({barn['cacao seeds']['count']} seeds)`*")
    #         mobile_embed.set_footer(text="Use -plant and -farm to plant and view your crops!")
    #         await ctx.send(embed=mobile_embed)


async def setup(bot):
    await bot.add_cog(FarmingCog(bot))
