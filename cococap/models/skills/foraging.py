from pydantic import BaseModel, Field, field_validator
from .base import Skill


class Stats(BaseModel):
    trees_chopped: int = 0
    double_trees_chopped: int = 0
    releaf_donations: int = 0


class Foraging(Skill):
    # grain id -> one entry per step of its pattern: an UPPERCASE letter once you know the stance for that step, or the
    # lowercase letters of the stances you have already seen fail there (your grain notes)
    grains: dict[str, list[str]] = Field(default_factory=dict)
    stats: Stats = Field(default_factory=Stats)

    @field_validator("grains", mode="before")
    @classmethod
    def _old_notes(cls, value):
        """(Notes used to be just "how many steps you know": turn those into the steps themselves.)"""
        if not isinstance(value, dict):
            return value
        from cococap.registry import get_registry

        grains = {g.id: g.pattern for g in get_registry().foraging.chopping.grains}
        return {k: ([c.upper() for c in grains.get(k, "")[:v]] if isinstance(v, int) else v) for k, v in value.items()}

    releaf_meter: int = 0  # When this reaches 50, the next tree drops 10m or a special item
    donations_made_today: int = 0  # Up to 3 donations per day
