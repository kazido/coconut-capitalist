import json

with open('../items/crops.json', 'r') as f:
    crops = json.load(f)

with open('../pets.json', 'r') as f:
    pet_rarities = json.load(f)

for rarity in pet_rarities:
    print(f"===={rarity.upper()}====")



