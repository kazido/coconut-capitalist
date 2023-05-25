import discord
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


if data["DEBUG"]:
    BOT_PREFIX = "."
    DATABASE = "testdatabase.db"
    TOKEN = data["secondary_token"]
    DEBUG_MODE = True
else:
    BOT_PREFIX = "-"
    DATABASE = "livedatabase.db"
    TOKEN = data["primary_token"]
    DEBUG_MODE = False
    
    
if data["FILE_LOGGING"]:
    FILE_LOGGING = True
else:
    FILE_LOGGING = False


class DiscordGuilds(Enum):
    PRIMARY_GUILD = 856915776345866240
    TESTING_GUILD = 977351545966432306

class GamblingChannels(Enum):
    PARADISE = 858549045613035541
    DREAMSCAPE = 959271607241683044
    PLANETARIUM = 961471869725343834
    NIGHTMARE = 961045401803317299
    HEAVEN = 962171274073899038
    WWTGS = 962171351794327562
    
    
class ModerationChannels(Enum):
    DATABASE_LOGS  = 858606781093511248
    


class CooldownTimes(Enum):
    WORK = 6
    DAILY = 21
    WEEKLY = 167


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
    TRASHCAN = ":trashcan:"
