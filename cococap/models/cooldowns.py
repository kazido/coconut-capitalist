from pydantic import BaseModel


class Cooldowns(BaseModel):
    """Unix timestamps of the last time each cooldown-gated action was used."""

    work: float = 0
    daily: float = 0
    weekly: float = 0
