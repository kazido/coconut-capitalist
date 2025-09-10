from pydantic import BaseModel
from .base import Skill


class Stats(BaseModel):
    quests_completed: int = 0
    treasures_found: int = 0
    fish_caught: int = 0
    community_book_entries: int = 0


class Skiff(BaseModel):
    level: int = 1


class QuestBook(BaseModel):
    level: int = 1
    common_donated: bool = False
    uncommon_donated: bool = False
    rare_donated: bool = False
    super_rare_donated: bool = False
    legendary_donated: bool = False


class Fishing(Skill):
    quest_book: QuestBook = QuestBook()
    skiff: Skiff = Skiff()
    stats: Stats = Stats()
