from pydantic import BaseModel
from typing import Optional


class Pet(BaseModel):
    name: str
    level: int = 1
    xp: int = 0


class Pethouse(BaseModel):
    active: Optional[Pet] = None
