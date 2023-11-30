import peewee

from cococap.entity_models import Items
from cococap.utils.members import User
from cococap.item_models import DataMaster, ItemType

from logging import getLogger
from playhouse.shortcuts import model_to_dict

log = getLogger(__name__)
log.setLevel(20)


class ItemDoesNotExist(Exception):
    pass


class EntityDoesNotExist(Exception):
    pass


class Item:
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


class Entity:
    """Class representing an actualized item, meaning an item with an owner, a quantity, etc."""
    def __init__(self, owner_id: int, item_id: str) -> None:
        try:
            entity_data = Items.get(owner=owner_id, item_id=item_id)
            for field, value in entity_data.__data__.items():
                setattr(self, field, value)
            self.item = Item(item_id)
            self.owner = User(owner_id)
        except peewee.DoesNotExist:
            raise EntityDoesNotExist(
                f"No {Items.__name__} found with ID {item_id} and owner ID {owner_id}."
            )

    def __str__(self) -> str:
        return f"{self.item.display_name} owned by {self.owner}"
    
    @staticmethod
    def create(owner: int, item_id: str, quantity: int = 1):
        """Inserts an entity into the database with specified owner and quantity"""
        # Ensure that the item is an actual item first
        if not DataMaster.get_or_none(item_id=item_id):
            return False, f"'{item_id}' is not a valid item id."
        # Retrieve or create the item in the database
        defaults = {"quantity": quantity}
        if Item(item_id).item_type == "TOOL":
            defaults["star_level"] = 1
        item, created = Items.get_or_create(owner=owner, item_id=item_id, defaults=defaults)
        if created:
            # If an item was created, return
            return True, f"New item created with quantity: {quantity}."
        else:
            # If an item was found, add to it's quantity
            item.quantity += quantity
            item.save()
            return True, f"Item quantity increased by {quantity}"

    def get_user_tool(self, skill: str = None):
        """Retrieve information about the tool that a user has equipped for specified skill."""
        if not skill:
            return "You didn't specify a skill to retrieve the tool from."
        user_skill = getattr(self, skill)
        user_tool_id = user_skill.tool_id
        if user_tool_id:
            return Entity(self.user_id, user_tool_id)
        return None


def delete_item(owner: int, item_id: str, quantity: int = None):
    # Ensure that the item is an actual item first
    if not DataMaster.get_or_none(item_id=item_id):
        return False, f"'{item_id}' is not a valid item id."
    try:
        # Try to decrement quantity of existing item
        item = Items.get(owner=owner, item_id=item_id)
        if quantity:
            item.quantity -= quantity
            if item.quantity <= 0:
                # If quantity becomes 0 or negative, delete item
                item.delete_instance()
                return True, "Item quantity 0 or below, item deleted."
            else:
                item.save()
                return True, f"Item quantity reduced by {quantity}"
        else:
            item.delete_instance()
            return True, "Item deleted."

    except Items.DoesNotExist:
        # If item doesn't exist, do nothing
        return False, "This item does not exist."


def trade_item(owner: int, new_owner: int, item_id: str, quantity: int = None):
    # Ensure that the item is an actual item first
    if not DataMaster.get_or_none(item_id=item_id):
        return False, f"'{item_id}' is not a valid item id."
    try:
        # Transfer the ownership of the item if it exists
        item: Items = Items.get(owner=owner, item_id=item_id)
        if quantity:
            if quantity > item.quantity:
                return False, "User does not own enough of this item."
            # Inserts same item into tradee's inventory
            create_entity(new_owner, item_id, quantity)
            # Removes items from trader's inventory
            delete_item(owner, item_id, quantity)
            return True, f"{quantity} items transferred."
        else:
            # If the entire quantity of the item is being traded, just transfer ownership
            item.owner_id = new_owner
            item.save()
            return True, "Entire item transferred."

    except Items.DoesNotExist:
        # If item doesn't exist, do nothing
        return False, "This item does not exist."
