import datetime
import discord

from discord.ext import commands
from discord import app_commands
from discord.ext import tasks

from cococap.user import User
from cococap.utils.shop import SubShopPage, ItemPage, ItemMenu
from cococap.constants import PROJECT_ROOT



class ShopCog(commands.Cog, name='Shop'):
    """Purchase helpful items on your way to the top!"""

    def __init__(self, bot):
        self.bot = bot
        self.shop_loop.start()
        
    time = datetime.time(hour=11)
    
    def cog_unload(self):
        self.shop_loop.cancel()
    
    @tasks.loop(time=time)
    async def shop_loop(self):
        pass

    
    @app_commands.command(name="shop", description="Buy helpful items!")
    async def shop(self, interaction: discord.Interaction):
        shop_view = ItemPage('corrupted_seed')
        
        await interaction.response.send_message(embed=shop_view.embed, view=shop_view)
        return
        
        shop_view = ItemMenu(interaction=interaction)
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
        ItemPage(subshop_dict=seeds_subshop_dict, parent_view=shop_view)
        
        
        await interaction.response.send_message(embed=shop_view.embed, view=shop_view)


async def setup(bot):
    await bot.add_cog(ShopCog(bot))
