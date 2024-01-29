

# class Pet:
#     def __init__(self, pet_id) -> None:
#         self.instance = mm.Pets.get(id=pet_id)
#         self.pet_embed = discord.Embed(title=f"Pet: {self.instance.name}",
#                                        color=discord.Color.from_str(pets[self.instance.rarity]['color']))
#         self.pet_embed.add_field(name="Rarity", value=f"{self.instance.rarity.replace('_', ' ')}")
#         self.pet_embed.add_field(name="Species",
#                                  value=f"{pets[self.instance.rarity]['animals'][self.instance.species]['emoji']}")
#         self.pet_embed.add_field(name="Health",
#                                  value=f"**{self.instance.health}/{pets[self.instance.rarity]['health']}**",
#                                  inline=False)
#         self.pet_embed.add_field(name="Level", value=f"{self.instance.level}")

#     def feed(self, crop):
#         pass

#     def switch_active_pet(self, pet_id):
#         for pet in mm.Pets.select().objects():
#             if pet.pet_id == pet_id:  # Set current active pet to inactive
#                 self.instance.active = False
#                 self.instance.save()
#                 pet.active = True  # Update matching pet to be active and to be objects active pet
#                 pet.save()

#     def rename(self, new_name):
#         self.instance.name = new_name
#         self.instance.save()
#         return new_name

