from pydantic import BaseModel
from .base import Skill


class Stats(BaseModel):
    trees_chopped: int = 0
    double_trees_chopped: int = 0
    releaf_donations: int = 0


class Foraging(Skill):
    stats: Stats = Stats()
    releaf_meter: int = 0  # When this reaches 50, the next tree drops 10m or a special item
    donations_made_today: int = 0  # Up to 3 donations per day
