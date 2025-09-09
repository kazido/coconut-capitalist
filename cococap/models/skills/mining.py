from pydantic import BaseModel
from typing import Optional
from base import Skill


class Stats(BaseModel):
    lodes_mined: int = 0
    lodes_auto_mined: int = 0


class Core(BaseModel):
    gem_id: Optional[str] = None


class Reactor(BaseModel):
    level: int = 1
    core_1: Core = Core()
    core_2: Core = Core()
    core_3: Core = Core()
    core_4: Core = Core()
    lodes_available: int = 0
    last_auto_mine: float = 0  # Used to calculate how many lodes are available


class Mining(Skill):
    reactor: Reactor = Reactor()
    stats: Stats = Stats()
    magnet_meter: int = 0
