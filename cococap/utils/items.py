import peewee

from cococap.entity_models import Items
from cococap.user import User
from cococap.item_models import DataMaster, ItemType

from logging import getLogger
from playhouse.shortcuts import model_to_dict

log = getLogger(__name__)
log.setLevel(20)


class ItemDoesNotExist(Exception):
    pass


class EntityDoesNotExist(Exception):
    pass


class ItemBlueprint:
    """Class representing the blueprint of an item, meaning an item's stats, rarity, etc."""

    def __init__(self, item_id: str) -> None:
        try:
            item_data = DataMaster.get_by_id(item_id)
            for field, value in item_data.__data__.items():
                setattr(self, field, value)
        except peewee.DoesNotExist:
            raise ItemDoesNotExist(f"No {DataMaster.__name__} found with ID {item_id}")

    def __str__(self) -> str:
        return self.display_name


class Item:
    """Class representing an actualized item, meaning an item with an owner, a quantity, etc."""

    def __init__(self, owner_id: int, item_id: str) -> None:
        try:
            entity_data = Items.get(owner=owner_id, item_id=item_id)
            for field, value in entity_data.__data__.items():
                setattr(self, field, value)
            self.item_data = ItemBlueprint(item_id)
            self.owner = User(owner_id)
        except peewee.DoesNotExist:
            raise EntityDoesNotExist(
                f"No {Items.__name__} found with ID {item_id} and owner ID {owner_id}."
            )

    def __str__(self) -> str:
        return f"{self.item_data.display_name} owned by {self.owner}"

    @staticmethod
    def create(owner: int, item_id: str, quantity: int = 1):
        """Inserts an item into the database with specified owner and quantity"""
        # Ensure that the item is an actual item first
        if not DataMaster.get_or_none(item_id=item_id):
            log.warn(f"Tried to create: {quantity} {item_id}. Error: item does not exist.")
            return False, f"'{item_id}' is not a valid item id."
        if quantity < 1:
            log.warn(f"Tried to create {quantity} {item_id}. Less than 1.")
            return False
        # Retrieve or create the item in the database
        defaults = {"quantity": quantity}
        if ItemBlueprint(item_id).item_type == "TOOL":
            defaults["star_level"] = 1
        item, created = Items.get_or_create(
            owner=owner, item_id=item_id, defaults=defaults
        )
        if created:
            # If an item was created, return
            log.info(f"{quantity} new {item_id} created with owner: {owner}.")
            return True
        else:
            # If an item was found, add to it's quantity
            item.quantity += quantity
            item.save()
            log.info(f"Added {quantity} {item_id} to: {owner}")
            return True
        
    @staticmethod
    def delete(owner: int, item_id: str, quantity: int = None):
        # Ensure that the item is an actual item first
        if not DataMaster.get_or_none(item_id=item_id):
            log.warn(f"Tried to delete: {item_id}. Error: not a valid item id.")
            return False, f"'{item_id}' is not a valid item id."
        if quantity < 1:
            log.warn(f"Tried to delete: {quantity} {item_id}. Error: less than 1.")
        try:
            # Try to decrement quantity of existing item
            item = Items.get(owner=owner, item_id=item_id)
            if quantity and (item.quantity - quantity > 0):
                item.quantity -= quantity
                item.save()
                log.info(f"Deleted {quantity} {item_id} from {owner}.")
                return True
            else:
                item.delete_instance()
                log.info(f"Deleted all {item_id} from {owner}.")
                return True

        except Items.DoesNotExist:
            # If item doesn't exist, do nothing
            log.warn(f"Tried to delete {quantity} {item_id} from {owner}. Does not exist.")
            return False

    def get_user_tool(self, skill: str = None):
        # TODO: Not sure I want this
        """Retrieve information about the tool that a user has equipped for specified skill."""
        if not skill:
            return "You didn't specify a skill to retrieve the tool from."
        user_skill = getattr(self, skill)
        user_tool_id = user_skill.tool_id
        if user_tool_id:
            return Item(self.user_id, user_tool_id)
        return None


def trade_item(owner: int, new_owner: int, item_id: str, quantity: int = None):
    # Ensure that the item is an actual item first
    if not DataMaster.get_or_none(item_id=item_id):
        log.warn(f"Tried to trade: {item_id}. Error: not a valid item id.")
        return False
    try:
        # Transfer the ownership of the item if it exists
        item: Items = Items.get(owner=owner, item_id=item_id)
        if quantity:
            if quantity > item.quantity:
                log.warn(f"Trade failed. Tried to trade {quantity} {item_id}. Error: more than owned.")
                return False
            # Inserts same item into tradee's inventory
            Item.create(new_owner, item_id, quantity)
            # Removes items from trader's inventory
            Item.delete(owner, item_id, quantity)
            log.info(f"Traded {quantity} {item_id} from {owner} to {new_owner}.")
            return True
        else:
            # If the entire quantity of the item is being traded, just transfer ownership
            item.owner_id = new_owner
            item.save()
            log.info(f"Transferred ownership of {item_id} from {owner} to {new_owner}.")
            return True

    except Items.DoesNotExist:
        # If item doesn't exist, do nothing
        log.warn(f"Tried to trade {item_id} from {owner} to {new_owner}. Item does not exist.")
        return False
