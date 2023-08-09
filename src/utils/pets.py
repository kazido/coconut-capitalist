


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
    def get_field(self, field: str = "pet_id"):
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
        new_level = int(self.instance.xp ** (1 / 3))
        if new_level > self.instance.level:
            new_level = (
                new_level if new_level < pet_data.max_level else pet_data.max_level
            )
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
            query = (Pets.owner_id == owner_id) & Pets.active
            active_pet = Pets.select().where(query).get()
        except Pets.DoesNotExist:
            return None
        return active_pet

    # Get data from a specified pet
    def get_data(pet_id: str, field: str):
        pet_data = DataPets.get_by_id(pet_id)
        return getattr(pet_data, field)
