import discord
from Cogs.ErrorHandler import registered
from ClassLibrary import *


class ShopCog(commands.Cog, name='Shop'):
    """Purchase helpful items on your way to the top!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @commands.command(name="Shop", aliases=["buy"], description="Buy helpful items!", brief="-shop")
    async def shop(self, ctx):
        # User information
        user = User(ctx)
        inventory = Inventory(ctx)

        # Available products
        tools = [shovel_lv1]
        seeds = [almond_seeds, coconut_seeds, cacao_seeds]

        # Class for subclassing buttons for purchasing items
        class ButtonCreation(discord.ui.Button):
            def __init__(self, ctx, label, style, custom_id, disabled, item, shop_view):
                super().__init__(label=label, style=style, custom_id=custom_id, disabled=disabled)
                self.ctx = ctx
                self.item = item
                self.shop_view = shop_view

            async def callback(self, interaction):
                if interaction.user != ctx.author:
                    return
                # Add the item to the players inventory, subtract the price of the item from their balance, display purchased embed
                if self.item.name.endswith('seed'):
                    await ctx.bot.dbfarms.update_one({"_id": user.user_id}, {"$inc": {self.item.name + 's': 1}})
                else:
                    await inventory.add_item(self.item.name, 1, self.item.durability)
                await user.update_balance(-self.item.price)
                new_balance = await user.check_balance('bits')
                for x in self.shop_view.children:
                    if x.label == "Go back":
                        pass
                    else:
                        if x.item not in seeds:
                            if await inventory.get(x.item.name):
                                x.style = discord.ButtonStyle.grey
                                x.label = "Owned"
                                x.disabled = True
                        if x.item.price > new_balance:
                            x.disabled = True
                            x.style = discord.ButtonStyle.grey
                await interaction.response.edit_message(view=self.shop_view)

        # ALL EMBEDS THAT WILL HAVE THE ITEMS LISTED BENEATH THEM
        tools_embed = discord.Embed(title="Shop for Tools!",
                                    description="Buy some tools that will allow you to dig, mine, or fish!\n*They're worth it, I promise.*",
                                    color=discord.Color.blue())
        for tool in tools:
            tools_embed.add_field(name=tool.name.replace('_', ' '), value='{:,}'.format(tool.price))
        seeds_embed = discord.Embed(title="Shop for Seeds!",
                                    description="Buy some seeds to plant.\n*Nothing special about these.*",
                                    color=discord.Color.brand_green())
        for seed in seeds:
            seeds_embed.add_field(name=seed.name.replace('_', ' '), value='{:,}'.format(seed.price))

        class GoBackButton(discord.ui.Button):
            def __init__(self, ctx, label, style, row):
                super().__init__(label=label, style=style, row=row)
                self.ctx = ctx

            async def callback(self, interaction):
                if interaction.user != ctx.author:
                    return
                await interaction.response.edit_message(embed=menu_page, view=ShopSectionSelect())
        go_back_button = GoBackButton(ctx, "Go back", discord.ButtonStyle.blurple, 2)

        # Function to add all items as buttons to each page
        buttons = {}
        async def add_buttons(view, items):
            balance = await user.check_balance('bits')
            for x in items:
                label = x.name.replace('_', ' ')
                if items != seeds:
                    if await inventory.get(x.name):
                        style = discord.ButtonStyle.grey
                        label = "Owned"
                        disabled = True
                    else:
                        if balance >= x.price:
                            style = discord.ButtonStyle.green
                            disabled = False
                        else:
                            style = discord.ButtonStyle.grey
                            disabled = True
                else:
                    if balance >= x.price:
                        style = discord.ButtonStyle.green
                        disabled = False
                    else:
                        style = discord.ButtonStyle.grey
                        disabled = True
                buttons[x.name] = ButtonCreation(ctx, label, style, x.name, disabled, item=x, shop_view=view)
                view.add_item(buttons[x.name])
            view.add_item(go_back_button)

        # CLASSES FOR EACH SHOP PAGE
        class ToolSelection(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)

        class SeedSelection(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)


        # Class to select what type of shop you want to open!
        class ShopSectionSelect(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)

            # Exit button to close the shop
            @discord.ui.button(label='Exit', style=discord.ButtonStyle.red, row=2)
            async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                await menu_message.delete()
                await ctx.message.delete()
                self.stop()

            # Button to choose the tools section
            @discord.ui.button(label='Tools', style=discord.ButtonStyle.green, custom_id='tools')
            async def tools_section_select(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                # Create the view and add the buttons
                tool_view = ToolSelection()
                await add_buttons(tool_view, tools)
                await interaction.response.edit_message(embed=tools_embed, view=tool_view)

            # Button to choose the seeds section
            @discord.ui.button(label='Seeds', style=discord.ButtonStyle.green, custom_id='seeds')
            async def seeds_section_select(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    return
                # Create the view and add the buttons
                seed_view = SeedSelection()
                await add_buttons(seed_view, seeds)
                await interaction.response.edit_message(embed=seeds_embed, view=seed_view)

        menu_page = discord.Embed(
            title="Shop Select",
            description="Choose which section you would like to shop from!",
            color=discord.Color.teal()
        )
        menu_message = await ctx.send(embed=menu_page, view=ShopSectionSelect())

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
