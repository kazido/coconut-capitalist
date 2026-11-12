from beanie import Document
from pymongo import ASCENDING, IndexModel
from pydantic import Field
from typing import Optional

from .skills.mining import Mining
from .skills.fishing import Fishing
from .skills.farming import Farming
from .skills.foraging import Foraging
from .skills.combat import Combat
from .cooldowns import Cooldowns
from .settings import Settings
from .stats import Stats
from .pethouse import Pethouse


class UserDocument(Document):
    # BASIC INFO
    name: str  # Required
    discord_id: int  # Required (unique, see Settings.indexes)
    rank: int = 0  # Will store the user's rank by rank ID
    bank: int = 0  # The user's bank which gains interest
    purse: int = 1000  # The user's purse for bits to be used readily
    tokens: int = 0  # The user's tokens which are exclusively used to rank up
    luckbucks: int = 0  # The currency just used for gambling
    party_id: Optional[int] = None  # Tracks what party a user is in

    # Skills
    mining: Mining = Field(default_factory=Mining)
    farming: Farming = Field(default_factory=Farming)
    foraging: Foraging = Field(default_factory=Foraging)
    fishing: Fishing = Field(default_factory=Fishing)
    combat: Combat = Field(default_factory=Combat)

    # General
    cooldowns: Cooldowns = Field(default_factory=Cooldowns)
    settings: Settings = Field(default_factory=Settings)
    statistics: Stats = Field(default_factory=Stats)
    pethouse: Pethouse = Field(default_factory=Pethouse)

    items: dict = Field(default_factory=dict)  # {item_id: {"quantity": int}}

    class Settings:
        name = "users"
        indexes = [IndexModel([("discord_id", ASCENDING)], unique=True)]


class PartyDocument(Document):
    party_id: int  # Custom generated party ID
    party_owner: int  # Discord ID of the party owner
    party_members: list = Field(default_factory=list)  # Discord IDs of all party members

    class Settings:
        name = "parties"


class SpecialEntitiesCollection(Document):
    pass

    class Settings:
        name = "special_entities"


class GuildDocument(Document):
    guild_id: int  # id of the guild that the bot is in
    channel_list: list = Field(default_factory=list)  # ids channels that the bot should be able to interact with
    admin_role_id: int  # id of the role that the bot should listen to as admin

    class Settings:
        name = "guilds"
