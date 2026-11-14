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


class BookProgress(BaseModel):
    """The personal collection book: how many of each fish you have turned in at the current level."""

    level: int = 1
    given: dict[str, int] = Field(default_factory=dict)


class TreasureState(BaseModel):
    """A hallucination you are carrying: the numbers you saw, and until when chests can turn up."""

    code: str = ""
    armed_until: float = 0.0


class Fishing(Skill):
    community_claimed: int = 0  # how many completions of the community book you have been paid for
    monthly_claimed: dict[str, list[bool]] = Field(default_factory=dict)  # month -> which community quests you were paid for
    treasure: TreasureState = Field(default_factory=TreasureState)
    book: BookProgress = Field(default_factory=BookProgress)
    daily: QuestProgress = Field(default_factory=QuestProgress)
    weekly: QuestProgress = Field(default_factory=QuestProgress)
    quest_book: QuestBook = Field(default_factory=QuestBook)
    skiff: Skiff = Field(default_factory=Skiff)
    stats: Stats = Field(default_factory=Stats)
