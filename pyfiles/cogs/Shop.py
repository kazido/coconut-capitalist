from cogs.ErrorHandler import registered
from classLibrary import RequestUser, Inventory
from classLibrary import tools, consumables
from discord.ext import commands
from discord import app_commands
import discord
import myModels as mm


class ShopCog(commands.Cog, name='Shop'):
    """Purchase helpful items on your way to the top!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @app_commands.guilds(977351545966432306, 856915776345866240)
    @app_commands.command(name="shop", description="Buy helpful items!")
    async def shop(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction) # User information
        inventory = Inventory(interaction)
        
        menu_page = discord.Embed(
            title="Shop Select",
            description="Choose which section you would like to shop from!",
            color=discord.Color.teal()
        )

        # Class for subclassing buttons for purchasing items
        # class ButtonCreation(discord.ui.Button):
        #     def __init__(self, ctx, label, style, custom_id, disabled, item, shop_view):
        #         super().__init__(label=label, style=style, custom_id=custom_id, disabled=disabled)
        #         self.ctx = ctx
        #         self.item = item
        #         self.shop_view = shop_view

        #     async def callback(self, button_interaction):
        #         if button_interaction.user != interaction.user:
        #             return
        #         # Add the item to the players inventory, subtract the price of the item from their balance, display purchased embed
        #         if self.item.name.endswith('seed'):
        #             user_farm = mm.Farms.select().where(id=interaction.user.id)
        #             if self.item:
        #         else:
        #             await inventory.add_item(self.item, 1)
        #         await user.update_balance(-self.item.price)
        #         new_balance = await user.check_balance('bits')
        #         for x in self.shop_view.children:
        #             if x.label == "Go back":
        #                 pass
        #             else:
        #                 if x.item not in seeds:
        #                     if await inventory.get(x.item.name):
        #                         x.style = discord.ButtonStyle.grey
        #                         x.label = "Owned"
        #                         x.disabled = True
        #                 if x.item.price > new_balance:
        #                     x.disabled = True
        #                     x.style = discord.ButtonStyle.grey
        #         await interaction.response.edit_message(view=self.shop_view)

        # class GoBackButton(discord.ui.Button):
        #     def __init__(self):
        #         super().__init__(label='Go back', style=discord.ButtonStyle.blurple, row=2)

        #     async def callback(self, go_back_interaction):
        #         if interaction.user != go_back_interaction.user:
        #             return
        #         await interaction.edit_original_response(embed=menu_page, view=ShopSectionSelect())

        # # Function to add all items as buttons to each page
        # buttons = {}

        # async def add_buttons(view, items):
        #     balance = await user.check_balance('bits')
        #     for x in items:
        #         label = x.name.replace('_', ' ')
        #         if items != seeds:
        #             if await inventory.get(x.name):
        #                 style = discord.ButtonStyle.grey
        #                 label = "Owned"
        #                 disabled = True
        #             else:
        #                 if balance >= x.price:
        #                     style = discord.ButtonStyle.green
        #                     disabled = False
        #                 else:
        #                     style = discord.ButtonStyle.grey
        #                     disabled = True
        #         else:
        #             if balance >= x.price:
        #                 style = discord.ButtonStyle.green
        #                 disabled = False
        #             else:
        #                 style = discord.ButtonStyle.grey
        #                 disabled = True
        #         buttons[x.name] = ButtonCreation(ctx, label, style, x.name, disabled, item=x, shop_view=view)
        #         view.add_item(buttons[x.name])
        #     view.add_item(go_back_button)

        # CLASSES FOR EACH SHOP PAGE
        class ToolSelection(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)
                self.tools_embed = discord.Embed(title="Shop for Tools!",
                                        description="Buy some tools that will allow you to dig, mine, or fish!\n*They're worth it, I promise.*",
                                        color=discord.Color.blue())
                for tool in tools:
                    self.tools_embed.add_field(name=tools[tool]['item_name'], value=f"{tools[tool]['buy_price']:,}")
            
            async def on_timeout(self) -> None:
                try:
                    await interaction.delete_original_response()
                except discord.errors.NotFound:
                    pass
            
        class SeedSelection(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)
                self.seeds_embed = discord.Embed(title="Shop for Seeds!",
                                        description="Buy some seeds to plant.\n*Nothing special about these.*",
                                        color=discord.Color.brand_green())
                for key, value in consumables.items():
                    if key.startswith('SEED'):
                        self.seeds_embed.add_field(name=value['item_name'], value=f"{value['price']:,}")

        # Class to select what type of shop you want to open!
        class ShopSectionSelect(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)
                views = [SeedSelection(), ToolSelection()]
                for view in views:
                    self.add_item(view)
                self.add_item(ExitButton())

        class SwitchToToolsShop(discord.ui.Button):
            def __init__(self, row=1):
                super().__init__(label="Tools", style=discord.ButtonStyle.blurple, row=row)

            async def callback(self, switch_to_tools_interaction: discord.Interaction):
                if switch_to_tools_interaction.user != interaction.user:
                    return
                self.view.stop()
                new_view = ToolSelection()
                await switch_to_tools_interaction.response.edit_message(embed=new_view.tools_embed, view=new_view)
        
        class SwitchToSeedsShop(discord.ui.Button):
            def __init__(self, row=1):
                super().__init__(label="Tools", style=discord.ButtonStyle.blurple, row=row)

            async def callback(self, switch_to_seeds_interaction: discord.Interaction):
                if switch_to_seeds_interaction.user != interaction.user:
                    return
                self.view.stop()
                new_view = SeedSelection()
                await switch_to_seeds_interaction.response.edit_message(embed=new_view.seeds_embed, view=new_view)

        class ExitButton(discord.ui.Button):
            def __init__(self, row=1):
                super().__init__(label="Exit", style=discord.ButtonStyle.red, row=row)

            async def callback(self, exit_interaction: discord.Interaction):
                if exit_interaction.user != interaction.user:
                    return
                await interaction.delete_original_response()
                self.view.stop()
            
        menu_message = await interaction.response.send_message(embed=menu_page, view=ShopSectionSelect())
                
async def setup(bot):
    await bot.add_cog(ShopCog(bot))
