from pydantic import BaseModel, Field
from .base import Skill


class Stats(BaseModel):
    trees_chopped: int = 0
    double_trees_chopped: int = 0
    releaf_donations: int = 0
    chops: int = 0  # every chop you have made
    grains: int = 0  # grains you have finished clean (Windfall counts them)


class Foraging(Skill):
    # grain id -> what you know about the one style it likes: an UPPERCASE letter once you have seen it work, or the lowercase letters
    # of the styles you have seen fail (your grain notes)
    styles: dict[str, str] = Field(default_factory=dict)
    stats: Stats = Field(default_factory=Stats)

    releaf_meter: int = 0  # When this reaches the goal, your next tree is a double tree
    donations_made_today: int = 0  # Up to 3 donations per day
    donation_day: int = -1  # the UTC day number donations_made_today counts
    double_ready: bool = False  # your next tree is a double tree
