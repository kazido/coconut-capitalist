import os
import configparser
from pathlib import Path

from dotenv import load_dotenv
from enum import Enum

# Load our environment variables (see .env.example) from the project root, not the current dir.
BOT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = Path(os.path.abspath(os.path.join(BOT_DIR, os.pardir)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Secret: the Discord bot token. Never commit it.
TOKEN = os.getenv("BOT_TOKEN")

# The SQLite database file (relative paths are resolved against the project root).
DATABASE_PATH = os.path.join(PROJECT_ROOT, os.getenv("DATABASE_PATH", "data/cococap.db"))


def require_secrets() -> None:
    """Raise a readable error if a required secret is missing (call once at startup)."""
    if not TOKEN:
        raise RuntimeError(
            "Missing required environment variable BOT_TOKEN. Copy .env.example to .env and fill it in."
        )


# Non-secret settings from config.ini (path is anchored to the project root)
config = configparser.ConfigParser()
config.read(os.path.join(PROJECT_ROOT, "config.ini"))
DEBUG_MODE = config.getboolean("config", "debug mode", fallback=False)
FILE_LOGGING = config.getboolean("config", "file logging", fallback=False)
DEV_MODE = config.getboolean("config", "dev mode", fallback=True)

# The guild the bot waits for before loading its extensions. Override with the GUILD_ID env var.
GUILD_ID = int(os.getenv("GUILD_ID", "856915776345866240"))

# Extensions that still depend on the pre-migration SQLite/peewee item database (`Master`,
# `cococap.item_models`, `get_items_from_db`) or on removed helpers. They are skipped at startup
# instead of failing noisily; remove an entry once its module has been ported. See docs/AUDIT.md.
DISABLED_EXTENSIONS: frozenset[str] = frozenset()  # extensions skipped at startup (none right now)

# Discord ID of the bot's owner/admin (receives reports, may use the debug commands).
OWNER_ID = int(os.getenv("OWNER_ID", "326903703422500866"))

# What the casino games stake and pay out: "purse" (bits) or "luckbucks". See docs/DESIGN.md.
CASINO_CURRENCY = "luckbucks"

BOT_ID = 956000805578768425 if DEV_MODE else 1016054559581413457
BOT_PREFIX = "-" if DEV_MODE else "."


class GamblingChannels(Enum):
    PARADISE = 858549045613035541
    DREAMSCAPE = 959271607241683044
    PLANETARIUM = 961471869725343834
    NIGHTMARE = 961045401803317299
    HEAVEN = 962171274073899038
    THERAPY = 962171351794327562


# The tools every player gets for free (the shop sells none): one per skill, claimed on the first /play or from the Tools page.
STARTER_TOOLS = ("rookiepickaxe", "starter_axe", "starter_rod", "tin_can")


class Rarities(Enum):
    COMMON = (1, "Common", "0x8E9AAF")
    UNCOMMON = (2, "Uncommon", "0x4FCB6B")
    RARE = (3, "Rare", "0x3D8BFF")
    SUPER_RARE = (4, "Super Rare", "0xA855F7")
    LEGENDARY = (5, "Legendary", "0xFFB020")
    PREMIUM = (6, "Premium", "0xFF4D4D")
    MYTHICAL = (7, "Mythical", "0xFF4FD8")

    def __new__(cls, value, name, color):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.rarity_name = name
        obj.color = color
        return obj

    @classmethod
    def from_value(cls, value: int):
        return cls(value)


IMAGES_REPO = "https://raw.githubusercontent.com/kazido/images/main"


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
