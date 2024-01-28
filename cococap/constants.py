import os
import json
from enum import Enum


# Paths
BOT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BOT_DIR, os.pardir))

# Opening config file
config_path = os.path.join(PROJECT_ROOT, "config.json")
with open(config_path, "r") as f:
    data = json.load(f)


BOT_PREFIX = "-"
TOKEN = data["primary_token"]
URI = data["mongo_uri"]
DATABASE = "livedatabase.db"

if data["DEV"]:
    BOT_PREFIX = "."
    TOKEN = data["secondary_token"]
    URI = data["mongo_uri"]
    DATABASE = "testdatabase.db"


DEBUG_MODE = False
if data["DEBUG_MODE"]:
    DEBUG_MODE = True


FILE_LOGGING = False
if data["FILE_LOGGING"]:
    FILE_LOGGING = True


class DiscordGuilds(Enum):
    PRIMARY_GUILD = 856915776345866240
    TESTING_GUILD = 977351545966432306


class GamblingChannels(Enum):
    PARADISE = 858549045613035541
    DREAMSCAPE = 959271607241683044
    PLANETARIUM = 961471869725343834
    NIGHTMARE = 961045401803317299
    HEAVEN = 962171274073899038
    THERAPY = 962171351794327562


class ModerationChannels(Enum):
    DATABASE_LOGS = 858606781093511248


class PartyRoles(Enum):
    PARTY_LEADER = 1130004841687699487

class Rarities(Enum):
    COMMON = (1, 'Common', '0x99F7A7')
    UNCOMMON = (2, 'Uncommon', '0x63EFFF')
    RARE = (3, 'Rare', '0x0C61CF')
    SUPER_RARE = (4, 'Super Rare', '0x6E3ADE')
    LEGENDARY = (5, 'Legendary', '0xE3AB3B')
    PREMIUM = (6, 'Premium', '0xE3A019')
    MYTHICAL = (7, 'Mythical', '0x9F34FF')
    
    
    def __new__(cls, value, name, color):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.rarity_name = name
        obj.color = color
        return obj
    
    @classmethod
    def from_value(cls, value):
        return cls(value)

class CooldownTimes(Enum):
    WORK = 6
    DAILY = 21
    WEEKLY = 167


IMAGES_REPO = "https://raw.githubusercontent.com/kazido/images"
GREEN_CHECK_MARK_URL = f"{IMAGES_REPO}/main/icons/checkmarks/green-checkmark-dist.png"
RED_X_URL = f"{IMAGES_REPO}/main/icons/checkmarks/red-x.png"


# Default role combinations
MODERATION_ROLES = None

# Bot replies
NEGATIVE_REPLIES = [
    "Noooooo!!",
    "Nope.",
    "I don't think so.",
    "Not gonna happen.",
    "Out of the question.",
    "Huh? No.",
    "Nah.",
    "Naw.",
    "Not likely.",
    "No way, José.",
    "Not in a million years.",
    "Fat chance.",
    "Certainly not.",
    "NEGATORY.",
    "Nuh-uh.",
    "Not in my house!",
]

POSITIVE_REPLIES = [
    "Yep.",
    "Absolutely!",
    "Can do!",
    "Affirmative!",
    "Yeah okay.",
    "Sure.",
    "Sure thing!",
    "You're the boss!",
    "Okay.",
    "No problem.",
    "I got you.",
    "Alright.",
    "You got it!",
    "ROGER THAT",
    "Of course!",
    "Aye aye, cap'n!",
    "I'll allow it.",
]

ERROR_REPLIES = [
    "Please don't do that.",
    "You have to stop.",
    "Do you mind?",
    "In the future, don't do that.",
    "That was a mistake.",
    "You blew it.",
    "You're bad at computers.",
    "Are you trying to kill me?",
    "Noooooo!!",
    "I can't believe you've done this",
]

TOO_RICH_TITLES = [
    "Begging is for poor people...",
    "You're already rich!",
    "Really?",
    "You have a job, go work it.",
    "No.",
    "Bet everything, then come back.",
]


# Emojis
class Emojis(Enum):
    HAPPY = ":smile:"
    FROWN = ":slight_frown:"
    SAD = ":sob:"
    ANGRY = ":angry:"
    CONFIRM = ":white_check_mark:"
    CANCEL = ":x:"
    STATUS_ONLINE = ":white_check_mark:"
    STATUS_OFFLINE = ":x:"
    TRASHCAN = ":wastebasket:"
