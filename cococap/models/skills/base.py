from pydantic import BaseModel
from typing import Optional


class Skill(BaseModel):
    xp: int = 0
    equipped_tool: Optional[str] = None
