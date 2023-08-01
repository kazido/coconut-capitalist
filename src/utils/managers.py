import discord

from src.models import Users, Items, Pets
from src.models import DataTables, Backrefs, DATATABLES, BACKREFS
from src.models import DataMaster, DataCrops, DataSeeds, DataTools, DataPets, DataAreas
from src.utils.members import retrieve_rank
from logging import getLogger


log = getLogger(__name__)


class UserManager:
    # Retireve an instance of a user and their rank information
    def __init__(self, user_id: int, interaction: discord.Interaction = None) -> None:

        # Create or retrieve the user instance from the Users table
        self.instance: Users
        self.instance, _ = Users.get_or_create(user_id=user_id)
        self.id = user_id
        # If there is no interaction, finish initializing
        if not interaction:
            return
        # Update the user's rank and display name if available in the interaction
        user = discord.utils.get(interaction.guild.members, id=user_id)
        self.rank = retrieve_rank(user_id=user_id, interaction=interaction)
        if user and (self.instance.name != user.display_name):
            self.instance.name = user.display_name
            self.instance.save()
            
    def __str__(self) -> str:
        return self.instance.name

    # Returns a field from the main user object
    def get_field(self, field: str, backref: BACKREFS=None):
        fields = self.instance
        if backref:
            table = getattr(fields, backref).get()
            return getattr(table, field)
        return getattr(fields, field)

    # Updates a field from the main user object
    def set_field(self, field: str, value, backref: BACKREFS=None):
        fields = self.instance
        if backref:
            # Get the related model from the base model
            table = getattr(fields, backref).get()
            setattr(table, field, value)
            return table.save()
        setattr(fields, field, value)
        return self.save()

    # Starts a game for the user, meaning they cannot play other games
    def start_game(self):
        self.instance.in_game = True
        log.debug(f"Updating {self.instance.name} status to True.")
        self.save()

    # Ends a game for the user, enabling them to play other games
    def end_game(self):
        self.instance.in_game = False
        log.debug(f"Updating {self.instance.name} status to False.")
        self.save()

    # Save the user's information in the database
    def save(self):
        self.instance.save()

class ItemManager:
    # Retrieve an item instance from the database
    def __init__(self, owner_id: int, item_id: str) -> None:
        try:
            self.instance: Items
            self.instance = Items.get(owner=owner_id, item_id=item_id)
        except Items.DoesNotExist:
            log.debug("Item not found.")
            self.instance = None
            
    def __str__(self) -> str:
        return DataManager.get_data("master", self.instance.item_id, 'display_name')

    def get_field(self, field: str):
        fields = self.instance
        item_data = DataManager('master', self.instance.item_id).instance
        sub_data = getattr(item_data, f"{item_data.type}_data").get()
        
        # Get the attributes from the related tables
        for attr in item_data.__data__:
            setattr(fields, attr, getattr(item_data, attr))
        for attr in sub_data.__data__:
            setattr(fields, attr, getattr(sub_data, attr))
        return getattr(fields, field)

    def insert_item(owner: int, item_id: str, quantity: int = 1):
        # Ensure that the item is an actual item first
        if not ItemManager.get_data(item_id, 'item_id'):
            return False, f"'{item_id}' is not a valid item id."
        # Retrieve or create the item in the database
        item, created = Items.get_or_create(
            owner=owner, item_id=item_id, defaults={"quantity": quantity}
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
        if not ItemManager.get_fields(item_id):
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
        if not ItemManager.get_fields(item_id):
            return False, f"'{item_id}' is not a valid item id."
        try:
            # Transfer the ownership of the item if it exists
            item: Items = Items.get(owner=owner, item_id=item_id)
            if quantity:
                if quantity > item.quantity:
                    return False, "User does not own enough of this item."
                # Inserts same item into tradee's inventory
                ItemManager.insert_item(new_owner, item_id, quantity)
                # Removes items from trader's inventory
                ItemManager.delete_item(owner, item_id, quantity)
                return True, f"{quantity} items transferred."
            else:
                # If the entire quantity of the item is being traded, just transfer ownership
                item.owner_id = new_owner
                item.save()
                return True, "Entire item transferred."

        except Items.DoesNotExist:
            # If item doesn't exist, do nothing
            return False, "This item does not exist."

    def get_data(item_id: str, field: str):
        item_data = DataMaster.get_by_id(item_id)
        if item_data.type:
            sub_data = getattr(item_data, f"{item_data.type}_data").get()
            # Get the attributes from the related tables
            for attr in sub_data.__data__:
                setattr(item_data, attr, getattr(sub_data, attr))
        return getattr(item_data, field)
    
class PetManager:
    # Retrieve row from pet table for feeding, changing name, etc.
    def __init__(self, owner_id: int, pet_id: str) -> None:
        try:
            self.instance: Pets
            self.instance = Pets.get(owner_id=owner_id, pet_id=pet_id)
        except Pets.DoesNotExist:
            print("Pet not found.")
            self.instance = None
            
    def __str__(self) -> str:
        return self.instance.name
            
    # Get field from instance
    def get_field(self, field: str = 'pet_id'):
        fields = self.instance
        pet_data = DataPets.get_by_id(self.instance.pet_id)
        for attr in pet_data.__data__:
            setattr(fields, attr, getattr(pet_data, attr))
        return getattr(fields, field)

    # Change the name of a user's pet
    def change_name(self, new_name):
        if len(new_name) > 14:
            return "Please refrain from using more than 14 characters."
        self.instance.name = new_name
        self.instance.save()
        return f"Name successfully changed to {new_name}."

    # Change the active status of a user's pet
    def set_activity(self, active: bool = False):
        self.instance.active = active
        self.instance.save()
        return f"Pet activity set to {active}"

    # Increase a pet's xp
    def feed_pet(self, crop_id: str):
        pet_data = PetManager.get_field(self.instance.pet_id)
        if self.instance.level >= pet_data.max_level:
            return False, "Cannot feed pet, already at max level."
        crop = ItemManager.get_fields(crop_id)
        if not crop:
            return False, "Specified crop does not exist."
        crop_xp = crop.pet_xp
        self.instance.xp += crop_xp

        # Check to see if pet has leveled up
        new_level = int(self.instance.xp**(1/3))
        if new_level > self.instance.level:
            new_level = new_level if new_level < pet_data.max_level else pet_data.max_level
            self.instance.level = new_level
            leveled_up, level = True, new_level
        else:
            leveled_up, level = False, None
        self.instance.save()
        return leveled_up, level

    # Insert a valid new pet into the database
    def insert_pet(owner_id: int, pet_id: str, name: str):
        # Ensure that the item is an actual item first
        if not PetManager.get_field(pet_id):
            return False, f"'{pet_id}' is not a valid item id."
        # Retrieve or create the item in the database
        pet = Pets.create(owner_id=owner_id, pet_id=pet_id, name=name)
        pet.save()
        return True, f"New pet ({name}) created with owner: {owner_id}"

    # Look for an active pet under the specified owner
    def get_active_pet(owner_id: int):
        try:
            query = ((Pets.owner_id == owner_id) & Pets.active)
            active_pet = Pets.select().where(query).get()
        except Pets.DoesNotExist:
            return None
        return active_pet
    
    # Get data from a specified pet
    def get_data(pet_id: str, field: str):
        pet_data = DataPets.get_by_id(pet_id)
        return getattr(pet_data, field)
    
class DataManager:
    def __init__(self, category: DATATABLES, entity_id: str) -> None:
        try:
            self.instance: DataTables[category].value
            self.instance = DataTables[category].value.get_by_id(entity_id)
        except DataTables[category].DoesNotExist:
            print("Entity not found")
            self.instance = None
            
    def __str__(self) -> str:
        return self.instance.display_name
            
    def get_field(self, field: str = 'item_id'):
        fields = self.instance
        return getattr(fields, field)
    
    # Get data from a specified table
    def get_data(category: DATATABLES, entity_id: str, field: str):
        entity_data = DataTables[category].value.get_by_id(entity_id)
        return getattr(entity_data, field)

class ToolManager(ItemManager):
    def __init__(self, owner_id: int, tool_id: str) -> None:
        super().__init__(owner_id, tool_id)
        self._total_power: int
        
    @property
    def total_power(self):
        self._total_power = self.get_field('power') * self.get_field('star_level')
        return self._total_power
