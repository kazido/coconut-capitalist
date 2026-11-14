from pydantic import BaseModel, Field
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


class QuestProgress(BaseModel):
    """Where a player is in the current period's quests (the quests themselves come from the clock and the player)."""

    period: int = -1  # the day number (daily) or week number (weekly) this progress belongs to
    progress: list[int] = Field(default_factory=list)
    done: list[bool] = Field(default_factory=list)


class Fishing(Skill):
    daily: QuestProgress = Field(default_factory=QuestProgress)
    weekly: QuestProgress = Field(default_factory=QuestProgress)
    quest_book: QuestBook = Field(default_factory=QuestBook)
    skiff: Skiff = Field(default_factory=Skiff)
    stats: Stats = Field(default_factory=Stats)
