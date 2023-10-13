import peewee

from src.entity_models import Items
from src.item_models import DataMaster, ItemType

from logging import getLogger
from playhouse.shortcuts import model_to_dict

log = getLogger(__name__)
log.setLevel(20)


class ItemDoesNotExist(Exception):
    pass

class EntityDoesNotExist(Exception):
    pass


class Item:
    def __init__(self, item_id: str) -> None:
        try:
            item_data = DataMaster.get_by_id(item_id)
            for field in item_data.__data__.keys():
                setattr(self, field, getattr(item_data, field))
        except peewee.DoesNotExist:
            raise ItemDoesNotExist(f"No {DataMaster.__name__} found with ID {item_id}")
    
    def __str__(self) -> str:
        return self.display_name
        

class Entity:
    # TODO: add self.owner and set it to an instance of the User class
    def __init__(self, owner_id: int, item_id: str) -> None:
        try:
            entity_data = Items.get(owner=owner_id, item_id=item_id)
            for field in entity_data.__data__.keys():
                setattr(self, field, getattr(entity_data, field))
            self.item = Item(item_id)
        except peewee.DoesNotExist:
            raise EntityDoesNotExist(f"No {Items.__name__} found with ID {item_id} and owner ID {owner_id}.")
        
    def __str__(self) -> str:
        # TODO: make self.owner reference the owners name
        return f"{self.item.display_name} owned by {self.owner}"
    
        
def get_item_data(item_id: str, backrefs: bool = False):
    """Retrieve an item by ID."""
    try:
        item = DataMaster.get_by_id(item_id)
        data = model_to_dict(item, backrefs=backrefs, max_depth=1)
        return data
    except peewee.DoesNotExist:
        raise ItemDoesNotExist(f"No {DataMaster.__name__} found with ID {item_id}")


def get_item_display_name(item_id):
    """Retrieve the display name or name of the item."""
    try:
        item = DataMaster.get_by_id(item_id)
        display_name = getattr(item, "display_name", None)
        return display_name
    except peewee.DoesNotExist:
        raise ItemDoesNotExist(f"No {DataMaster.__name__} found with ID {item_id}")
    

def _get_total_power(entity_data: dict):
    tool_data = get_item_data(entity_data['item_id'], backrefs=True)
    tool_power = tool_data['tool_data'][0]['power']
    _total_power = entity_data['star_level'] * tool_power
    return _total_power


def get_entity(owner_id: int, item_id: str, backrefs: bool = False):
    """Retrieve data about an existing entity."""
    try:
        item_info = get_item_data(item_id, backrefs=True)
        item = Items.get(owner=owner_id, item_id=item_id)
        data = model_to_dict(item, backrefs=backrefs, max_depth=1)
        if item_info['filter_type'] == 'tool':
            data['total_power'] = _get_total_power(data)
        return data
    except Items.DoesNotExist:
        raise ItemDoesNotExist(
            f"No {Items.__name__} found with ID {item_id} and owner ID {owner_id}."
        )


def set_entity_field(owner_id: int, item_id: str, field, value):
    """Set the field of an item"""
    if not hasattr(Items, field):
        raise ValueError(f"Field '{field}' does not exist in model {Items.__name__}")
    item = get_entity(owner_id=owner_id, item_id=item_id)
    item.field = value
    return item.save()


def create_entity(owner: int, item_id: str, quantity: int = 1):
    """Inserts an entity into the database with specified owner and quantity"""
    # Ensure that the item is an actual item first
    if not DataMaster.get_or_none(item_id=item_id):
        return False, f"'{item_id}' is not a valid item id."
    # Retrieve or create the item in the database
    defaults = {"quantity": quantity}
    if get_item_data(item_id)['filter_type'] == 'TOOL':
        defaults['star_level'] = 1
    item, created = Items.get_or_create(
        owner=owner, item_id=item_id, defaults=defaults
    )
    if created:
        # If an item was created, return
        return True, f"New item created with quantity: {quantity}."
    else:
        # If an item was found, add to it's quantity
        item.quantity += quantity
        item.save()
        return True, f"Item quantity increased by {quantity}"


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
