from pydantic import BaseModel
from typing import Optional
from .base import Skill


class Stats(BaseModel):
    crops_grown: int = 0


class Plot(BaseModel):
    crop_id: Optional[str] = None
    cycle: int = 0
    can_harvest: bool = False
    imbued: bool = False
    unlocked: bool = False


class Farm(BaseModel):
    plot_1 = Plot()
    plot_2 = Plot()
    plot_3 = Plot()
    plot_4 = Plot()
    plot_5 = Plot()
    plot_6 = Plot()
    plot_7 = Plot()
    plot_8 = Plot()
    plot_9 = Plot()


class Farming(Skill):
    farm: Farm = Farm()
    stats: Stats = Stats()
    applied_fertilizer: Optional[str] = None
    rain_god_blessings: int = 0
