import asyncio
from random import randint

from discord.ext import commands
from ClassLibrary import *
from Cogs.EconomyCog import get_role
from Cogs.ErrorHandler import registered, missing_perks


class Crop:
    def __init__(self, type, seed, price):
        self.type = type
        self.seed = seed
        self.price = price


almond = Crop("almonds", "almond_seeds", 0)
coconut = Crop("coconuts", "coconut_seeds", 0)
cacao = Crop("cacaos", "cacao_seeds", 0)
crops = [almond, coconut, cacao]


async def embed_out_check(ctx, database):
    if database["has_open_farm"]:
        embed = discord.Embed(
            title="You already have a farming module!",
            description="Please close the farming module, or wait 20 seconds",
            color=discord.Color.red()
        )
        message = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await message.delete()
        return True


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


class FarmingCog(commands.Cog, name="Farming"):
    """Special farming cog, allows users to farm for coconuts on plots of land"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def add_farms(self, ctx):
        # await self.bot.dbfarms.update_many({}, {"$set": {"plot2": "Empty"}})
        pass

    @registered()
    @missing_perks("Farmer")
    @commands.command(name="Farm", description="Grow some crops to fill your barn!", brief="-farm")
    async def farm(self, ctx):
        user_id = ctx.author.id
        users_farm = await self.bot.dbfarms.find_one({"_id": user_id})
        if await embed_out_check(ctx, users_farm):
            return
        await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": True}})
        embed = discord.Embed(
            title=f"{ctx.author.name}'s Farm",
            description="Collect seeds and plant them in your plots!\nCustomizations coming soon!",
            color=0x1adb24
        )
        plots = [users_farm['plot1'], users_farm['plot2'], users_farm['plot3']]
        emoji = None
        for count, x in enumerate(plots):
            if x == "coconuts" or x == "coconut":
                emoji = ":coconut:"
            elif x == "almonds" or x == "almond":
                emoji = ":chestnut:"
            elif x == "cacaos" or x == "cacao":
                emoji = ":chocolate_bar:"
            else:
                emoji = x
            embed.add_field(name=f"Plot {count + 1} 🌳", value=emoji)
        embed.set_footer(text="Crops have a chance to grow once every 30 minutes.")

        # For every plot, if its empty, button style is grey, if its not, button style is green!
        def farm_check():
            amount = 1
            styles = {}
            labels = {}
            disabled = {1: False,
                        2: False,
                        3: False}
            plant_types = {}
            plants = ["almonds", "almond", "coconuts", "coconut", "cacaos", "cacao"]
            for count, x in enumerate(plots):
                if x == "Empty!":
                    styles[count + 1] = discord.ButtonStyle.grey
                    labels[count + 1] = "Empty"
                    disabled[count + 1] = True
                elif x not in plants:
                    styles[count + 1] = discord.ButtonStyle.grey
                    labels[count + 1] = "Growing"
                    disabled[count + 1] = True
                else:
                    styles[count + 1] = discord.ButtonStyle.green
                    labels[count + 1] = "Harvest!"
                    if x.endswith('s'):
                        plant_types[count + 1] = x
                    else:
                        plant_types[count + 1] = x + "s"
            return styles, plant_types, disabled, labels, amount

        styles, plant_types, disabled, labels, amount = farm_check()

        class FarmButtons(discord.ui.View):
            def __init__(self, *, timeout=20):
                super().__init__(timeout=timeout)

            async def on_timeout(self) -> None:
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": False}})
                await message.delete()

            @discord.ui.button(label=labels[1], style=styles[1], disabled=disabled[1])
            async def plot_1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                amount_to_add = 1
                if plant_types[1] == "almonds":
                    amount_to_add = randint(2, 20)
                elif plant_types[1] == "coconuts":
                    amount_to_add = randint(1, 2)
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$inc": {plant_types[1]: amount_to_add}})
                button.disabled = True
                button.style = discord.ButtonStyle.grey
                button.label = "Empty"
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"plot1": "Empty!"}})
                embed.set_field_at(0, name="Plot 1 🌳", value=f"+{amount_to_add}")
                farm_check()
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label=labels[2], style=styles[2], disabled=disabled[2])
            async def plot_2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                amount_to_add = 1
                if plant_types[2] == "almonds":
                    amount_to_add = randint(2, 20)
                elif plant_types[2] == "coconuts":
                    amount_to_add = randint(1, 2)
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$inc": {plant_types[2]: amount_to_add}})
                button.disabled = True
                button.style = discord.ButtonStyle.grey
                button.label = "Empty"
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"plot2": "Empty!"}})
                embed.set_field_at(1, name="Plot 2 🌳", value=f"+{amount_to_add}")
                farm_check()
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label=labels[3], style=styles[3], disabled=disabled[3])
            async def plot_3_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                amount_to_add = 1
                if plant_types[3] == "almonds":
                    amount_to_add = randint(2, 20)
                elif plant_types[3] == "coconuts":
                    amount_to_add = randint(1, 2)
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$inc": {plant_types[3]: amount_to_add}})
                button.disabled = True
                button.style = discord.ButtonStyle.grey
                button.label = "Empty"
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"plot3": "Empty!"}})
                embed.set_field_at(2, name="Plot 3 🌳", value=f"+{amount_to_add}")
                farm_check()
                await interaction.response.edit_message(embed=embed, view=self)

            @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
            async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": False}})
                await message.delete()
                await ctx.message.delete()
                self.stop()

        message = await ctx.send(embed=embed, view=FarmButtons())

    @registered()
    @missing_perks("Farmer")
    @commands.command(name="Plant", description="Plant some seeds and grow some crops!", brief="-plant")
    async def plant(self, ctx):
        user_id = ctx.author.id
        users_farm = await self.bot.dbfarms.find_one({"_id": user_id})
        if users_farm['plot1'] != "Empty!" and users_farm['plot2'] != "Empty!" and users_farm['plot3'] != "Empty!":
            embed = discord.Embed(
                title="Your farm is currently full.",
                description="Use -farm to see your plots.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        if await embed_out_check(ctx, users_farm):
            return
        await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": True}})
        names = []
        for x in crops:
            names.append(x.type)
        plant_embed = discord.Embed(
            title="What type of crop would you like to plant?",
            description=f"You can plant whatever crops you have seeds for: {', '.join(names)}",
            color=0x1adb24
        )
        unavailable_embed = discord.Embed(
            title="You have planted seeds in all your plots!",
            color=discord.Color.dark_grey()
        )
        plant_embed.set_footer(text="Tip: check the amount of seeds you have in -barn")
        unavailable_embed.set_footer(text="Tip: check the amount of seeds you have in -barn")
        seeds = [users_farm[almond.seed], users_farm[coconut.seed], users_farm[cacao.seed]]

        def seed_check():
            styles = {}
            labels = {}
            disabled = {1: False,
                        2: False,
                        3: False}
            for count, x in enumerate(seeds):
                if x == 0:
                    styles[count + 1] = discord.ButtonStyle.grey
                    labels[count + 1] = "No seeds"
                    disabled[count + 1] = True
                else:
                    styles[count + 1] = discord.ButtonStyle.blurple
                    labels[count + 1] = names[count]
            return styles, disabled, labels

        styles, disabled, labels = seed_check()
        options = {"p1": "Plot 1", "p2": "Plot 2", "p3": "Plot 3"}

        class PlantButtons(discord.ui.View):
            def __init__(self, *, timeout=20):
                super().__init__(timeout=timeout)

            async def on_timeout(self) -> None:
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": False}})
                await plant_message.delete()

            @discord.ui.button(label=labels[1], style=styles[1], disabled=disabled[1])
            async def coconut_seed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await button_function(self, plant_embed, unavailable_embed, options, ctx, interaction, button, user_id,
                                      almond)

            @discord.ui.button(label=labels[2], style=styles[2], disabled=disabled[2])
            async def cacao_seed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await button_function(self, plant_embed, unavailable_embed, options, ctx, interaction, button, user_id,
                                      coconut)

            @discord.ui.button(label=labels[3], style=styles[3], disabled=disabled[3])
            async def almond_seed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await button_function(self, plant_embed, unavailable_embed, options, ctx, interaction, button, user_id,
                                      cacao)

            @discord.ui.button(label="Exit", style=discord.ButtonStyle.red)
            async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                await ctx.bot.dbfarms.update_one({"_id": user_id}, {"$set": {"has_open_farm": False}})
                await plant_message.delete()
                await ctx.message.delete()
                self.stop()

        plant_message = await ctx.send(embed=plant_embed, view=PlantButtons())

    @registered()
    @missing_perks("Farmer")
    @commands.command(name="Barn", description="Check your stock of crops and seeds.", brief="-bard")
    async def barn(self, ctx):
        user_id = ctx.author.id
        users_farm = await self.bot.dbfarms.find_one({"_id": user_id})
        embed = discord.Embed(
            title=f"{ctx.author.name}'s Barn",
            description="Here is your inventory of crops and seeds. Happy farming!",
            color=0x8c6803
        )
        barn_crops = []
        for x in crops:
            barn_crops.append(x.type)
        for x in crops:
            barn_crops.append(x.seed.replace('_', ' '))
        barn = {"coconuts": {"emoji": ":coconut:",
                             "count": users_farm['coconuts']},
                "cacaos": {"emoji": ":chocolate_bar:",
                           "count": users_farm['cacaos']},
                "almonds": {"emoji": ":chestnut:",
                            "count": users_farm['almonds']},
                "coconut seeds": {"emoji": ":coconut: seeds",
                                  "count": users_farm['coconut_seeds']},
                "cacao seeds": {"emoji": ":chocolate_bar: seeds",
                                "count": users_farm['cacao_seeds']},
                "almond seeds": {"emoji": ":chestnut: seeds",
                                 "count": users_farm['almond_seeds']},
                }
        for x in barn_crops:
            embed.add_field(name=barn[x]['emoji'], value=barn[x]['count'], inline=True)
        embed.set_footer(text="Use -plant and -farm to plant and view your crops!")
        if not ctx.author.is_on_mobile():
            await ctx.send(embed=embed)
        else:
            mobile_embed = discord.Embed(
                title=f"{ctx.author.name}'s Barn",
                description="Here is your inventory of crops and seeds. Happy farming!",
                color=0x8c6803
            )
            mobile_embed.add_field(name="Almonds", value=f"`{barn['almonds']['count']}`\n"
                                                         f"*`({barn['almond seeds']['count']} seeds)`*")
            mobile_embed.add_field(name="Coconuts", value=f"`{barn['coconuts']['count']}`\n"
                                                          f"*`({barn['coconut seeds']['count']} seeds)`*")
            mobile_embed.add_field(name="Cacaos", value=f"`{barn['cacaos']['count']}`\n"
                                                        f"*`({barn['cacao seeds']['count']} seeds)`*")
            mobile_embed.set_footer(text="Use -plant and -farm to plant and view your crops!")
            await ctx.send(embed=mobile_embed)


async def setup(bot):
    await bot.add_cog(FarmingCog(bot))
