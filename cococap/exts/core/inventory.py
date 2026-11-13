import discord

from discord import app_commands
from discord.ext import commands

from cococap.errors import CustomError
from cococap.models.instance import ItemInstance
from cococap.registry import get_registry
from cococap.services.equipment import TOOL_FOR_SKILL, EquipmentError, equip
from cococap.user import User
from utils.custom_embeds import CustomEmbed
from utils.items.items import item_autocomplete
from utils.menus import Menu, MenuHandler, PaginationMenu

PER_PAGE = 15


def inventory_lines(items: dict[str, int], filter: str | None = None) -> list[str]:
    """One display line per stack in `items` ({item_id: quantity}), sorted by item name.

    `filter` matches (case-insensitively) an item's name, id, skill or category. Ids missing from
    the registry (renamed/removed items) are still listed, never crash the command.
    """
    reg = get_registry()
    needle = filter.lower() if filter else None
    rows = []
    for item_id, quantity in items.items():
        if quantity <= 0:
            continue
        item = reg.find_item(item_id)
        if item is None:
            if needle is None or needle in item_id.lower():
                rows.append((item_id, f"❔ {quantity:,} {item_id} *(unknown item)*"))
            continue
        if needle and not any(
            needle in field for field in (item.name.lower(), item.id, item.skill or "", item.category)
        ):
            continue
        rows.append((item.name.lower(), f"{item.emoji or '▫️'} {quantity:,} {item.name}"))
    return [line for _, line in sorted(rows)]


def instance_label(instance: ItemInstance) -> str:
    """e.g. "Starter Axe #4 [Soloist]" -- the id disambiguates identical-looking tools."""
    reg = get_registry()
    template = reg.item(instance.template_id)
    enchants = ", ".join(
        f"{reg.enchants[e].name if e in reg.enchants else e}"
        + (f" {lvl}" if lvl > 1 else "")
        for e, lvl in sorted(instance.enchants.items())
    )
    return f"{template.name} #{instance.id}" + (f" [{enchants}]" if enchants else "")


def instance_lines(instances: list[ItemInstance], equipped_ids: set[int], filter: str | None = None) -> list[str]:
    reg = get_registry()
    needle = filter.lower() if filter else None
    rows = []
    for inst in instances:
        template = reg.find_item(inst.template_id)
        if template is None:
            continue
        label = instance_label(inst)
        if needle and not any(
            needle in field for field in (label.lower(), template.id, template.skill or "", "tool")
        ):
            continue
        mark = " ✅" if inst.id in equipped_ids else ""
        rows.append((label.lower(), f"{template.emoji or '🗡️'} {label}{mark}"))
    return [line for _, line in sorted(rows)]


class InventoryCog(commands.Cog, name="Inventory"):
    """Check out all the useful items you own."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="Check your inventory!")
    @app_commands.describe(filter="only show items matching this name, skill or type")
    async def inventory(self, interaction: discord.Interaction, filter: str | None = None):
        user = await User.get(interaction.user.id)
        items = await user.items()
        instances = await user.instances()
        equipped = set()
        for skill in TOOL_FOR_SKILL:
            equipped_id = (await user.skill(skill)).equipped_instance_id
            if equipped_id is not None:
                equipped.add(equipped_id)
        lines = instance_lines(instances, equipped, filter) + inventory_lines(items, filter)

        if not lines:
            message = (
                f"*No items found using this filter:* {filter}"
                if filter and (items or instances)
                else "You don't have any items! Get to it!"
            )
            return await interaction.response.send_message(message, ephemeral=True)

        pages = [lines[i : i + PER_PAGE] for i in range(0, len(lines), PER_PAGE)]
        handler = MenuHandler(interaction=interaction)
        for number, page in enumerate(pages, start=1):
            embed = CustomEmbed(
                title=f"{interaction.user.name}'s Inventory",
                desc="\n".join(page),
                color=discord.Color.from_rgb(153, 176, 162),
                interaction=interaction,
                activity="inventory",
            )
            if len(pages) > 1:
                embed.set_footer(text=f"Page {number}/{len(pages)}")
            handler.add_menu((PaginationMenu if len(pages) > 1 else Menu)(embed=embed))

        first = handler.get_current()
        await interaction.response.send_message(embed=first.embed, view=first)

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

    @inventory.autocomplete("filter")
    async def _filter_autocomplete(self, interaction: discord.Interaction, current: str):
        return await item_autocomplete(interaction, current)


async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
