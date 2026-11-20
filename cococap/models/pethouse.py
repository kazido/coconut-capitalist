from pydantic import BaseModel, Field, field_validator, model_validator

CURVE_VERSION = 1  # 0: one xp curve for every pet; 1: a curve per rarity (services/pets.py rescales version 0 so no pet loses a level)


class OwnedPet(BaseModel):
    stars: int = 1
    xp: int = 0
    spirits: list[str] = Field(default_factory=list)  # skills this pet was given a Spirit for
    lent_tool: str | None = None  # id of the one real tool lent to this pet (it stays yours but you cannot use it meanwhile)
    buff_until: float = 0.0  # unix time its skill-food xp buff ends (0 = none)


class Pethouse(BaseModel):
    active: str | None = None  # the species whose bonuses are in effect
    pets: dict[str, OwnedPet] = Field(default_factory=dict)  # species id -> your one pet of that kind
    target: str | None = None  # the pet you are hunting: orbs are likelier to give it
    misses: int = 0  # orbs opened since that missed it (makes the next one likelier)
    fuel_seconds: float = 0.0  # the ONE tank, for the active pet: seconds of idle work left (crops fill it, capped by pet_score.toml)
    fuel_kinds: list[str] = Field(default_factory=list)  # crop kinds in the tank now (each widens the cap); cleared when it runs empty
    last_collect: float = 0.0  # unix time the idle haul was last collected or the tank last topped up (0 = never)
    curve_version: int = CURVE_VERSION  # which xp curve the stored xp is on (see CURVE_VERSION)

    @model_validator(mode="before")
    @classmethod
    def _unversioned_house_is_on_the_first_curve(cls, data):
        if isinstance(data, dict) and "curve_version" not in data and data.get("pets"):
            return {**data, "curve_version": 0}  # saved before the field existed: it holds xp on the old curve
        return data

    @field_validator("active", mode="before")
    @classmethod
    def _old_style(cls, value):
        return value if isinstance(value, str) else None  # (the old format stored a whole pet here)
