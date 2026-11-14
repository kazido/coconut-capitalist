from pydantic import BaseModel, Field
from .base import Skill


class Stats(BaseModel):
    monsters_slain: int = 0
    bosses_slain: int = 0


class Combat(Skill):
    stats: Stats = Field(default_factory=Stats)
    kills: dict[str, int] = Field(default_factory=dict)  # enemy id -> how many you have slain (the Bestiary)
