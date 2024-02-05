from cococap.user import User
from cococap.item_models import Master

import random
from logging import getLogger

log = getLogger(__name__)
log.setLevel(20)


async def create_item(owner: User, item_id: str, quantity: int = 1):
    """Inserts an item into the database with specified owner and quantity"""

    inventory: dict = owner.get_field("items")

    # Ensure that the item is an actual item first
    if not Master.get_or_none(item_id=item_id):
        log.warn(f"Tried to create: {quantity} {item_id}. Error: item does not exist.")
        return False, f"'{item_id}' is not a valid item id."
    if quantity < 1:
        log.warn(f"Tried to create {quantity} {item_id}. Less than 1.")
        return False
    # Retrieve or create the item in the database
    if item_id not in inventory.keys():
        inventory[item_id] = {"quantity": quantity}
        log.info(f"{quantity} new {item_id} created with owner: {owner}.")
        await owner.save()
        return True
    else:
        # If an item was found, add to it's quantity
        inventory[item_id]["quantity"] += quantity
        log.info(f"Added {quantity} {item_id} to: {owner}")
        await owner.save()
        return True


async def delete_item(owner: User, item_id: str, quantity: int = None):
    inventory: dict = owner.get_field("items")
    # Ensure that the item is an actual item first
    if not Master.get_or_none(item_id=item_id):
        log.warn(f"Tried to delete: {item_id}. Error: not a valid item id.")
        return False, f"'{item_id}' is not a valid item id."
    if quantity < 1:
        log.warn(f"Tried to delete: {quantity} {item_id}. Error: less than 1.")
    if item_id in inventory.keys():
        # Try to decrement quantity of existing item
        if quantity and (inventory[item_id]["quantity"] - quantity > 0):
            inventory[item_id]["quantity"] -= quantity
            log.info(f"Deleted {quantity} {item_id} from {owner}.")
            await owner.save()
            return True
        else:
            inventory.pop(item_id)
            log.info(f"Deleted all {item_id} from {owner}.")
            await owner.save()
            return True
    else:
        # If item doesn't exist, do nothing
        log.warn(f"Tried to delete {quantity} {item_id} from {owner}. Does not exist.")
        return False


async def trade_item(owner: User, new_owner: int, item_id: str, quantity: int = None):
    user_2 = User(uid=new_owner)
    await user_2.load()

    inventory: dict = owner.get_field("items")
    inventory_2: dict = user_2.get_field("items")

    # Ensure that the item is an actual item first
    if not Master.get_or_none(item_id=item_id):
        log.warn(f"Tried to trade: {item_id}. Error: not a valid item id.")
        return False
    if item_id in inventory.keys():
        # Transfer the ownership of the item if it exists
        item = inventory[item_id]
        if quantity:
            if quantity > item["quantity"]:
                log.warn(
                    f"Trade failed. Tried to trade {quantity} {item_id}. Error: more than owned."
                )
                return False
            # Inserts same item into tradee's inventory
            create_item(new_owner, item_id, quantity)
            # Removes items from trader's inventory
            delete_item(owner, item_id, quantity)
            log.info(f"Traded {quantity} {item_id} from {owner} to {new_owner}.")
            return True
        else:
            # Inserts same item into tradee's inventory
            create_item(new_owner, item_id, inventory[item_id]["quantity"])
            # Removes items from trader's inventory
            delete_item(owner, item_id)
            return True

    else:
        # If item doesn't exist, do nothing
        log.warn(f"Tried to trade {item_id} from {owner} to {new_owner}. Item does not exist.")
        return False


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
    drops = {}
    query = Master.select().where(Master.skill == skill, Master.drop_rate != None)
    for item in query:
        drops[item.item_id] = item
    return drops
