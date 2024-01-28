from beanie import Document, Link
from typing import Optional, List


class UserCollection(Document):
    name: str # Required
    discord_id: int # Required
    location: str = "the_agora"
    bank: int = 0
    purse: int = 1000
    tokens: int = 0
    in_game: bool = False
    party_id: Optional[str] = None
    drops_claimed: int = 0
    farming: dict = {
        "xp": 0,
        "equipped_tool": None,
        "is_farming": False,
        "crops_grown": 0,
        "fertilizer": None,
        "rain_god_blessings": 0,
        "plots_unlocked": 3,
        "plot1": {},
        "plot2": {},
        "plot3": {},
    }
    foraging: dict = {
        "xp": 0,
        "equipped_tool": None,
        "trees_chopped": 0,
        "double_trees_chopped": 0,
        "releaf_donations": 0,
        "releaf_meter": 0,
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
        "lodes_mined": 0,
        "core_slot1": None,
        "core_slot2": None,
        "core_slot3": None,
        "core_slot4": None,
        "prestige_level": 0,
        "bonus_type": None,
        "bonuses_remaining": 0,
    }
    combat: dict = {
        "xp": 0,
        "equipped_tool": None,
        "monsters_slain": 0,
        "bosses_slain": 0,
    }
    settings: dict = {
        "auto_deposit": False,
        "withdraw_warning": True,
        "disable_max_bet": False,
        "comprehensive_checkin": False,
    }
    pets: dict = {}
    items: dict = {}
    cooldowns: dict = {"work": 0, "daily": 0, "weekly": 0}

    class Settings:
        name = "users"


class PartyCollection(Document):
    party_id: str
    party_owner: int
    location: str
    party_members: list = []
    channel_id: int
    public: bool = False

    class Settings:
        name = "parties"