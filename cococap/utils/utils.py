import random
import discord

from datetime import datetime
from cococap.user import User
from cococap.item_models import Master

from cococap.constants import Rarities
from logging import getLogger

log = getLogger(__name__)


# Delay drops until half hour
def seconds_until_tasks():
    minutes = random.randint(20, 40)
    current_time = datetime.now()
    time_until = minutes - current_time.minute
    if time_until == 0:
        return 0
    elif time_until < 0:
        minutes = current_time.minute + random.randint(5, 20)
        time_until = minutes - current_time.minute
    return (time_until * 60) - current_time.second


field_formats = {
    # General fields section
    "item_id": {"text": "**Item ID**: *{:}*"},
    "item_type": {"text": "**Type**: *{:}*"},
    "rarity": {"text": "**Rarity**: *{:}*", "shop_field": True, "rarity": True},
    "consumable": {"text": "**Single Use**: *{:}*"},
    "is_material": {"text": "**Material**: *{:}*"},
    "skill": {"text": "**Category**: *{:}*"},
    "drop_rate": {"text": "**Drop Rate**: 1/*{:,}*"},
    "min_drop": {"text": "**Min Roll**: *{:,}*"},
    "max_drop": {"text": "**Max Roll**: *{:,}*"},
    # Crop specific section
    "pet_xp": {"text": "**Pet XP**: *{:,}*", "shop_field": True},
    "min_harvest": {"text": "**Min Harvest**: *{:,}*"},
    "max_harvest": {"text": "**Max Harvest**: *{:,}*"},
    "grows_from": {
        "text": "**Grows From**: *{:}*",
        "shop_field": True,
        "get_display_name": True,
    },
    # Seed specific section
    "growth_odds": {"text": "**Growth Time**: ~*{:,}* cycles", "shop_field": True},
    "grows_into": {
        "text": "**Grows Into**: *{:}*",
        "shop_field": True,
        "get_display_name": True,
    },
    # Tool specific section
    "power": {"text": "**Power**: *{:,}*", "shop_field": True},
    # Pet specific section
    "max_level": {"text": "**Max Level**: *{:,}*", "shop_field": True},
    "work_bonus": {"text": "**Work Bonus**: *{:,}* bits", "shop_field": True},
    "daily_bonus": {"text": "**Daily Bonus**: *{:,}* tokens", "shop_field": True},
    # Rank specific section
    "emoji": {"text": "**Emoji**: *{:}*"},
    "token_price": {"text": "**Price**: *{:,}* tokens", "shop_field": True},
    "wage": {"text": "**Wage**: *{:,}* bits", "shop_field": True},
    "next_rank_id": {"text": "**Next Rank**: *{:}*", "shop_field": True},
    # Area specific section
    "difficulty": {"text": "**Difficulty**: *{:,}* :star:"},
    "token_bonus": {"text": "**Daily Bonus**: *{:,}* tokens"},
    "fuel_requriement": {"text": "**Fuel Type**: *{:}*"},
    "fuel_amount": {"text": "**Req. Fuel**: *{:,}*"},
    # Bottom formatting
    "price": {"text": "**Price**: *{:,}*", "shop_field": True},
    "sell_price": {"text": "**Sell Price**: *{:,}*"},
}


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
        title=item_data.display_name,
        description=item_data.description,
    )

    def format_value(value, embed: discord.Embed):
        """Takes an unformatted value and formats it by specific tags"""
        if field_formats.get("rarity"):
            rarity = Rarities.from_value(value)
            formatted_value = rarity.rarity_name
            embed.color = discord.Color.from_str(rarity.color)
        else:
            log.debug(f"No fields to be formatted, returning original value: {value}")
            return value
        log.debug(f"Finished formatting value: {formatted_value}")
        return formatted_value

    def construct_stats_string(item_data: dict, for_shop: bool):
        """Constructs a string filled with item information."""
        stats_string = ""
        for field_name in field_formats.keys():
            # For loop will add the fields based on order set in field_formats
            if field_name in item_data:
                value = item_data[field_name]
                field_format = field_formats[field_name]
                # Update any values based on their field_format
                value = format_value(value, field_format, embed)
                if for_shop and not "shop_field" in field_format:
                    # Only accept shop_fields if for_shop is True
                    log.debug(f"for_shop == {for_shop} and no shop_field, skipping")
                    continue
                # Add the formatted information to the a string
                if value is not None:
                    stats_string += field_format["text"].format(value) + "\n"

        return stats_string

    stats_string = construct_stats_string(item_data, for_shop)
    # Add the string to the embed under a field titled "Stats"
    embed.add_field(name="Stats", value=stats_string)
    return embed


async def check_bet(user: User, bet: int):
    """Ensures that a user is not betting invalid amounts"""
    balance = user.get_field('purse')
    if int(bet) <= 0:
        return f"I sense something fishy... Quit it.", False
    elif int(bet) > balance:
        return f"Sorry, but no loans. You only have {balance:,} bits.", False
    else:
        return "Passed", True