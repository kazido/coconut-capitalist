from cococap.user import User
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
    # Area specific section
    "difficulty": {
        "text": "**Difficulty**: *{:,}* :star:",
    },
    "token_bonus": {
        "text": "**Daily Bonus**: *{:,}* tokens",
    },
    "fuel_requriement": {
        "text": "**Fuel Type**: *{:}*",
    },
    "fuel_amount": {
        "text": "**Req. Fuel**: *{:,}*",
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
