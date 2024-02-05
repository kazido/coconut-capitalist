import discord

from discord.ext import commands
from discord import app_commands

from cococap.user import User
from cococap.item_models import Master
from cococap.utils.messages import Cembed
from cococap.utils.items import create_item, delete_item, trade_item
from cococap.utils.utils import construct_embed


class InventoryCog(commands.Cog, name='Inventory'):
    """Check out all the useful items you own."""

    def __init__(self, bot):
        self.bot = bot
        
    # Class for managing the items database
    class Inventory:
        def __init__(self):
            pass

        def add_item(self, reference_id, reference_dict: dict, quantity: int = 1):
            exisiting_item = m.Items.get_or_none(owner_id=self.interaction.user.id, reference_id=reference_id)
            if exisiting_item:
                exisiting_item.quantity += quantity
                exisiting_item.save()
            else:
                m.Items.insert(durability=reference_dict[reference_id]['durability'], 
                                item_name=reference_dict[reference_id]['item_name'], 
                                owner_id=self.interaction.user.id, quantity=quantity, reference_id=reference_id)

        # def remove_item(self, item, quantity=None):
        #     if isinstance(quantity, int):
        #         check_remaining_items_statement = """SELECT quantity FROM items WHERE owner_id = ? and item_name = ?"""
        #         self.cursor.execute(check_remaining_items_statement, [self.user_id, item.name])
        #         remaining_items = self.cursor.fetchall()[0][0]
        #         if remaining_items - quantity >= 0:
        #             delete_item_statement = """DELETE FROM items WHERE owner_id = ? and item_name = ?"""
        #             self.cursor.execute(delete_item_statement, [quantity, self.user_id, item.name])
        #         else:
        #             update_quantity_statement = """UPDATE items SET quantity = quantity - ? WHERE owner_id = ? and item_name = ?"""
        #             self.cursor.execute(update_quantity_statement, [quantity, self.user_id, item.name])
        #         self.sqliteConnection.commit()
        #     else:
        #         delete_item_statement = """DELETE FROM items WHERE owner_id = ? and item_name = ?"""
        #         self.cursor.execute(delete_item_statement, [quantity, self.user_id, item.name])
        #         self.sqliteConnection.commit()

        def find(self, reference_id=None):
            if reference_id:
                exisiting_item = m.Items.get_or_none(m.Items.owner_id==self.interaction.user.id, m.Items.reference_id==reference_id)
                if exisiting_item:
                    return exisiting_item.objects()
                else:
                    return False
            query = m.Items.select().where(m.Items.owner_id==self.interaction.user.id)
            return query.objects()

    
    @app_commands.command(name="inventory", description="Check your inventory!")
    @app_commands.guilds(977351545966432306, 856915776345866240)
    async def inventory(self, interaction: discord.Interaction):
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        
        inventory: dict = user.get_field('items')
        
        if len(inventory) == 0:
            desc = "You don't have any items!"
        else:
            desc = None

        inventory_embed = Cembed(
            title=f"{interaction.user.name}'s Inventory",
            desc=desc,
            color=discord.Color.from_rgb(153, 176, 162),
            interaction=interaction, activity="inventory"
        )
        for k, v in inventory.items():
            data: Master = Master.get_by_id(k)
            inventory_embed.add_field(name=data.display_name, value=v['quantity'])
            
        await interaction.response.send_message(embed=inventory_embed)
        
    @app_commands.command(name="wiki", description="What is this item?")
    @app_commands.guilds(977351545966432306, 856915776345866240)
    async def wiki(self, interaction: discord.Interaction, item_id: str):
        embed: discord.Embed = construct_embed(item_id, for_shop=False)
        await interaction.response.send_message(embed=embed)
        return
        

async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
