from pydantic import BaseModel, Field, field_validator


class OwnedPet(BaseModel):
    stars: int = 1
    xp: int = 0
    spirits: list[str] = Field(default_factory=list)  # skills this pet was given a Spirit for


class Pethouse(BaseModel):
    active: str | None = None  # the species whose bonuses are in effect
    pets: dict[str, OwnedPet] = Field(default_factory=dict)  # species id -> your one pet of that kind

    @field_validator("active", mode="before")
    @classmethod
    def _old_style(cls, value):
        return value if isinstance(value, str) else None  # (the old format stored a whole pet here)
