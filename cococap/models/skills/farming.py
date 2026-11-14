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
    watered: int = -1  # the hour you last watered this plot (once per hour)


def _plot() -> Plot:
    return Plot()


class Farm(BaseModel):
    """Room for up to MAX_PLOTS plots (three pages of nine); how many exist in the game is `services.farming.PLOTS`."""

    plot_1: Plot = Field(default_factory=_plot)
    plot_2: Plot = Field(default_factory=_plot)
    plot_3: Plot = Field(default_factory=_plot)
    plot_4: Plot = Field(default_factory=_plot)
    plot_5: Plot = Field(default_factory=_plot)
    plot_6: Plot = Field(default_factory=_plot)
    plot_7: Plot = Field(default_factory=_plot)
    plot_8: Plot = Field(default_factory=_plot)
    plot_9: Plot = Field(default_factory=_plot)
    plot_10: Plot = Field(default_factory=_plot)
    plot_11: Plot = Field(default_factory=_plot)
    plot_12: Plot = Field(default_factory=_plot)
    plot_13: Plot = Field(default_factory=_plot)
    plot_14: Plot = Field(default_factory=_plot)
    plot_15: Plot = Field(default_factory=_plot)
    plot_16: Plot = Field(default_factory=_plot)
    plot_17: Plot = Field(default_factory=_plot)
    plot_18: Plot = Field(default_factory=_plot)
    plot_19: Plot = Field(default_factory=_plot)
    plot_20: Plot = Field(default_factory=_plot)
    plot_21: Plot = Field(default_factory=_plot)
    plot_22: Plot = Field(default_factory=_plot)
    plot_23: Plot = Field(default_factory=_plot)
    plot_24: Plot = Field(default_factory=_plot)
    plot_25: Plot = Field(default_factory=_plot)
    plot_26: Plot = Field(default_factory=_plot)
    plot_27: Plot = Field(default_factory=_plot)


MAX_PLOTS = 27


class Farming(Skill):
    farm: Farm = Field(default_factory=Farm)
    stats: Stats = Field(default_factory=Stats)
    applied_fertilizer: Optional[str] = None
    rain_god_blessings: int = 0
    starter_given: bool = False  # you have had your free starter seeds
