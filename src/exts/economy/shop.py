from utils.decorators import registered
from classLibrary import RequestUser
from utils.shop import SubShopPage, SubShopView, ShopView
from discord.ext import commands
from discord import app_commands
import discord
import models as mm
from constants import PROJECT_ROOT
import json


# with open(f'{PROJECT_ROOT}\projfiles\game_entities\\pets.json', 'r') as pets_file:
#     pets = json.load(pets_file)
    
# with open(f'{PROJECT_ROOT}\projfiles\game_entities\\tools.json', 'r') as tools_file:
#     tools = json.load(tools_file)
    
# with open(f'{PROJECT_ROOT}\projfiles\game_entities\\consumables.json', 'r') as consumables_file:
#     consumables = json.load(consumables_file)

class ShopCog(commands.Cog, name='Shop'):
    """Purchase helpful items on your way to the top!"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @app_commands.guilds(977351545966432306, 856915776345866240)
    @app_commands.command(name="shop", description="Buy helpful items!")
    async def shop(self, interaction: discord.Interaction):
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
        # for seed_ref_id, seed_info in consumables['SEEDS'].items():
        #     seeds_subshop_dict['pages'].append(SubShopPage(entity_ref_id=seed_ref_id, entity_info=seed_info, command_interaction=interaction))
        # for starter_item_ref_id, starter_item_info in tools['TOOLS_STARTER'].items():
        #     tools_subshop_dict['pages'].append(SubShopPage(entity_ref_id=starter_item_ref_id, entity_info=starter_item_info, command_interaction=interaction))
            
        # SubShopView(subshop_dict=tools_subshop_dict, parent_view=shop_view)
        SubShopView(subshop_dict=seeds_subshop_dict, parent_view=shop_view)
        
        
        await interaction.response.send_message(embed=shop_view.embed, view=shop_view)


async def setup(bot):
    await bot.add_cog(ShopCog(bot))
