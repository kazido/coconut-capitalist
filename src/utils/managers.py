import discord

from src.models import Users, Items, Pets, backrefs
from src.models import DataMaster, DataCrops, DataSeeds, DataTools, DataPets
from src.utils.members import retrieve_rank
from logging import getLogger


log = getLogger(__name__)


class UserManager:
    # Retireve an instance of a user and their rank information
    def __init__(self, user_id, interaction: discord.Interaction) -> None:

        # Create or retrieve the user instance from the Users table
        self.instance, created = Users.get_or_create(user_id=user_id)

        # Setup remaining user data from other sources
        if interaction:
            self.rank = retrieve_rank(user_id=user_id, interaction=interaction)

            # Update the user's display name if available in the interaction
            user = discord.utils.get(interaction.guild.members, id=user_id)
            if user and (self.instance.name != user.display_name):
                log.debug(f"Updating {self.instance.name} to {user.display_name}")
                self.instance.name = user.display_name
                self.instance.save()

        if created:
            welcome_embed = discord.Embed(
                title="Welcome, Capitalist!",
                description="Insert helpful tips later.",
                color=discord.Color.green()
            )
            user.send(embed=welcome_embed)

    def get_data(user_id: int):
        try:
            user_data = Users.get_by_id(user_id)
            # Needs to be updated whenever a new skill is added
            for table_name in backrefs:
                table = getattr(user_data, table_name).get()
                for attr in table.__data__:
                    unique_attr = table_name + '_' + attr
                    setattr(user_data, unique_attr, getattr(table, attr))
            return user_data
        except Users.DoesNotExist:
            # Handle the case where item_id does not exist in the database.
            return None
        
    def set_data(self, field: str, value):
        # Can only be used on an instance of UserManager
        field_parts = field.split('.')
        if len(field_parts) > 1:
            # Get the related model from the base model
            model = getattr(self.instance, field_parts[0])
            model_row = model.get()
            setattr(model_row, field_parts[1], value)
            model_row.save()
        else:
            setattr(self.instance, field_parts[0], value)
            self.save()

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

    def __init__(self, owner_id: int = None, item_id: str = None) -> None:
        try:
            self.instance = Items.get(owner=owner_id, item_id=item_id)
        except Items.DoesNotExist:
            print("Item not found.")

    def get_data(item_id: str):
        try:
            item_data = DataMaster.get_by_id(item_id)
            sub_data = getattr(item_data, f"{item_data.type}_data").get()
            for attr in sub_data.__data__:
                setattr(item_data, attr, getattr(sub_data, attr))
            return item_data
        except DataMaster.DoesNotExist:
            # Handle the case where item_id does not exist in the database.
            return None

    def insert_item(owner: int, item_id: str, quantity: int = 1):
        # Ensure that the item is an actual item first
        if not ItemManager.get_data(item_id):
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
        if not ItemManager.get_data(item_id):
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
        if not ItemManager.get_data(item_id):
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


class PetManager:
    # Retrieve row from pet table for feeding, changing name, etc.
    def __init__(self, owner_id: int, pet_id: str = None) -> None:
        try:
            self.instance = Pets.get(owner_id=owner_id, pet_id=pet_id)
        except Pets.DoesNotExist:
            print("Pet not found.")
            
    # Change the name of a user's pet
    def change_name(self, new_name):
        if len(new_name) > 14:
            return "Please refrain from using more than 14 characters."
        self.instance.name = new_name
        self.instance.save()
        return f"Name successfully changed to {new_name}."
    
    # Change the active status of a user's pet
    def set_activity(self, active: bool=False):
        self.instance.active = active
        self.instance.save()
        return f"Pet activity set to {active}"
        
    # Increase a pet's xp
    def feed_pet(self, crop_id: str):
        pet_data = PetManager.get_data(self.instance.pet_id)
        if self.instance.level >= pet_data.max_level:
            return False, "Cannot feed pet, already at max level."
        crop = ItemManager.get_data(crop_id)
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

    # Get data of a specified pet
    def get_data(pet_id: str):
        try:
            pet_data = DataPets.get_by_id(pet_id)
            return pet_data
        except DataMaster.DoesNotExist:
            # Handle the case where item_id does not exist in the database.
            return None

    # Insert a valid new pet into the database
    def insert_pet(owner_id: int, pet_id: str, name: str):
        # Ensure that the item is an actual item first
        if not PetManager.get_data(pet_id):
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

