from beanie import Document
from typing import Optional


class UserDocument(Document):
    name: str  # Required
    discord_id: int  # Required
    rank: int  # Will store the user's rank by rank ID
    bank: int = 0  # The user's bank which gains interest
    purse: int = 1000  # The user's purse for bits to be used readily
    tokens: int = 0  # The user's tokens which are exclusively used to rank up
    luckbucks: int = 0 # The currency just used for gambling
    in_game: dict = {
        "in_game": False,
        "message_id": "",
    }  # Used to prevent user's from playing multiple games at once (message id is useless right now)
    party_id: Optional[int] = None # Tracks what party a user is in
    drops_claimed: int = 0 # Fun statistic
    farming: dict = {
        "xp": 0,
        "equipped_tool": None,
        "is_farming": False,
        "crops_grown": 0,
        "fertilizer": None,
        "rain_god_blessings": 0,
        "plots_unlocked": 3,
        "plot1": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot2": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot3": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot4": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot5": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot6": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot7": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot8": {"crop_id": None, "cycle": 0, "imbued": False},
        "plot9": {"crop_id": None, "cycle": 0, "imbued": False},
    }
    foraging: dict = {
        "xp": 0,
        "equipped_tool": None,
        "trees_chopped": 0,  # Statistic for how many trees the user has chopped
        "double_trees_chopped": 0,  # Statistic for how many double trees the user has chopped
        "releaf_donations": 0,  # Statistic for how many re-leaf donations the user has made
        "releaf_meter": 0,  # When this reaches 50, the next tree drops 10m or a special item
        "donations_made_today": 0,  # Up to 3 donations per day
    }
    fishing: dict = {
        "xp": 0,
        "equipped_tool": None,
        "skiff_level": 1,
        "fish_caught": 0,
        "community_book_entries": 0,
        "quest_book": {
            "level": 1,
            "found": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        },
        "quests_completed": 0,
        "treasures_found": 0,
    }
    mining: dict = {
        "xp": 0,
        "equipped_tool": None,
        "lodes_mined": 0,  # Statistic for manual mining
        "lodes_auto_mined": 0,  # Statistic for auto-mining
        "core_slot1": None,
        "core_slot2": None,
        "core_slot3": None,
        "core_slot4": None,
        "prestige_level": 1,  # Level of the reactor
        "lodes_available": 0,  # Auto-mined lodes that are available to claim
        "last_auto_mine": 0,  # Last time the user auto-mined -> used to calculate how many auto-mined lodes there are
        "magnet_meter": 0,
    }
    combat: dict = {
        "xp": 0,
        "equipped_tool": None,
        "monsters_slain": 0,
        "bosses_slain": 0,
    }
    settings: dict = {
        "auto_deposit": False,  # Will automatically deposit the user's bits into their bank after working
        "withdraw_warning": True,  # Displays a warning when trying to withdraw any bits from the bank
        "disable_max_bet": False,  # Disables the bet "max" option when gambling
    }
    pets: dict = {}  # Empty dict which will contain the user's pets
    items: dict = {}  # Empty dict to contain the user's items
    cooldowns: dict = {"work": 0, "daily": 0, "weekly": 0}

    class Settings:
        name = "users"


class PartyDocument(Document):
    party_id: int  # Custom generated party ID
    party_owner: int  # Discord ID of the party owner
    party_members: list = []  # Discord IDs of all party members
    channel_id: int  # Channel ID of the party channel (secret to party members)

    class Settings:
        name = "parties"


class SpecialEntitiesCollection(Document):

    class Settings:
        name = "special_entities"


class GuildDocument(Document):
    guild_id: int  # Discord ID of the guild that the bot is in
    channel_list: list = (
        []
    )  # Discord IDs of all channels that the bot should be able to interact with
    admin_role_id: int  # Discord ID of the role that the bot should listen to as admin

    class Settings:
        name = "guilds"


class ItemDocument(Document):
    item_id: int  # Custom generated item ID
    filter_type: str  #
    rarity: int  # (1-7)
    price: int
    description: str
    wiki: str
    display_name: str
    drop_rate: int

    class Settings:
        name = "items"
