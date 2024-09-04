import discord
from cococap.constants import Rarities

from cococap.item_models import Master

import random
from logging import getLogger

log = getLogger(__name__)
log.setLevel(20)

field_formats = {
    # General fields section
    "wiki": {
        "text": "{:}",
    },
    "filter_type": {
        "text": "**Type**: *{:}*",
    },
    "rarity": {
        "text": "**Rarity**: *{:}*",
        "shop_field": True,
    },
    "skill": {
        "text": "**Category**: *{:}*",
    },
    "drop_rate": {
        "text": "**Drop Rate**: 1/*{:,}*",
    },
    "min_drop": {
        "text": "**Drops at least**: *{:,}*",
    },
    "max_drop": {
        "text": "**Drops at most**: *{:,}*",
    },
    # Crop specific section
    "pet_xp": {
        "text": "**Pet XP**: *{:,}*",
        "shop_field": True,
    },
    "min_harvest": {
        "text": "**Min Harvest**: *{:,}*",
    },
    "max_harvest": {
        "text": "**Max Harvest**: *{:,}*",
    },
    "grows_from": {
        "text": "**Grows From**: *{:}*",
        "shop_field": True,
        "get_display_name": True,
    },
    # Seed specific section
    "growth_odds": {
        "text": "**Growth Time**: ~*{:,}* cycles",
        "shop_field": True,
    },
    "grows_into": {
        "text": "**Grows Into**: *{:}*",
        "shop_field": True,
        "get_display_name": True,
    },
    # Tool specific section
    "power": {
        "text": "**Power**: *{:,}*",
        "shop_field": True,
    },
    # Pet specific section
    "max_level": {
        "text": "**Max Level**: *{:,}*",
        "shop_field": True,
    },
    "work_bonus": {
        "text": "**Work Bonus**: *{:,}* bits",
        "shop_field": True,
    },
    "daily_bonus": {
        "text": "**Daily Bonus**: *{:,}* tokens",
        "shop_field": True,
    },
    # Rank specific section
    "token_price": {
        "text": "**Price**: *{:,}* tokens",
        "shop_field": True,
    },
    "wage": {
        "text": "**Wage**: *{:,}* bits",
        "shop_field": True,
    },
    "next_rank_id": {
        "text": "**Next Rank**: *{:}*",
        "shop_field": True,
    },
    # Bottom formatting
    "price": {
        "text": "**Price**: *{:,}*",
        "shop_field": True,
    },
    "sell_price": {
        "text": "**Sell Price**: *{:,}*",
    },
}


def skewed_roll(min_drop: int, max_drop: int):
    """Returns an integer between min_drop and max_drop, skewed towards min_drop."""
    # only to be used in roll_drops
    range_size = max_drop - min_drop
    roll = min_drop + round((random.random() ** 3) * range_size)
    return roll


def roll_item(item: Master):
    """Rolls item and returns the quantity"""
    # If a 1 is rolled, the item was dropped
    if random.randint(1, item.drop_rate) == 1:
        quantity = skewed_roll(item.min_drop, item.max_drop)
        return quantity
    return None


def get_skill_drops(skill: str):
    """Returns a dictionary of all items related to the passed skill"""
    drops = {}
    query = Master.select().where(Master.skill.contains(skill))
    for item in query:
        # Add the item in to the dict by it's item_id
        drops[item.item_id] = item
    return drops


def item_attributes(item_data: dict, for_shop: bool):
    """Constructs a string filled with item information."""
    attributes = ""
    for field_name in item_data:
        if field_name in field_formats.keys():
            value = item_data[field_name]
            if field_name == "rarity":
                rarity = Rarities.from_value(value)
                value = rarity.rarity_name
            if not value or (for_shop and not "shop_field" in formatting):
                continue
            formatting = field_formats[field_name]
            attributes += formatting["text"].format(value) + "\n"

    return attributes


def construct_embed(item_id, for_shop: bool):
    """Constructs an embed filled with formatted data about the item that is passed.

    Args:
        item_id: The item ID to create an embed for.
        for_shop (bool): If True, will only add fields needed for the shop.

    Returns:
        discord.Embed: An embed filled with the items data.
    """
    item_data: Master = Master.get_by_id(item_id)

    # Create an embed with the proper information from the item
    embed = discord.Embed(
        title=f"{item_data.emoji} {item_data.display_name}",
        description=f'"*{item_data.description}*"',
    )
    divider = "-" * (len(embed.description) - 2)
    embed.description += f"\n{divider}\n"
    rarity = Rarities.from_value(item_data.rarity)
    embed.color = discord.Color.from_str(rarity.color)
    embed.set_footer(text=f"Wiki: {item_id}")

    attributes = item_attributes(item_data.__dict__["__data__"], for_shop)
    embed.set_thumbnail(url=discord.PartialEmoji.from_str(item_data.emoji).url)
    # Add the string to the embed under a field titled "Stats"
    embed.description += attributes
    return embed
