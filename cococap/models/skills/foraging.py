from pydantic import BaseModel, Field
from .base import Skill


class Stats(BaseModel):
    trees_chopped: int = 0
    double_trees_chopped: int = 0  # legacy (double trees are gone)
    releaf_donations: int = 0  # how many times you have given to the Releaf Foundation
    chops: int = 0  # every chop you have made
    grains: int = 0  # grains you have finished clean (Windfall counts them)


class Foraging(Skill):
    # grain id -> what you know about the one style it likes: an UPPERCASE letter once you have seen it work, or the lowercase letters
    # of the styles you have seen fail (your grain notes)
    styles: dict[str, str] = Field(default_factory=dict)
    stats: Stats = Field(default_factory=Stats)

    # LEGACY (the old per-player Re-leaf and its double trees, now replaced by the server-wide Releaf Foundation): nothing reads these any more;
    # they stay so saves written before the rebuild still load.
    releaf_meter: int = 0
    donations_made_today: int = 0
    donation_day: int = -1
    double_ready: bool = False
