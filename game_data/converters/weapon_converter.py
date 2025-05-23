import importlib

# Weapons!

# Swords:
#   swords do decent dps
#   all swords do more damage the more consecutive hits you get

# Bows:
#   bows do high dps
#   all bows take 1 turn to charge their attacks

# Shields:
#   shields have low dps
#   all shields have the ability to protect their team from some damage

# Spells:
#   spells have very high dps
#   all spells have requirements to use their best attack, but can use weaker attacks for free


# USED TO ASSEMBLE USABLE WEAPON FROM WHAT THE PLAYER HAS
class Weapon:
    # Need to pass in a weapon id so we can build it from the weapon.ini file
    def __init__(self, weapon_id: str):
        split = weapon_id.split(".", 1)
        file = split[0]
        config.read(os.path.join("ini", f"{file}.ini"))
        weapon = config[split[1]]
        # Basic Stats
        self.data = weapon
        self.type = weapon["type"]
        self.name = weapon["name"]
        self.description = weapon["description"]
        self.strength = weapon["strength"]
        self.requirement = weapon["requirement"]
        # Ability
        self.ability = self._retrieve_ability()
        self.ability_name = weapon["ability_name"]
        self.ability_description = weapon["ability_description"]

