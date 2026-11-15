from pydantic import BaseModel, Field
from typing import Optional
from .base import Skill


class Stats(BaseModel):
    lodes_mined: int = 0
    lodes_auto_mined: int = 0


class Core(BaseModel):
    gem_id: Optional[str] = None


class Reactor(BaseModel):
    level: int = 1
    core_1: Core = Field(default_factory=Core)
    core_2: Core = Field(default_factory=Core)
    core_3: Core = Field(default_factory=Core)
    core_4: Core = Field(default_factory=Core)
    lodes_available: int = 0
    last_auto_mine: float = 0  # Used to calculate how many lodes are available


class Mining(Skill):
    reactor: Reactor = Field(default_factory=Reactor)
    stats: Stats = Field(default_factory=Stats)
    magnet_meter: int = 0
    magnet_on: bool = True  # the magnet marks rows (and spends meter) while this is on
    magnet_auto_feed: bool = False  # the auto-miner's copper, iron and gold fill the magnet first
    lifeline_wait: int = 0  # mines left before the Lifeline capstone is ready again (0: ready)
