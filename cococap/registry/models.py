"""Typed game-data models. One instance per entry in ``configs/*.toml``.

All models are frozen and reject unknown keys, so a typo in a data file fails at startup with the
file/entry named, instead of surfacing as an AttributeError in the middle of a command.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Skill = Literal["farming", "foraging", "fishing", "mining", "combat", "shepherding"]
Category = Literal["material", "tool", "key_item", "pet_item", "crop", "seed"]
ToolKind = Literal["pickaxe", "axe", "sword", "rod"]

ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class _Data(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def check_id(value: str) -> str:
    # Ids are used as MongoDB field-path segments (items.<id>.quantity): no dots or '$'.
    if not ID_RE.match(value):
        raise ValueError(f"invalid id {value!r}: use lowercase snake_case (e.g. 'apple_seed')")
    return value


class Drop(_Data):
    """Found by chance: 1-in-`rate` per roll, yielding `min`..`max` items."""

    rate: int = Field(ge=1)
    min: int = Field(ge=1)
    max: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max < self.min:
            raise ValueError("drop.max must be >= drop.min")
        return self


class Crop(_Data):
    """Present on a harvested crop item."""

    seed: str
    min_harvest: int = Field(ge=1)
    max_harvest: int = Field(ge=1)
    pet_xp: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max_harvest < self.min_harvest:
            raise ValueError("crop.max_harvest must be >= crop.min_harvest")
        return self


class Seed(_Data):
    """Present on a seed item: how many rain cycles until it grows into `grows_into`."""

    grows_into: str
    cycles: int = Field(ge=1)


class Tool(_Data):
    """Present on equippable tools. `requirement` is the minimum skill level."""

    kind: ToolKind
    power: int = Field(ge=1)
    requirement: int = Field(default=0, ge=0)
    ability: str | None = None
    ability_name: str | None = None
    ability_description: str | None = None


class Item(_Data):
    id: str
    name: str
    description: str = ""
    wiki: str = ""
    emoji: str | None = None
    rarity: int = Field(ge=1, le=7)
    skill: Skill | None = None
    category: Category
    price: int = Field(default=0, ge=0)  # 0 = not sold in the shop
    sell_price: int = Field(default=0, ge=0)  # 0 = cannot be sold
    drop: Drop | None = None
    crop: Crop | None = None
    seed: Seed | None = None
    tool: Tool | None = None

    _id = field_validator("id")(check_id)

    @model_validator(mode="after")
    def _category_matches_sections(self):
        for section, category in (("crop", "crop"), ("seed", "seed")):
            if (getattr(self, section) is not None) != (self.category == category):
                raise ValueError(f"'{section}' section must be present iff category is '{category}'")
        if self.tool is not None and self.category != "tool":
            raise ValueError("'tool' section requires category 'tool'")
        return self

    @property
    def is_instance(self) -> bool:
        """Tools are unique objects (can carry enchants); everything else is a stackable counter."""
        return self.tool is not None

    @property
    def buyable(self) -> bool:
        return self.price > 0

    @property
    def sellable(self) -> bool:
        return self.sell_price > 0

    @property
    def display(self) -> str:
        """Emoji (if any) followed by the name."""
        return f"{self.emoji} {self.name}" if self.emoji else self.name


class Pet(_Data):
    id: str
    name: str
    emoji: str | None = None
    stars: int | None = Field(default=None, ge=1, le=3)

    _id = field_validator("id")(check_id)


class Enemy(_Data):
    id: str
    name: str
    attack: int = Field(ge=0)
    hp: int = Field(ge=1)
    shield: int = Field(default=0, ge=0)

    _id = field_validator("id")(check_id)


class Rank(_Data):
    rank_id: int = Field(ge=0)
    display_name: str
    description: str = ""
    emoji: str
    color: str = Field(pattern=r"^[0-9a-fA-F]{6}$")  # hex without '#'
    token_price: int = Field(ge=0)
    wage: int = Field(ge=0)


class Effect(_Data):
    """One thing an enchant does, scaled by the enchant's level on the item.

    - stat_add:  stat += amount * level
    - stat_mult: stat *= 1 + amount * level   (applied after every stat_add)
    - flag:      grants a named capability (e.g. "soloist") that game rules check for
    """

    type: Literal["stat_add", "stat_mult", "flag"]
    stat: str | None = None
    amount: float = 0.0
    flag: str | None = None

    @model_validator(mode="after")
    def _fields_match_type(self):
        if self.type == "flag":
            if not self.flag:
                raise ValueError("a 'flag' effect needs `flag`")
        elif not self.stat:
            raise ValueError(f"a '{self.type}' effect needs `stat`")
        return self


class Enchant(_Data):
    id: str
    name: str
    description: str = ""
    applies_to: list[ToolKind] = Field(min_length=1)
    max_level: int = Field(default=1, ge=1)
    effects: list[Effect] = Field(min_length=1)

    _id = field_validator("id")(check_id)


class WyrmholeRules(_Data):
    odds: int = Field(ge=2)
    gem_bonus: int = Field(ge=0)
    min_odds: int = Field(ge=2)
    min_row: int = Field(ge=0)
    implosion_item: str
    pool: dict[str, int]


class ReactorRules(_Data):
    gem_slot_level: int = Field(ge=1)
    max_prestige: int = Field(ge=1)
    prestige_per_extra_column: int = Field(ge=1)
    core_gems: list[str] = Field(min_length=4, max_length=4)
    automine_seconds: int = Field(ge=1)
    automine_cap_hours: int = Field(ge=1)


class MagnetRules(_Data):
    level: int = Field(ge=1)
    capacity: int = Field(ge=1)
    values: dict[str, int]


class ScarabRules(_Data):
    chance: int = Field(ge=1)
    seconds: int = Field(ge=1)
    reward_item: str


class MiningRules(_Data):
    rows: int = Field(ge=1)
    columns: int = Field(ge=1)
    xp_per_column: int = Field(ge=0)
    depth_tables: list[list[str]]
    wyrmhole: WyrmholeRules
    reactor: ReactorRules
    magnet: MagnetRules
    scarab: ScarabRules

    @model_validator(mode="after")
    def _shape(self):
        if len(self.depth_tables) != self.rows:
            raise ValueError("depth_tables must have exactly `rows` lists")
        return self
