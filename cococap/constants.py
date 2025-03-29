import os
import json

from enum import Enum
from dotenv import load_dotenv

load_dotenv()


# Paths
BOT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BOT_DIR, os.pardir))

# Opening config file
config_path = os.path.join(PROJECT_ROOT, "config.json")
with open(config_path, "r") as f:
    data = json.load(f)


# Grab the bot token from the .env file using the load_dotenv function from the dotenv package
TOKEN = os.getenv("BOT_TOKEN")
# Same deal, grab the URI for the MongoDB database
URI = os.getenv("URI")
DATABASE = "itemdatabase.db"

DEBUG_MODE = bool(data["DEBUG_MODE"])
FILE_LOGGING = bool(data["FILE_LOGGING"])
DEV_MODE = bool(data["DEV_MODE"])

BOT_ID = 956000805578768425 if DEV_MODE else 1016054559581413457
BOT_PREFIX = "-" if DEV_MODE else "."


class GamblingChannels(Enum):
    PARADISE = 858549045613035541
    DREAMSCAPE = 959271607241683044
    PLANETARIUM = 961471869725343834
    NIGHTMARE = 961045401803317299
    HEAVEN = 962171274073899038
    THERAPY = 962171351794327562


class ModerationChannels(Enum):
    DATABASE_LOGS = 858606781093511248


class Rarities(Enum):
    COMMON = (1, "Common", "0x99F7A7")
    UNCOMMON = (2, "Uncommon", "0x63EFFF")
    RARE = (3, "Rare", "0x0C61CF")
    SUPER_RARE = (4, "Super Rare", "0x6E3ADE")
    LEGENDARY = (5, "Legendary", "0xE3AB3B")
    PREMIUM = (6, "Premium", "0xFF3B3B")
    MYTHICAL = (7, "Mythical", "0x9F34FF")

    def __new__(cls, value, name, color):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.rarity_name = name
        obj.color = color
        return obj

    @classmethod
    def from_value(cls, value: int):
        return cls(value)


class Categories(Enum):
    FARMING = ("🌽", "Farming", "0x2f919e")
    FORAGING = ("🌳", "Foraging", "0x2f9e47")
    FISHING = ("🐟", "Fishing", "0x2f3a9e")
    MINING = ("⛏️", "Mining", "0x9e492f")
    COMBAT = ("⚔️", "Combat", "0x9e2f2f")
    SHEPHERDING = ("🐑", "Shepherding", "0x5f2f9e")
    GENERAL = ("📦", "General", "0x8b9a9e")

    def __new__(cls, emoji, name, color):
        obj = object.__new__(cls)
        obj._value_ = name.lower()
        obj.emoji = emoji
        obj.display_name = name
        obj.color = color
        return obj

    @classmethod
    def from_name(cls, name: str):
        return cls(name.lower())


class LeaderboardCategories(Enum):
    BITS = ("💸", "Bits", "purse", "0xbbd6ed")
    LUCKBUCKS = ("🍀", "Luckbucks", "luckbucks", "0x47d858")
    FARMING = ("🌽", "Farming", "farming.xp", "0x2f919e")
    FORAGING = ("🌳", "Foraging", "foraging.xp", "0x2f9e47")
    FISHING = ("🐟", "Fishing", "fishing.xp", "0x2f3a9e")
    MINING = ("⛏️", "Mining", "mining.xp", "0x9e492f")
    COMBAT = ("⚔️", "Combat", "combat.xp", "0x9e2f2f")
    # SHEPHERDING = ("🐑", "Shepherding", ['shepherding'], "0x5f2f9e")  # TO BE ADDED
    DROPS = ("📦", "Drops", "drops_claimed", "0x8b9a9e")

    def __new__(cls, emoji, name, column: str, color):
        obj = object.__new__(cls)
        obj._value_ = name.lower()
        obj.emoji = emoji
        obj.display_name = name
        obj.column = column
        obj.color = color
        return obj

    @classmethod
    def from_name(cls, name: str):
        return cls(name.lower())


FIRST_PLACE_ANSI_PREFIX = "\u001b[0;37m"
SECOND_PLACE_ANSI_PREFIX = "\u001b[0;33m"
THIRD_PLACE_ANSI_PREFIX = "\u001b[0;31m"
OTHER_PLACE_ANSI_PREFIX = "\u001b[0;30m"
RESET_POSTFIX = "\u001b[0m"


IMAGES_REPO = "https://raw.githubusercontent.com/kazido/images/main"
GREEN_CHECK_MARK_URL = f"{IMAGES_REPO}/icons/checkmarks/green-checkmark-dist.png"
RED_X_URL = f"{IMAGES_REPO}/icons/checkmarks/red-x.png"


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
    "Something went wrong.",
    "Uh oh.",
    "Oops!",
    "Something didn't work properly.",
    "Are you trying to break something?",
]

SUCCESS_REPLIES = [
    "Success!",
    "Nice job!",
    "Good job!",
]

FAILURE_REPLIES = [
    "Bummer.",
    "Too bad...",
    "Sorry!",
    "Failed.",
    "RIP :(",
    "Nice try.",
    "Good effort.",
    'I^I "nooo!"',
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


NUMBER_EMOJIS = {
    1: ":one:",
    2: ":two:",
    3: ":three:",
    4: ":four:",
    5: ":five:",
    6: ":six:",
    7: ":seven:",
    8: ":eight:",
    9: ":nine:",
    10: ":ten:",
}
