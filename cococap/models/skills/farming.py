from pydantic import BaseModel, Field
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
    since: int = 0  # the last rain (hour number) already counted for this plot


def _plot() -> Plot:
    return Plot()


class Farm(BaseModel):
    plot_1: Plot = Field(default_factory=_plot)
    plot_2: Plot = Field(default_factory=_plot)
    plot_3: Plot = Field(default_factory=_plot)
    plot_4: Plot = Field(default_factory=_plot)
    plot_5: Plot = Field(default_factory=_plot)
    plot_6: Plot = Field(default_factory=_plot)
    plot_7: Plot = Field(default_factory=_plot)
    plot_8: Plot = Field(default_factory=_plot)
    plot_9: Plot = Field(default_factory=_plot)


class Farming(Skill):
    farm: Farm = Field(default_factory=Farm)
    stats: Stats = Field(default_factory=Stats)
    applied_fertilizer: Optional[str] = None
    rain_god_blessings: int = 0
