from pydantic import BaseModel
from base import Skill


class Stats(BaseModel):
    monsters_slain: int = 0
    bosses_slain: int = 0


class Combat(Skill):
    stats: Stats = Stats()
