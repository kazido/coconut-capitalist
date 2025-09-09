from pydantic import BaseModel


class Stats(BaseModel):
    claimed_work: int = 0
    claimed_daily: int = 0
    claimed_weekly: int = 0


class Cooldowns(BaseModel):
    work: float = 0
    daily: float = 0
    weekly: float = 0
    stats: Stats = Stats()
