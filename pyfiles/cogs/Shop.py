from cogs.ErrorHandler import registered
from classLibrary import RequestUser, Inventory
from ViewElements import SubShopPage, SubShopView, ShopView
from discord.ext import commands
from discord import app_commands
import discord
import myModels as mm
from myModels import ROOT_DIRECTORY
import json


with open(f'{ROOT_DIRECTORY}\projfiles\game_entities\\pets.json', 'r') as pets_file:
    pets = json.load(pets_file)
    
with open(f'{ROOT_DIRECTORY}\projfiles\game_entities\\tools.json', 'r') as tools_file:
    tools = json.load(tools_file)
    
with open(f'{ROOT_DIRECTORY}\projfiles\game_entities\\consumables.json', 'r') as consumables_file:
    consumables = json.load(consumables_file)

class ShopCog(commands.Cog, name='Shop'):
    """Purchase helpful items on your way to the top!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @app_commands.guilds(977351545966432306, 856915776345866240)
    @app_commands.command(name="shop", description="Buy helpful items!")
    async def shop(self, interaction: discord.Interaction):
        # await interaction.response.send_message("I'm not done yet...", ephemeral=True)
        user = RequestUser(interaction.user.id, interaction=interaction)  # User information
        inventory = Inventory(interaction)
        
        shop_view = ShopView(command_interaction=interaction)
        tools_subshop_dict = {
            "name": "Tools",
            "emoji": '⚒️',
            "description": "Shop for some upgradable tools that will start you on your journey through various skills.",
            "pages": []
        }
        seeds_subshop_dict = {
            "name": "Seeds",
            "emoji": '🌱',
            "description": "Seeds will grow into crops which can be used for feeding your pet or reselling for profit!",
            "pages": []
        }
        for seed_ref_id, seed_info in consumables['SEEDS'].items():
            seeds_subshop_dict['pages'].append(SubShopPage(entity_ref_id=seed_ref_id, entity_info=seed_info, command_interaction=interaction))
        for starter_item_ref_id, starter_item_info in tools['TOOLS_STARTER'].items():
            tools_subshop_dict['pages'].append(SubShopPage(entity_ref_id=starter_item_ref_id, entity_info=starter_item_info, command_interaction=interaction))
            
        tools_subshop = SubShopView(subshop_dict=tools_subshop_dict, parent_view=shop_view)
        seeds_subshop = SubShopView(subshop_dict=seeds_subshop_dict, parent_view=shop_view)
        
        
        await interaction.response.send_message(embed=shop_view.embed, view=shop_view)
        
       
        # def add_button(view, parent_dict, item_ref_id):
        #     user_balance = user.instance.money
        #     label = parent_dict[item_ref_id]['item_name'].capitalize()
        #     if item_ref_id.startswith('TOOL_') and inventory.get(item_ref_id):
        #         style = discord.ButtonStyle.grey
        #         disabled = True
        #     elif user_balance >= parent_dict[item_ref_id]['price']:
        #         style = discord.ButtonStyle.green
        #         disabled = False
        #     else:
        #         style = discord.ButtonStyle.grey
        #         disabled = True

        #     new_button = PurchaseItemButton(
        #         item_ref_id, parent_dict, label=label, button_disabled=disabled, button_style=style)
        #     view.add_item(new_button)

        # # Class for subclassing buttons for purchasing items
        # class PurchaseItemButton(discord.ui.Button):
        #     def __init__(self, item_ref_id, parent_dict, label, button_disabled, button_style):
        #         if item_ref_id.startswith('TOOL_'):
        #             item_exists = mm.Items.get_or_none(
        #                 owner_id=interaction.user.id, reference_id=item_ref_id)
        #             if item_exists:
        #                 self.button_label = 'Out of Stock'
        #                 self.button_emoji = '🚫'
        #             else:
        #                 self.button_label = parent_dict[item_ref_id]['item_name']
        #                 self.button_emoji = None
        #         elif item_ref_id.startswith(('CROP', 'SEED')):
        #             self.button_label = parent_dict[item_ref_id]['item_name']
        #             self.button_emoji = parent_dict[parent_dict[item_ref_id]
        #                                             ['grows_into']]['emoji']
        #         self.item_ref_id = item_ref_id
        #         self.parent_dict = parent_dict
        #         if label:
        #             self.button_label = label
        #         else:
        #             self.button_label = self.parent_dict[self.item_ref_id]['item_name']
        #         super().__init__(label=self.button_label,
        #                          style=button_style, disabled=button_disabled)

        #     async def callback(self, purchase_interaction: discord.Interaction):
        #         if purchase_interaction.user != interaction.user:
        #             return
        #         await purchase_interaction.response.send_message("This isn't finished yet.", ephemeral=True)

        #         # Add the item to the players inventory, subtract the price of the item from their balance, display purchased embed
        #         # item_price = self.parent_dict[self.item_ref_id]['price']
        #         # await user.update_balance(-item_price)

        # # View that contains the Tools Shop
        # class ToolShopView(discord.ui.View):
        #     tool_categories = {}
        #     for key, value in tools.items():  # Adds all categories and items into a dictionary
        #         tool_category = key.rsplit('_', 1)[0].split('_', 1)
        #         try:
        #             tool_categories[tool_category[1]][key] = value
        #         except KeyError:  # If the category hasn't been added yet
        #             tool_categories[tool_category[1]] = {}
        #             tool_categories[tool_category[1]][key] = value
        #     for key in tool_categories.keys():  # Adds an embed for each category
        #         embed = discord.Embed(title=f"Looking for {key.lower()}s?",
        #                                 description=f"Tools have unlimited durability and will give you their respective XP.\n\
        #                                                                 All tools can be resold for 80% of their buy price.",
        #                                 color=discord.Color.blue())
        #         for value in tool_categories[key].values():  # Adds a field for each tool in the category
        #             embed.add_field(name=value['item_name'], value=f"**{value['price']:,}** bits\n"
        #                                                                         f"Power: {value['power']}")
        #         embed.set_author(name=f"{interaction.user.name} - Shopping for {key.lower()}s",
        #                                 icon_url=interaction.user.display_avatar)
        #         tool_categories[key]['view_embed'] = embed
                
        #     def __init__(self, timeout=180):
        #         super().__init__(timeout=timeout)
        #         self.current_page = 0
        #         self.view_embed = list(ToolShopView.tool_categories.values())[self.current_page]['view_embed']
        #         self.update_buttons(tools_dict=list(ToolShopView.tool_categories.values())[self.current_page])
        #         self.add_item(Paginator_Backward_Button(interaction, ToolShopView.tool_categories.values()))
        #         self.add_item(GoBackButton(row=1))
        #         self.add_item(Paginator_Forward_Button(interaction, ToolShopView.tool_categories.values()))
                
                    
        #     def update_buttons(self, tools_dict):
        #         for child in self.children:
        #             if child.row == 1:
        #                 continue
        #             self.remove_item(child)
        #         for key, value in tools_dict.items():
        #             if type(value) == discord.embeds.Embed:
        #                 continue
        #             add_button(self, tools, key)
        #         return self

        #     async def on_timeout(self) -> None:
        #         await ShopSelectView.on_timeout(self=self)

        # # View that contains the Seeds Shop
        # class SeedShopView(discord.ui.View):
        #     def __init__(self, *, timeout=20):
        #         super().__init__(timeout=timeout)
        #         self.view_embed = discord.Embed(title="Shop for Seeds!",
        #                                         description="Buy some seeds to plant.\n*Grown crops can be used to sell for profit or feed to pets.*",
        #                                         color=discord.Color.brand_green())
        #         self.view_embed.set_author(name=f"{interaction.user.name} - Shopping for seeds",
        #                                 icon_url=interaction.user.display_avatar)
        #         for key, value in consumables.items():
        #             if key.startswith('SEED'):
        #                 self.view_embed.add_field(
        #                     name=f"{value['item_name'].capitalize()} {consumables[value['grows_into']]['emoji']}", value=f"{value['price']:,}")
        #                 add_button(self, consumables, key)
        #         self.add_item(GoBackButton())

        #     async def on_timeout(self) -> None:
        #         await ShopSelectView.on_timeout(self=self)

        


async def setup(bot):
    await bot.add_cog(ShopCog(bot))
