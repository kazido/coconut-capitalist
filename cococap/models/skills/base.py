from pydantic import BaseModel
from typing import Optional


class Skill(BaseModel):
    xp: int = 0
    # id of the equipped tool (an item instance the player owns); None = nothing equipped
    equipped_instance_id: Optional[int] = None
