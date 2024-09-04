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