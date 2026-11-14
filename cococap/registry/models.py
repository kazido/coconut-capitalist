"""Typed game-data models. One instance per entry in ``configs/*.toml``.

All models are frozen and reject unknown keys, so a typo in a data file fails at startup with the
file/entry named, instead of surfacing as an AttributeError in the middle of a command.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cococap import emojis

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


class ToolUpgrade(_Data):
    """What it costs to turn this tool into the next one up (the tool keeps its enchants and rolled bonuses)."""

    to: str
    bits: int = Field(ge=0)
    items: dict[str, int] = Field(default_factory=dict)


class Tool(_Data):
    """Present on equippable tools. `requirement` is the minimum skill level."""

    kind: ToolKind
    power: int = Field(ge=1)
    requirement: int = Field(default=0, ge=0)
    ability: str | None = None
    ability_name: str | None = None
    ability_description: str | None = None
    upgrade: ToolUpgrade | None = None


class Item(_Data):
    id: str
    name: str
    description: str = ""
    wiki: str = ""
    emoji_raw: str | None = Field(default=None, alias="emoji")  # as written in the data file
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
    def emoji(self) -> str | None:
        """The item's emoji, looked up by name among the bot's application emojis (see `cococap.emojis`)."""
        return emojis.resolve(self.emoji_raw)

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
    min_depth: int = Field(ge=0)
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


class RiskLabel(_Data):
    """A word and colour for the collapse risk the player sees (e.g. Calm / Unstable / Critical)."""

    name: str
    emoji: str
    from_risk: float = Field(ge=0, le=1)  # this label applies from this collapse chance upward


class DescentRules(_Data):
    floor: int = Field(ge=1)  # rows in the shaft; digging the last one reaches the vault
    rows_per_tier: int = Field(ge=1)
    # Pressure: every dig adds `creak` plus the hardness of each cell dug; vents and braces remove some.
    creak: float = Field(ge=0)
    default_hardness: float = Field(ge=0)
    empty_hardness: float = Field(ge=0)
    hardness: dict[str, float]  # item id -> pressure added when that ore is dug
    reactor_reduction: float = Field(ge=0)
    max_reduction: float = Field(ge=0, le=0.95)
    brace_amount: float = Field(ge=0)
    braces_base: int = Field(ge=0)
    braces_per_reactor_levels: int = Field(ge=1)
    # Collapse risk is a smooth curve of pressure: 0 below `safe_pressure`, `max_risk` at 100.
    safe_pressure: float = Field(ge=0, lt=100)
    max_risk: float = Field(ge=0, le=1)
    risk_exponent: float = Field(ge=1)
    collapse_loss: float = Field(ge=0, le=1)
    power_yield_bonus: float = Field(ge=0)
    depth_bonus_per_row: float = Field(ge=0)  # every row deeper pays this much more (so going on is tempting)
    # Special cells. Plain cells show their ore; these show what they are.
    vent_chance: float = Field(ge=0, le=1)  # no loot, but cools the tunnel
    vent_relief: float = Field(ge=0)
    rich_chance: float = Field(ge=0, le=1)  # a mystery lode: rolls the NEXT tier's table, more of it
    rich_multiplier: float = Field(ge=1)
    cache_chance: float = Field(ge=0, le=1)  # supplies: +braces
    cache_min_depth: int = Field(ge=0)
    cache_braces: int = Field(ge=1)
    bomb_pressure: float = Field(ge=0)  # a bomb clears a whole row for this flat pressure
    bombs_per_run: int = Field(ge=0)  # most bombs you can carry into one run
    lookahead: int = Field(ge=1, le=3)  # how many rows ahead you can see
    vault_gem_chance: float = Field(ge=0, le=1)  # chance the vault also holds one random reactor gem (gems are rare!)
    vault_ore: dict[str, int]
    warnings: list[RiskLabel] = Field(min_length=1)

    @model_validator(mode="after")
    def _warnings_ascend_from_zero(self):
        starts = [w.from_risk for w in self.warnings]
        if starts[0] != 0 or starts != sorted(starts) or len(set(starts)) != len(starts):
            raise ValueError("risk warnings must start at 0 and have strictly increasing `from_risk` values")
        return self


class MiningRules(_Data):
    columns: int = Field(ge=1)
    xp_per_column: int = Field(ge=0)
    depth_tables: list[list[str]] = Field(min_length=1)
    wyrmhole: WyrmholeRules
    reactor: ReactorRules
    magnet: MagnetRules
    scarab: ScarabRules
    descent: DescentRules


class MarketRules(_Data):
    """The Farmer's Market: open on certain weekdays (0 = Monday), better prices, blessings for land deeds."""

    min_level: int = Field(ge=1)
    days: list[int] = Field(min_length=1)
    price_bonus: float = Field(ge=0)  # +50% -> 0.5
    deed_chance: float = Field(ge=0, le=1)  # per blessing deposited

    @field_validator("days")
    @classmethod
    def _weekdays(cls, days: list[int]) -> list[int]:
        if any(not 0 <= d <= 6 for d in days):
            raise ValueError("market days are weekday numbers 0 (Monday) to 6 (Sunday)")
        return days


class FarmingRules(_Data):
    free_plots: int = Field(ge=1, le=9)  # plots you own from the start
    grow_chance: float = Field(gt=0, le=1)  # per rain (every hour), per growing plot
    blessing_chance: float = Field(ge=0, le=1)  # per rain in which something grew
    anomaly_odds: int = Field(ge=1)  # 1 in N per harvest
    xp_per_rarity: int = Field(ge=0)  # xp for a harvest = crop rarity x this
    deed_item: str
    market: MarketRules


class TreeHeight(_Data):
    min: int = Field(ge=1)
    max: int = Field(ge=1)
    weight: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max < self.min:
            raise ValueError("tree height max must be >= min")
        return self


class CommunityRules(_Data):
    open_minutes: int = Field(ge=1, le=60)
    min_zone: int = Field(ge=1)
    max_zone: int = Field(ge=1)
    hp_multiplier: float = Field(ge=1)
    min_share: float = Field(ge=0, le=1)
    group_bonus: float = Field(ge=0)
    max_group_bonus: float = Field(ge=0)
    expired_factor: float = Field(ge=0, le=1)
    refresh_seconds: float = Field(gt=0)


class SpotKind(_Data):
    """A kind of place on the trunk: some are easier to cut than others."""

    name: str
    multiplier: float = Field(gt=0)
    weight: float = Field(gt=0)


class ChoppingRules(_Data):
    """How a swing's damage varies: good chops, the kind of spot you stand at, and spots wearing down at random."""

    good_chop_chance: float = Field(ge=0, le=1)
    good_chop_bonus: float = Field(ge=0)  # +50% -> 0.5
    wear_chance: float = Field(ge=0, le=1)  # each chop: the chance the spot wears down one step
    wear_step: float = Field(ge=0, lt=1)  # each step makes chops this much weaker
    spot_floor: float = Field(gt=0, le=1)  # ...but never below this share
    spots: list[SpotKind] = Field(min_length=1)


class ForagingRules(_Data):
    zones: int = Field(ge=1)
    levels_per_zone: int = Field(ge=1)
    heavy_zone: int = Field(ge=1)
    heavy_solo_power: float = Field(gt=0, le=1)
    zone_hp_growth: float = Field(ge=0)
    xp_per_hp: float = Field(ge=0)
    bits_per_hp: int = Field(ge=0)
    hp_per_roll: int = Field(ge=1)
    zone_reward_growth: float = Field(ge=0)  # each zone above 1 pays this much more per hp (bits and drop rolls)
    heights: list[TreeHeight] = Field(min_length=1)
    chopping: ChoppingRules
    community: CommunityRules

    @model_validator(mode="after")
    def _zones_fit(self):
        if not 1 <= self.community.min_zone <= self.community.max_zone <= self.zones:
            raise ValueError("community zones must satisfy 1 <= min_zone <= max_zone <= zones")
        return self


class BiteRules(_Data):
    wait_min: float = Field(gt=0)
    wait_max: float = Field(gt=0)
    speedup_per_power: float = Field(ge=0)
    min_wait_factor: float = Field(gt=0, le=1)
    window: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.wait_max < self.wait_min:
            raise ValueError("bite wait_max must be >= wait_min")
        return self


class ReelRules(_Data):
    base_length: int = Field(ge=1)
    power_per_slip: int = Field(ge=1)


class QuestTemplate(_Data):
    """"Catch `count` fish of rarity `min_rarity` or better", and what it pays."""

    min_rarity: int = Field(ge=1, le=7)
    count: int = Field(ge=1)
    bits: int = Field(ge=0)
    xp: int = Field(ge=0)


class QuestRules(_Data):
    min_level: int = Field(ge=1)
    daily_count: int = Field(ge=1)  # how many of the daily templates each player gets per day
    daily: list[QuestTemplate] = Field(min_length=1)
    weekly: list[QuestTemplate] = Field(min_length=1)

    @model_validator(mode="after")
    def _enough(self):
        if len(self.daily) < self.daily_count:
            raise ValueError("there must be at least daily_count daily quest templates")
        return self


class FishingRules(_Data):
    xp_per_rarity: int = Field(ge=0)
    bite: BiteRules
    reel: ReelRules
    quests: QuestRules


class MinigamePayout(_Data):
    flashcard_add: int = Field(ge=0)
    flashcard_sub: int = Field(ge=0)
    flashcard_mul: int = Field(ge=0)
    unscramble_per_letter: float = Field(ge=0)
    sequence_per_element: int = Field(ge=0)
    trivia_easy: int = Field(ge=0)
    trivia_medium: int = Field(ge=0)
    trivia_hard: int = Field(ge=0)


class SequenceDifficulty(_Data):
    easy: int = Field(ge=1)
    medium: int = Field(ge=1)
    hard: int = Field(ge=1)


class MinigameRules(_Data):
    daily_cap: int = Field(ge=0)
    streak_bonus: float = Field(ge=0)
    streak_bonus_max_steps: int = Field(ge=0)
    payout: MinigamePayout
    sequence_difficulty: SequenceDifficulty


class ExchangeRules(_Data):
    bits_per_luckbuck: int = Field(ge=1)
    daily_limit: int = Field(ge=0)


class EconomyRules(_Data):
    party_xp_bonus: float = Field(ge=0)  # skill xp bonus while you are in a party of 2 or more (applies to every skill)
    starting_luckbucks: int = Field(ge=0)
    weekly_luckbucks: int = Field(ge=0)
    minigames: MinigameRules
    exchange: ExchangeRules
