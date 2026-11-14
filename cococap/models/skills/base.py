from pydantic import BaseModel, Field
from typing import Optional


class Skill(BaseModel):
    xp: int = 0
    # id of the equipped tool (an item instance the player owns); None = nothing equipped
    equipped_instance_id: Optional[int] = None
    mastery: list[str] = Field(default_factory=list)  # the Mastery nodes you have bought (ids), if this skill has a tree
