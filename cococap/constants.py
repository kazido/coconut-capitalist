import os
import configparser

from dotenv import load_dotenv
from enum import Enum

# Load our environment variables (see .env.example) from the project root, not the current dir.
BOT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(BOT_DIR, os.pardir))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Secrets: the Discord bot token and the MongoDB connection string. Never commit these.
TOKEN = os.getenv("BOT_TOKEN")
URI = os.getenv("URI")


def require_secrets() -> None:
    """Raise a readable error if a required secret is missing (call once at startup)."""
    missing = [name for name, value in (("BOT_TOKEN", TOKEN), ("URI", URI)) if not value]
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
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
DISABLED_EXTENSIONS = frozenset(
    {
        "cococap.exts.core.inventory",
        "cococap.exts.economy.pets",
        "cococap.exts.economy.shop",
        "cococap.exts.minigames.wiki",
        "cococap.exts.minigames.trivia",
        "cococap.exts.skills.fishing",
        "cococap.exts.skills.foraging",
        "cococap.exts.skills.mining",
        "cococap.exts.exploration.mining",
        "cococap.exts.gambling.snail_racing",  # empty stub: setup() calls add_cog() with no cog
    }
)

# Discord ID of the bot's owner/admin (receives reports, may use the debug commands).
OWNER_ID = int(os.getenv("OWNER_ID", "326903703422500866"))

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


class AlphabetEmojis(Enum):
    LETTER_A = ":regional_indicator_a:"
    LETTER_B = ":regional_indicator_b:"
    LETTER_C = ":regional_indicator_c:"
    LETTER_D = ":regional_indicator_d:"
    LETTER_E = ":regional_indicator_e:"
    LETTER_F = ":regional_indicator_f:"
    LETTER_G = ":regional_indicator_g:"
    LETTER_H = ":regional_indicator_h:"
    LETTER_I = ":regional_indicator_i:"
    LETTER_J = ":regional_indicator_j:"
    LETTER_K = ":regional_indicator_k:"
    LETTER_L = ":regional_indicator_l:"
    LETTER_M = ":regional_indicator_m:"
    LETTER_N = ":regional_indicator_n:"
    LETTER_O = ":regional_indicator_o:"
    LETTER_P = ":regional_indicator_p:"
    LETTER_Q = ":regional_indicator_q:"
    LETTER_R = ":regional_indicator_r:"
    LETTER_S = ":regional_indicator_s:"
    LETTER_T = ":regional_indicator_t:"
    LETTER_U = ":regional_indicator_u:"
    LETTER_V = ":regional_indicator_v:"
    LETTER_W = ":regional_indicator_w:"
    LETTER_X = ":regional_indicator_x:"
    LETTER_Y = ":regional_indicator_y:"
    LETTER_Z = ":regional_indicator_z:"


class AlphabetUnicode(Enum):
    LETTER_A = "🇦"
    LETTER_B = "🇧"
    LETTER_C = "🇨"
    LETTER_D = "🇩"
    LETTER_E = "🇪"
    LETTER_F = "🇫"
    LETTER_G = "🇬"
    LETTER_H = "🇭"
    LETTER_I = "🇮"
    LETTER_J = "🇯"
    LETTER_K = "🇰"
    LETTER_L = "🇱"
    LETTER_M = "🇲"
    LETTER_N = "🇳"
    LETTER_O = "🇴"
    LETTER_P = "🇵"
    LETTER_Q = "🇶"
    LETTER_R = "🇷"
    LETTER_S = "🇸"
    LETTER_T = "🇹"
    LETTER_U = "🇺"
    LETTER_V = "🇻"
    LETTER_W = "🇼"
    LETTER_X = "🇽"
    LETTER_Y = "🇾"
    LETTER_Z = "🇿"


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
