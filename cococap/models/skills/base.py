from pydantic import BaseModel, Field
from typing import Optional


class Skill(BaseModel):
    xp: int = 0
    # id of the equipped tool (an item instance the player owns); None = nothing equipped
    equipped_instance_id: Optional[int] = None
    mastery: list[str] = Field(default_factory=list)  # the Mastery nodes you have bought (ids), if this skill has a tree
    # accessory slots (configs/accessories.toml slots_per_skill): the owned accessory instance id in each, None = empty
    accessory_ids: list[Optional[int]] = Field(default_factory=lambda: [None, None])
