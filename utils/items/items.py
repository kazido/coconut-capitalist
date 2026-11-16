"""Item presentation and rolling helpers, built on the typed registry (cococap.registry)."""

import random
from typing import List

import discord
from discord.app_commands import Choice

from cococap.constants import Rarities
from cococap.registry import Item, get_registry
from cococap.services.loot import roll_drop

MAX_CHOICES = 25  # Discord's limit for autocomplete results and select options


def roll_item(item: Item) -> int | None:
    """Roll `item`'s drop table once with the global RNG (services take an explicit one)."""
    return roll_drop(item, random)


def custom_emoji_url(emoji: str | None) -> str | None:
    """The image URL of a custom (<:name:id>) emoji; None for unicode or missing emoji."""
    if not emoji:
        return None
    partial = discord.PartialEmoji.from_str(emoji)
    return partial.url if partial.is_custom_emoji() else None


def item_attributes(item: Item, for_shop: bool = False) -> str:
    """A bulleted block of the item's stats. The shop shows only what matters when buying."""
    reg = get_registry()
    lines: list[str] = []

    def add(text: str, *, shop: bool = False) -> None:
        if shop or not for_shop:
            lines.append(text)

    if item.wiki:
        add(item.wiki)
    add(f"**Rarity**: {item.rarity_tag.split(' ', 1)[0]} *{Rarities.from_value(item.rarity).rarity_name}*", shop=True)
    add(f"**Type**: *{item.category.replace('_', ' ').title()}*")
    if item.skill:
        add(f"**Category**: *{item.skill.title()}*")
    if item.category == "fish":  # a fish's drop odds are a roll order, not its real chance: say where it lives instead
        from cococap.services import wiki

        if item.size:
            add(f"**Size**: *{item.size.min:g}-{item.size.max:g} cm*")
        add(f"**Where to catch it**: {wiki.where_to_catch_text(item, reg)}")
    elif item.drop:
        add(f"**Drop Rate**: 1/*{item.drop.rate:,}*")
        add(f"**Drops**: *{item.drop.min:,}*" + (f"-*{item.drop.max:,}*" if item.drop.max > item.drop.min else ""))
    if item.pet_food:
        add(f"**Pet xp**: *{reg.economy.pets.food_xp[item.pet_food.tier - 1]:,}* (tier {item.pet_food.tier}), more for a pet of its skill", shop=True)
    if item.crop:
        add(f"**Harvest**: *{item.crop.min_harvest:,}*-*{item.crop.max_harvest:,}*")
        add(f"**Pet XP**: *{item.crop.pet_xp:,}*", shop=True)
        add(f"**Grows From**: *{reg.item(item.crop.seed).name}*", shop=True)
    if item.seed:
        add(f"**Growth Time**: ~*{item.seed.cycles:,}* cycles", shop=True)
        add(f"**Grows Into**: *{reg.item(item.seed.grows_into).name}*", shop=True)
    if item.scroll and (enchant := reg.enchants.get(item.scroll.enchant)):
        add(f"**Enchant - {enchant.name}**: {enchant.description}")
        add(f"**Goes on**: *{', '.join(enchant.applies_to)}*  ·  **Max level**: *{enchant.max_level}*")
        from cococap.services import scrolls

        if found := scrolls.scroll_skills(item.id, reg):
            add(f"**Found while**: *{', '.join(found)}* (a rare find, about one scroll per few hours of play in each)")
    if item.tool:
        add(f"**Power**: *{item.tool.power:,}*", shop=True)
        if item.tool.requirement:
            add(f"**Requires level**: *{item.tool.requirement}*", shop=True)
        if item.tool.ability_name:
            add(f"**Ability - {item.tool.ability_name}**: {item.tool.ability_description}", shop=True)
    if item.buyable:
        add(f"**Price**: *{item.price:,}*", shop=True)
    if item.sellable:
        add(f"**Sell Price**: *{item.sell_price:,}*")
    return "\n".join(lines)


def construct_embed(item_id: str, for_shop: bool = False) -> discord.Embed:
    """An embed describing the item.

    Args:
        item_id: The registry id of the item.
        for_shop: If True, only the fields relevant to buying are shown.
    """
    item = get_registry().item(item_id)
    description = f'"*{item.description}*"' if item.description else ""
    embed = discord.Embed(
        title=item.display,
        description=f"{description}\n{'-' * 20}\n{item_attributes(item, for_shop)}".strip(),
        color=discord.Color.from_str(Rarities.from_value(item.rarity).color),
    )
    embed.set_footer(text=f"Wiki: {item.id}")
    if url := custom_emoji_url(item.emoji):
        embed.set_thumbnail(url=url)
    return embed


def _matching(items, current: str) -> List[Choice[str]]:
    needle = current.lower()
    return [
        Choice(name=i.name, value=i.id) for i in items if needle in i.name.lower() or needle in i.id
    ][:MAX_CHOICES]


async def item_autocomplete(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    """Autocomplete over every item (Discord allows at most 25 results)."""
    return _matching(get_registry().items.values(), current)


async def buyable_autocomplete(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    return _matching(get_registry().shop_items(), current)
