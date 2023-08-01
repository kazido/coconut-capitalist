import random

from datetime import datetime
from src.utils.managers import UserManager, ItemManager, DataManager


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
        item: DataManager = DataManager("master", item.item_id)
        # If a 1 is rolled, the item was dropped
        if random.randint(1, item.get_field('drop_rate')) == 1:
            quantity = skewed_random(item.get_field('min_drop'), item.get_field('max_drop'))
            drops.append({"item": item, "quantity": quantity})
    return drops


def distribute_drops(user: UserManager, item_pool, bit_multiplier=1):
    """Distribute bits and drops to a user"""
    # Generate rewards
    bits_reward = bit_multiplier * skewed_random(10, 100)
    roll = roll_drops(item_pool)
    # Distribute items to user
    for item in roll:
        ItemManager.insert_item(user.id, item["item"].get_field(), item["quantity"])
    # Distribute bits to user
    user.set_field('purse', user.get_field('purse') + bits_reward)
    return roll, bits_reward


def check_bet(user: UserManager, bet):
    """Ensures that a user is not betting invalid amounts"""
    balance = user.get_field("purse")
    if int(bet) < 0:
        return f"The oldest trick in the book... Nice try.", False
    elif int(bet) > balance:
        return f"No loans. You have {balance} bits.", False
    elif int(bet) == 0:
        return "What did you think this was going to do?", False
    else:
        return "Passed", True
