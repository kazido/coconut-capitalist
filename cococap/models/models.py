from beanie import Document
from typing import Optional

from .skills.mining import Mining
from .skills.fishing import Fishing
from .skills.farming import Farming
from .skills.foraging import Foraging
from .skills.combat import Combat
from cooldowns import Cooldowns
from settings import Settings
from stats import Stats
from pethouse import Pethouse


class UserDocument(Document):
    # BASIC INFO
    name: str  # Required
    discord_id: int  # Required
    rank: int = 0  # Will store the user's rank by rank ID
    bank: int = 0  # The user's bank which gains interest
    purse: int = 1000  # The user's purse for bits to be used readily
    tokens: int = 0  # The user's tokens which are exclusively used to rank up
    luckbucks: int = 0  # The currency just used for gambling
    party_id: Optional[int] = None  # Tracks what party a user is in

    # Skills
    mining: Mining = Mining()
    farming: Farming = Farming()
    foraging: Foraging = Foraging()
    fishing: Fishing = Fishing()
    combat: Combat = Combat()

    # General
    cooldowns: Cooldowns = Cooldowns()
    settings: Settings = Settings()
    statistics: Stats = Stats()
    pethouse: Pethouse = Pethouse()

    items: dict = {}  # Empty dict to contain the user's items

    class Settings:
        name = "users"


class PartyDocument(Document):
    party_id: int  # Custom generated party ID
    party_owner: int  # Discord ID of the party owner
    party_members: list = []  # Discord IDs of all party members

    class Settings:
        name = "parties"


class SpecialEntitiesCollection(Document):
    pass

    class Settings:
        name = "special_entities"


class GuildDocument(Document):
    guild_id: int  # id of the guild that the bot is in
    channel_list: list = []  # ids channels that the bot should be able to interact with
    admin_role_id: int  # id of the role that the bot should listen to as admin

    class Settings:
        name = "guilds"
