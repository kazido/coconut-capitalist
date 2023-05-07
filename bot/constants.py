import discord
import os
import json
from enum import Enum


# Paths

BOT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BOT_DIR, os.pardir))

# Opening config file
config_path = os.path.join(PROJECT_ROOT, "bot", "config.json")
with open(config_path, "r") as f:
    data = json.load(f)


# If DEBUG is set to 1
if data["DEBUG"]:
    BOT_PREFIX = "."
    DATABASE = "testdatabase.db"
    TOKEN = data["secondary_token"]

# If DEBUG is set to 0
else:
    BOT_PREFIX = "-"
    DATABASE = "livedatabase.db"
    TOKEN = data["primary_token"]


class DiscordGuilds(Enum):
    PRIMARY_GUILD = discord.Object(id=856915776345866240)
    TESTING_GUILD = discord.Object(id=977351545966432306)

class GamblingChannels(Enum):
    PARADISE = discord.Object(id=858549045613035541)
    DREAMSCAPE = discord.Object(id=959271607241683044)
    PLANETARIUM = discord.Object(id=961471869725343834)
    NIGHTMARE = discord.Object(id=961045401803317299)
    HEAVEN = discord.Object(id=962171274073899038)
    WWTGS = discord.Object(id=962171351794327562)


class CooldownTimes(Enum):
    WORK = 6
    DAILY = 21
    WEEKLY = 167

# Bot replies
NEGATIVE_REPLIES = [
    "Noooooo!!",
    "Nope.",
    "I'm sorry Dave, I'm afraid I can't do that.",
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
class Emoji(Enum):
    HAPPY = ":smile:"
    FROWN = ":slight_frown:"
    SAD = ":sob:"
    ANGRY = ":angry:"
    CONFIRM = ":white_check_mark:"
    CANCEL = ":x:"
