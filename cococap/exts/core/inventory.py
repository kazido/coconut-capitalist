import discord

from discord import app_commands
from discord.ext import commands

from cococap.errors import CustomError
from cococap.models.instance import ItemInstance
from cococap.registry import get_registry
from cococap.screens import open_screen
from cococap.services.equipment import TOOL_FOR_SKILL, EquipmentError, equip
from cococap.user import User
from utils.custom_embeds import CustomEmbed
from utils.items.items import item_autocomplete
from utils.menus import Menu, MenuHandler, PaginationMenu

from cococap.services.inventory import (  # noqa: F401  (re-exported for callers/tests)
    PER_PAGE,
    instance_label,
    instance_lines,
    inventory_lines,
)


class InventoryCog(commands.Cog, name="Inventory"):
    """Check out all the useful items you own."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="Check your inventory!")
    async def inventory(self, interaction: discord.Interaction):
        await open_screen(interaction, "inventory")

    @app_commands.command(name="equip", description="Equip one of your tools.")
    @app_commands.describe(tool="the tool to equip")
    async def equip(self, interaction: discord.Interaction, tool: int):
        user = await User.get(interaction.user.id)
        instance = await user.instance(tool)
        if instance is None:
            raise CustomError("You don't own a tool with that id.")
        kind = get_registry().item(instance.template_id).tool
        skill = next((s for s, k in TOOL_FOR_SKILL.items() if kind and k == kind.kind), None)
        if skill is None:
            raise CustomError("That can't be equipped.")
        try:
            await equip(user, skill, tool)
        except EquipmentError as e:
            raise CustomError(str(e)) from e
        await interaction.response.send_message(
            f"Equipped **{instance_label(instance)}** for {skill}.", ephemeral=True
        )

    @equip.autocomplete("tool")
    async def _equip_autocomplete(self, interaction: discord.Interaction, current: str):
        user = await User.get(interaction.user.id)
        needle = current.lower()
        return [
            app_commands.Choice(name=instance_label(i)[:100], value=i.id)
            for i in await user.instances()
            if needle in instance_label(i).lower()
        ][:25]


async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
