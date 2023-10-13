import random
import discord

from datetime import datetime

from src.item_models import DataMaster, field_formats

from src.utils.items import get_item_data, get_item_display_name, create_entity
from src.utils.members import get_user_data, set_user_field

from src.constants import Rarities
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


def skewed_random(min_drop, max_drop):
    """Returns an integer between min_drop and max_drop, skewed towards min_drop"""
    range_size = max_drop - min_drop + 1
    skewed_random = min_drop + int((random.random() ** 2) * range_size)
    return skewed_random


def roll_drops(item_pool):
    """Rolls each item in an item pool and returns all items that rolled and their quantity"""
    drops = []
    # Roll each item in the pool once
    for item in item_pool:
        get_item_data(item.item_id)
        # If a 1 is rolled, the item was dropped
        if random.randint(1, item["drop_rate"]) == 1:
            quantity = skewed_random(item["min_drop"], item["max_drop"])
            drops.append({"item": item, "quantity": quantity})
    return drops


def distribute_drops(user_id, item_pool, bit_multiplier=1):
    # TODO: Fix user.get_field, UserManager has changed
    """Distribute bits and drops to a user"""
    user = get_user_data(user_id)
    # Generate rewards
    bits_reward = bit_multiplier * skewed_random(10, 100)
    roll = roll_drops(item_pool)
    # Distribute items to user
    for item in roll:
        log.info(f"User rolled {item}")
        create_entity(user_id, item["item"]["item_id"], item["quantity"])
    # Distribute bits to user
    log.info(f"User rolled {bits_reward} bits")
    set_user_field(user_id, 'purse', user['purse'] + bits_reward)
    return roll, bits_reward


def construct_embed(item_id, for_shop: bool):
    """Constructs an embed filled with formatted data about the item that is passed.

    Args:
        item_id: The item ID to create an embed for.
        for_shop (bool): If True, will only add fields needed for the shop.

    Returns:
        discord.Embed: An embed filled with the items data.
    """
    item_data = get_item_data(item_id, backrefs=True)
    log.debug(f"Retrieved {item_data} from manager with item_id: {item_id}")

    # Create an embed with the proper information from the item
    embed = discord.Embed(
        title=item_data["display_name"],
        description=item_data["description"],
    )

    def format_value(value, field_format: dict, embed: discord.Embed):
        """Takes an unformatted value and formats it by specific tags"""
        if field_format.get("get_display_name"):
            formatted_value = get_item_display_name(value)
        elif field_format.get("rarity"):
            rarity = Rarities.from_value(value)
            formatted_value = rarity.rarity_name
            embed.color = discord.Color.from_str(rarity.color)
        else:
            log.debug(f"No fields to be formatted, returning original value: {value}")
            return value
        log.debug(f"Finished formatting value: {formatted_value}")
        return formatted_value

    def construct_stats_string(item_data: dict, field_formats: dict, for_shop: bool):
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

    stats_string = construct_stats_string(item_data, field_formats, for_shop)
    # Add the string to the embed under a field titled "Stats"
    embed.add_field(name="Stats", value=stats_string)
    return embed


def check_bet(user_id, bet):
    """Ensures that a user is not betting invalid amounts"""
    user = get_user_data(user_id)
    balance = user['purse']
    if int(bet) < 0:
        return f"The oldest trick in the book... Nice try.", False
    elif int(bet) > balance:
        return f"No loans. You have {balance} bits.", False
    elif int(bet) == 0:
        return "What did you think this was going to do?", False
    else:
        return "Passed", True
