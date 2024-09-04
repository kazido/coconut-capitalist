import discord

from discord.ext import commands
from discord import app_commands

from cococap.user import User
from cococap.item_models import Master
from cococap.utils.messages import Cembed


class InventoryCog(commands.Cog, name="Inventory"):
    """Check out all the useful items you own."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="Check your inventory!")
    @app_commands.guilds(977351545966432306, 856915776345866240)
    async def inventory(self, interaction: discord.Interaction):
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        inventory: dict = user.get_field("items")

        if len(inventory) == 0:
            return await interaction.response.send_message(
                "You don't have any items!", ephemeral=True
            )

        inventory_embed = Cembed(
            title=f"{interaction.user.name}'s Inventory",
            desc="",
            color=discord.Color.from_rgb(153, 176, 162),
            interaction=interaction,
            activity="inventory",
        )
        for k, v in inventory.items():
            data: Master = Master.get_by_id(k)
            inventory_embed.description += f"{data.emoji} {v['quantity']:,} {data.display_name}\n"

        await interaction.response.send_message(embed=inventory_embed)


async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
