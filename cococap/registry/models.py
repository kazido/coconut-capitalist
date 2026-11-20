"""Typed game-data models. One instance per entry in ``configs/*.toml``.

All models are frozen and reject unknown keys, so a typo in a data file fails at startup with the
file/entry named, instead of surfacing as an AttributeError in the middle of a command.
"""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cococap import emojis

Skill = Literal["farming", "foraging", "fishing", "mining", "combat", "shepherding"]
Category = Literal["material", "tool", "key_item", "pet_item", "pet_food", "crop", "seed", "fish", "scroll", "bait", "part", "accessory"]
ToolKind = Literal["pickaxe", "axe", "sword", "rod", "can"]

ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class _Data(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def check_id(value: str) -> str:
    # Ids are used as MongoDB field-path segments (items.<id>.quantity): no dots or '$'.
    if not ID_RE.match(value):
        raise ValueError(f"invalid id {value!r}: use lowercase snake_case (e.g. 'seed_apple')")
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


class CropScroll(_Data):
    """A scroll one crop alone can drop: 1 in `odds` harvests of that crop (farming rolls it once per harvest)."""

    item: str
    odds: int = Field(ge=1)


class Crop(_Data):
    """Present on a harvested crop item."""

    seed: str
    min_harvest: int = Field(ge=1)
    max_harvest: int = Field(ge=1)
    pet_xp: int = Field(default=0, ge=0)
    scroll: CropScroll | None = None  # the scroll only this crop can drop when harvested (see CropScroll)

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
    # A fork: instead of (or beside) the usual next tool, a second, different path. Its target keeps climbing on its own chain.
    fork: ToolUpgrade | None = None
    path: str | None = None  # the name of the path this tool is on, once it has forked ("Warden", "Prospector")
    stats: dict[str, float] = Field(default_factory=dict)  # what the tool does besides its power (danger_reduction, ore_yield, bite_speed...)


class Size(_Data):
    """How big a fish can be, in cm: every catch gets its own size, and there are records to beat."""

    min: float = Field(gt=0)
    max: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max <= self.min:
            raise ValueError("size max must be greater than min")
        return self


class Scroll(_Data):
    """A one-use scroll that puts an enchant (one level) on a tool of a fitting kind."""

    enchant: str


class PetFood(_Data):
    """Food a skill drops for pets. Its tier sets how much pet xp it is worth (economy.toml [pets] food_xp)."""

    tier: int = Field(ge=1, le=3)
    xp_mult: float = Field(ge=1, default=1.0)  # a feast: worth this many times its tier's pet xp


class Bait(_Data):
    """Bait for crab pots: each catch uses one. `luck` multiplies the chance of rare fish (rarity 4+), `speed` the catches per hour."""

    luck: float = Field(gt=0)
    speed: float = Field(gt=0)


class ReelTell(_Data):
    """How a fish's mystery arrow (❓) behaves. left/right: always that arrow. last: the same as the arrow just before it.
    opposite: the opposite of the arrow just before it. first: the same as the FIRST arrow of the reel. Every tell can be learned."""

    tell: Literal["left", "right", "last", "first", "opposite"]


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
    size: Size | None = None  # fish only
    scroll: Scroll | None = None
    bait: Bait | None = None
    pet_food: PetFood | None = None
    reel: ReelTell | None = None  # fish of rarity 4+: what their ❓ turns out to be
    crop: Crop | None = None
    seed: Seed | None = None
    tool: Tool | None = None
    stars: int = Field(default=0, ge=0, le=3)  # quality tier (0 = no star, the default). Tier 1-3 items are GENERATED from a base item (`star_of`), see StarRules
    star_of: str | None = None  # the base (1-star) item id, for a generated star variant

    _id = field_validator("id")(check_id)

    @model_validator(mode="after")
    def _category_matches_sections(self):
        for section, category in (("crop", "crop"), ("seed", "seed")):
            if (getattr(self, section) is not None) != (self.category == category):
                raise ValueError(f"'{section}' section must be present iff category is '{category}'")
        if (self.pet_food is not None) != (self.category == "pet_food"):
            raise ValueError("'pet_food' section must be present iff category is 'pet_food'")
        if self.category == "pet_food" and not self.skill and self.price <= 0 and self.drop is None:
            raise ValueError("pet food with no skill must be sold in the shop or drop from something")
        if self.tool is not None and self.category != "tool":
            raise ValueError("'tool' section requires category 'tool'")
        return self

    @property
    def emoji(self) -> str | None:
        """The bot's emoji named `<item id>` if uploaded, else the data file's (tokens resolve by name; see `cococap.emojis`)."""
        base = emojis.resolve(self.emoji_raw)
        if self.star_of:  # a starred variant shows its own art if it has any, else the plain material's
            base = emojis.for_id("item", self.star_of, base)
        return emojis.for_id("item", self.id, base)

    @property
    def is_instance(self) -> bool:
        """Tools and smithing parts are unique objects (own tier/traits/enchants); everything else is a stackable counter."""
        return self.tool is not None or self.category in ("part", "accessory")

    @property
    def buyable(self) -> bool:
        return self.price > 0

    @property
    def sellable(self) -> bool:
        return self.sell_price > 0

    @property
    def display(self) -> str:
        """Emoji (if any) followed by the name; a starred material shows star icons instead of the ★ marks in its name."""
        name = self.name.rsplit(" ", 1)[0] + " " + emojis.stars(self.stars) if self.star_of and self.stars > 0 else self.name
        return f"{self.emoji} {name}" if self.emoji else name


class PetBonus(_Data):
    """One thing a pet does while it is your active pet. `stat` is what the game looks up (see services/pets.py)."""

    stat: str
    value: float = Field(gt=0)  # at one star and the TOP level (a fresh pet gives a tenth; see [pets] level_floor in economy.toml)
    text: str  # how it reads, with {v} for the number


class PetTrait(PetBonus):
    """A pet's one named effect (what its old bonus was). It scales with the pet's level and stars (see services/pets.py)."""

    name: str


class PetLoadout(_Data):
    """The simulated "mini you" a pet is scored from (see PetScoreRules and services/pet_score.py). Nothing here is a real item."""

    tool_tier: int = Field(ge=0, le=4)  # 0 = a fresh tool ... 4 = a forked one
    mastery_score: int = Field(ge=0, le=100)  # mastery points the pet "has spent"
    enchant_levels: int = Field(default=0, ge=0)  # total enchant levels the pet "has" (simulated: no real enchants, which change; counts toward gear)


class PetScoreRules(_Data):
    """configs/pet_score.toml: formula constants, sidekick bonus, haul caps, fuel tank. All TODO(balance)."""

    mastery_per_point: float = Field(ge=0)
    gear_per_tier: float = Field(ge=0)
    gear_per_enchant_level: float = Field(ge=0)
    ability_points: dict[str, int]  # "none" / "mid" / "high" -> points out of 100
    skill_points: dict[str, dict[int, int]]  # "specialist" (one skill) and "global_total" (spread over five), by pet rarity
    level_floor: float = Field(gt=0, le=1)
    star_bonus: float = Field(ge=0)
    sidekick_per_strength: float = Field(ge=0)
    sidekick_cap: float = Field(ge=0)
    haul_active_share: float = Field(gt=0, le=1)
    haul_xp_per_score_hour: float = Field(ge=0)
    haul_drop_rolls_per_score_hour: float = Field(ge=0)  # each hour of work rolls the skill's COMMON drop table this many times per point of score
    tank_cap_hours: float = Field(gt=0)
    tank_hours_per_kind: float = Field(ge=0)
    tank_max_kinds: int = Field(ge=1)
    fuel_minutes_per_value: float = Field(gt=0)
    food_buff_bonus: float = Field(ge=0)  # skill food gives the pet this much extra xp rate...
    food_buff_minutes: float = Field(gt=0)  # ...for this long (feeding again refreshes it, it never stacks)


class Pet(_Data):
    id: str
    name: str
    skill: Literal["global", "mining", "farming", "foraging", "fishing", "combat"] = "global"  # the one skill it looks after
    emoji_raw: str | None = Field(default=None, alias="emoji")
    rarity: int = Field(default=1, ge=1, le=8)  # 6 Mythical, 8 Celestial (no pets of those yet)
    ability: Literal["none", "mid", "high"] = "none"  # worth 0 / 50 / 100 of the 1000 score points
    description: str = ""
    trait: PetTrait | None = None  # a pet may have no trait
    loadout: PetLoadout

    _id = field_validator("id")(check_id)

    @property
    def bonuses(self) -> list[PetBonus]:
        """The engine reads a pet's effects as a list of bonuses: its trait is the only one."""
        return [self.trait] if self.trait else []

    @property
    def emoji(self) -> str | None:
        """The bot's emoji named `pet_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("pet", self.id, self.emoji_raw)


EffectKind = Literal[
    "attack_up", "attack_down", "defense_up", "defense_down", "speed_up", "speed_down",  # stat changes: value = fraction (0.3 = 30%)
    "stun",  # the unit loses its turn
    "bleed",  # damage every turn, ignores defense: value = fraction of the caster's attack
    "shield",  # absorbs damage: value = fraction of the caster's max hp
    "heal",  # instant: value = fraction of the target's max hp
    "meter",  # turn meter: value = fraction of a full bar, negative pulls it back
    "empower",  # the unit's next damaging skill deals value x damage (once)
    "reveal",  # the player can see what each enemy will do next
]
SkillTarget = Literal["enemy", "all_enemies", "self", "ally"]
BUFFS = frozenset({"attack_up", "defense_up", "speed_up", "shield", "empower", "reveal"})


class SkillEffect(_Data):
    """Something a skill does besides damage. Timed effects (stat changes, stun, bleed, ...) last `turns` of the
    affected unit's own turns. `chance` is rolled for every target; `on` says who receives it."""

    kind: EffectKind
    on: Literal["target", "self"] = "target"
    chance: int = Field(default=100, ge=1, le=100)
    turns: int = Field(default=1, ge=1)
    value: float = 0

    @model_validator(mode="after")
    def _needs_value(self):
        if self.kind not in {"stun", "reveal"} and self.value == 0:
            raise ValueError(f"effect '{self.kind}' needs a value")
        return self


class CombatSkill(_Data):
    """An action in a fight. `power` multiplies the user's attack (0 = no damage). A skill with a cooldown can be used
    again after that many of the user's own turns; cooldown 0 can be used every turn."""

    id: str
    name: str
    description: str = ""
    power: float = Field(default=0, ge=0)
    target: SkillTarget = "enemy"
    cooldown: int = Field(default=0, ge=0)
    hits: int = Field(default=1, ge=1)
    effects: list[SkillEffect] = Field(default_factory=list)

    _id = field_validator("id")(check_id)

    @model_validator(mode="after")
    def _does_something(self):
        if self.power == 0 and not self.effects:
            raise ValueError("a skill needs power or an effect")
        if self.power > 0 and self.target in {"self", "ally"}:
            raise ValueError("damaging skills must target enemies")
        return self


class DropEntry(_Data):
    """One line of a drop table. Either an item (`min`..`max` of it, skewed toward `min`) or a bits amount."""

    weight: int = Field(ge=1)
    item: str | None = None
    min: int = Field(default=1, ge=1)
    max: int = Field(default=1, ge=1)
    bits_min: int = Field(default=0, ge=0)
    bits_max: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _item_or_bits(self):
        if (self.item is None) == (self.bits_max == 0):
            raise ValueError("a drop is either an item or a bits amount (bits_min/bits_max), not both or neither")
        if self.max < self.min or self.bits_max < self.bits_min:
            raise ValueError("max must be >= min")
        return self


class DropTable(_Data):
    """What a kill (or a channel drop) can give. One entry is chosen by weight: a bigger weight is likelier."""

    id: str
    entries: list[DropEntry] = Field(min_length=1)

    _id = field_validator("id")(check_id)


class Phase(_Data):
    """A boss changes when its hp falls below `below` (a fraction of max hp): it says `message`, gives itself the `buffs`
    and, if `skills` is set, swaps to that skill list (with every cooldown reset)."""

    below: float = Field(gt=0, lt=1)
    message: str
    skills: list[str] | None = Field(default=None, min_length=1)
    buffs: list[SkillEffect] = Field(default_factory=list)


class Enemy(_Data):
    """A monster. `skills` are in priority order: it uses the first one that is off cooldown."""

    id: str
    name: str
    attack: int = Field(ge=0)
    hp: int = Field(ge=1)
    shield: int = Field(default=0, ge=0)
    defense: int = Field(default=0, ge=0)
    speed: int = Field(default=100, ge=1)
    skills: list[str] = Field(default_factory=lambda: ["strike"], min_length=1)
    immune: list[EffectKind] = Field(default_factory=list)  # effects it can never receive (bosses shrug off stuns)
    xp: int = Field(default=0, ge=0)
    emoji: str = "👾"
    drops: str | None = None  # id of its table in drops.toml
    drop_chance: int = Field(default=100, ge=0, le=100)  # percent chance a kill drops anything at all
    boss: bool = False  # shown as a boss in the Bestiary and counted in bosses_slain
    telegraph: bool = False  # bosses: the player always sees what it will do next
    phases: list[Phase] = Field(default_factory=list)  # in the order they happen (highest `below` first)

    _id = field_validator("id")(check_id)

    @model_validator(mode="after")
    def _phases_in_order(self):
        marks = [p.below for p in self.phases]
        if marks != sorted(marks, reverse=True) or len(set(marks)) != len(marks):
            raise ValueError("phases must be listed from the highest `below` to the lowest, each different")
        return self


class PlayerRules(_Data):
    """A player's fighting stats: from their combat level and the sword in their hand."""

    base_hp: int = Field(ge=1)
    hp_per_level: int = Field(ge=0)
    base_attack: int = Field(ge=1)
    attack_per_power: int = Field(ge=0)  # per point of sword power
    attack_per_level: int = Field(ge=0)
    base_defense: int = Field(ge=0)
    defense_per_level: int = Field(ge=0)
    speed: int = Field(ge=1)


class Encounter(_Data):
    """A fight the player can pick: a group of enemies. `min_level` is the combat level that opens it."""

    id: str
    name: str
    enemies: list[str] = Field(min_length=1, max_length=4)
    min_level: int = Field(default=0, ge=0)
    key: str | None = None  # a key_item spent to start it (dropped by enemies)

    _id = field_validator("id")(check_id)


class CombatRules(_Data):
    meter_full: int = Field(ge=1)  # a unit acts when its turn meter reaches this
    defense_scale: int = Field(ge=1)  # damage = attack x power x scale / (scale + defense)
    crit_chance: int = Field(ge=0, le=100)
    crit_damage: float = Field(ge=1)
    max_rounds: int = Field(ge=1)  # a fight this long is a loss (stops stalemates)
    player: PlayerRules
    skills: dict[str, CombatSkill]
    kits: dict[str, list[str]]  # sword item id (or "default") -> skill ids, basic skill first
    encounters: list[Encounter] = Field(min_length=1)


class Rank(_Data):
    rank_id: int = Field(ge=0)
    display_name: str
    description: str = ""
    emoji_raw: str = Field(alias="emoji")
    color: str = Field(pattern=r"^[0-9a-fA-F]{6}$")  # hex without '#'
    token_price: int = Field(ge=0)
    wage: int = Field(ge=0)
    xp_bonus: float = Field(default=0.0, ge=0, le=1)  # a global bonus to every skill's xp, for as long as you hold the rank

    @property
    def emoji(self) -> str:
        """The bot's emoji named `rank_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("rank", self.rank_id, self.emoji_raw)


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
    emoji_raw: str = Field(default="📜", alias="emoji")
    description: str = ""
    applies_to: list[ToolKind] = Field(min_length=1)
    max_level: int = Field(default=1, ge=1)
    effects: list[Effect] = Field(min_length=1)

    _id = field_validator("id")(check_id)

    @property
    def emoji(self) -> str:
        """The bot's emoji named `enchant_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("enchant", self.id, self.emoji_raw)


class MiniWyrmholeRow(_Data):
    pool: dict[str, int] = Field(min_length=1)  # item = quantity; the row's 3 nodes are drawn from it

    @model_validator(mode="after")
    def _quantities(self):
        if any(q < 1 for q in self.pool.values()):
            raise ValueError("mini_wyrmhole row pools need quantities of at least 1")
        return self


class WyrmholeRules(_Data):
    """The big wyrmhole: a hazard-free mini mine; its LAST row holds the implosion gem or a core gem you do not own."""

    odds: int = Field(ge=2)
    gem_bonus: int = Field(ge=0)
    min_odds: int = Field(ge=2)
    min_depth: int = Field(ge=0)  # first row (0-based) a wyrmhole can show in...
    max_depth: int | None = Field(default=None, ge=0)  # ...and the last, or None for no cap (every row from min_depth down can hold one)
    big_chance: float = Field(gt=0, le=1)  # digging into a wyrmhole opens a BIG one with this chance, else a small one
    implosion_item: str
    columns: int = Field(ge=2)  # nodes per row
    rows: list[MiniWyrmholeRow] = Field(min_length=1)
    xp_per_row: int = Field(ge=0)
    implosion_base: float = Field(ge=0, le=1)  # chance the gem is the implosion gem with no core gem owned...
    implosion_per_gem: float = Field(ge=0, le=1)  # ...plus this for every core gem owned

    @model_validator(mode="after")
    def _depths(self):
        if self.max_depth is not None and self.max_depth < self.min_depth:
            raise ValueError("wyrmhole: max_depth must be at least min_depth")
        return self


class MiniWyrmholeRules(_Data):
    columns: int = Field(ge=2)  # nodes per row
    rows: list[MiniWyrmholeRow] = Field(min_length=1)
    xp_per_row: int = Field(ge=0)
    last_row_bonus: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _sane(self):
        if any(q < 1 for q in self.last_row_bonus.values()):
            raise ValueError("mini_wyrmhole: last_row_bonus quantities must be at least 1")
        return self


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
    drain_per_row: float = Field(default=0.0, ge=0)  # meter points one dug row uses while the magnet marks it
    bits_per_point: int = Field(ge=1)  # a material gives sell_price // bits_per_point meter points (at least 1)


class ScarabPrize(_Data):
    """One thing a scarab can give for a solved scroll: items, mining xp, or both."""

    name: str
    weight: float = Field(gt=0)
    items: dict[str, int] = Field(default_factory=dict)
    xp: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _gives_something(self):
        if not self.items and not self.xp:
            raise ValueError("a scarab prize must give items or xp")
        return self


class ScarabRules(_Data):
    chance: int = Field(ge=1)  # 1 in this many mines (however they ended) brings a scarab
    seconds: int = Field(ge=1)  # time to unscramble its scroll
    prizes: list[ScarabPrize] = Field(min_length=1)


class RiskLabel(_Data):
    """A word and colour for the collapse risk the player sees (e.g. Calm / Unstable / Critical)."""

    name: str
    emoji: str
    from_risk: float = Field(ge=0, le=1)  # this label applies from this collapse chance upward


class Milestone(_Data):
    """A landmark row on the way down. Finishing it makes a CHECKPOINT: everything in your pack at that moment is safe from a collapse
    (a collapse only costs what you dug after it). It can also give a little extra (pressure relief, braces, a taste of the vault's ore)."""

    row: int = Field(ge=1)  # the row number you finish (1-based, like the page says)
    relief: float = Field(default=0, ge=0)  # pressure taken off
    braces: int = Field(default=0, ge=0)
    vault_share: float = Field(default=0, ge=0, le=1)  # this share of the vault's ore, as a taste of what is below


class DescentRules(_Data):
    floor: int = Field(ge=1)  # rows in the shaft; digging the last one reaches the vault
    rows_per_tier: int = Field(ge=1)
    # Pressure: every dig adds `creak` plus the hardness of each cell dug; vents and braces remove some.
    creak: float = Field(ge=0)
    default_hardness: float = Field(ge=0)
    empty_hardness: float = Field(ge=0)
    hardness: dict[str, float]  # item id -> pressure added when that ore is dug
    reactor_reduction: float = Field(ge=0)
    lifeline_pressure: float = Field(default=30.0, ge=0, le=100)  # Mastery capstone Lifeline: the pressure the reactor drops the mine to when it saves you
    lifeline_loss: float = Field(default=0.25, ge=0, le=1)  # ...the share of your unbanked haul that costs (a collapse takes `collapse_loss`)
    lifeline_runs: int = Field(default=4, ge=1)  # ...and how many mines the reactor needs to recharge afterwards (the one that saved you counts as the first)
    max_reduction: float = Field(ge=0, le=0.95)
    brace_amount: float = Field(ge=0)
    second_wind_item: str  # the Second Wind scroll: 1 in second_wind_odds banked runs that reached the top pressure label drop it
    second_wind_odds: int = Field(ge=1)
    braces_base: int = Field(ge=0)
    braces_per_reactor_levels: int = Field(ge=1)
    # Collapse risk is a smooth curve of pressure: 0 below `safe_pressure`, `max_risk` at 100.
    safe_pressure: float = Field(ge=0, lt=100)
    max_risk: float = Field(ge=0, le=1)
    risk_exponent: float = Field(ge=1)
    collapse_loss: float = Field(ge=0, le=1)
    power_yield_bonus: float = Field(ge=0)
    power_base: int = Field(ge=1)  # the pickaxe power that mines plain ore (x1): every point above it adds power_yield_bonus
    depth_bonus_per_row: float = Field(ge=0)  # every row deeper pays this much more (so going on is tempting)
    # Special cells. Plain cells show their ore; these show what they are.
    vent_chance: float = Field(ge=0, le=1)  # no loot, but cools the tunnel
    vent_relief: float = Field(ge=0)
    rich_chance: float = Field(ge=0, le=1)  # a mystery lode: rolls the NEXT tier's table, more of it
    rich_multiplier: float = Field(ge=1)
    cache_chance: float = Field(ge=0, le=1)  # supplies: +braces
    cache_min_depth: int = Field(ge=0)
    cache_braces: int = Field(ge=1)
    bomb_pressure: float = Field(ge=0)  # the Auto-Bomb charge clears a whole row for this flat pressure
    bomb_layers: int = Field(ge=1)  # rows a scarab bomb blows down, with no pressure added
    bombs_per_run: int = Field(ge=0)  # most bombs you can carry into one run
    lookahead: int = Field(ge=1, le=3)  # how many rows ahead you can see
    vault_gem_chance: float = Field(ge=0, le=1)  # chance the vault also holds one random reactor gem (gems are rare!)
    vault_ore: dict[str, int]
    warnings: list[RiskLabel] = Field(min_length=1)
    soft_below: float = Field(default=5, ge=0)  # a cell whose hardness is under this FEELS soft from above (copper, empty cells, vents and caches)...
    hard_from: float = Field(default=9, ge=0)  # ...and from this up it feels hard (gold): in between is firm (iron). Harder rock is where the better ore is
    milestones: list[Milestone] = Field(default_factory=list)  # landmark rows (10, 20...) that reward you; the vault is the last one

    @model_validator(mode="after")
    def _milestones_fit(self):
        if self.soft_below > self.hard_from:
            raise ValueError("soft_below must not be above hard_from")
        rows = [m.row for m in self.milestones]
        if rows != sorted(set(rows)) or any(not 1 <= r < self.floor for r in rows):
            raise ValueError("milestone rows must be different, climbing, and above the floor (the vault is the last landmark)")
        return self

    @model_validator(mode="after")
    def _warnings_ascend_from_zero(self):
        starts = [w.from_risk for w in self.warnings]
        if starts[0] != 0 or starts != sorted(starts) or len(set(starts)) != len(starts):
            raise ValueError("risk warnings must start at 0 and have strictly increasing `from_risk` values")
        return self


class MineScroll(_Data):
    """A scroll only one mine type can drop: 1 in `odds` banked runs of that type (settle_run rolls it)."""

    item: str
    odds: int = Field(ge=1)


class MineType(_Data):
    """One kind of mine you can roll when you head down (shown before you dig). Every effect is a plain number; 1.0 / 0 / {} changes nothing."""

    id: str
    name: str
    emoji_raw: str = Field(alias="emoji")
    weight: float = Field(gt=0)  # how often it is rolled, relative to the other types
    description: str
    pressure_mult: float = Field(default=1.0, ge=0.25, le=2.0)  # x the pressure every dig adds (0.8: calmer)
    xp_mult: float = Field(default=1.0, ge=0.5, le=3.0)  # x the mining xp the run pays
    yield_mult: float = Field(default=1.0, ge=0.5, le=3.0)  # x the quantity of every cell
    rich_chance_add: float = Field(default=0.0, ge=0, le=0.5)  # added to every cell's chance of being a rich lode
    wyrmhole_mult: float = Field(default=1.0, ge=1, le=20)  # x the chance of a big wyrmhole (per cell) and of a small one (per mine)
    ore_boost: dict[str, float] = Field(default_factory=dict)  # item -> x its drop chance (other ores stay possible; more of a hard ore also means more pressure)
    ore_yield: dict[str, float] = Field(default_factory=dict)  # item -> x the quantity of that item (no extra pressure)
    scroll: MineScroll | None = None  # the scroll this mine type alone can drop (see MineScroll)

    @model_validator(mode="after")
    def _boosts_are_sane(self):
        if any(not 1.0 <= m <= 5.0 for m in (*self.ore_boost.values(), *self.ore_yield.values())):
            raise ValueError(f"mine type '{self.id}': an ore_boost / ore_yield must be between 1 and 5")
        return self

    @property
    def emoji(self) -> str:
        """The bot's emoji named `mine_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("mine", self.id, self.emoji_raw)


class MineSite(_Data):
    """One of the 14 named mines ([[mines]] in mining.toml, in the order of the mining locations in locations.toml; the name and emoji come from there).
    `tables` are its own 5 depth tables (rarest first); leave them out to use the shared `depth_tables` (mine 1)."""

    id: str
    tables: list[list[str]] | None = Field(default=None, min_length=1)
    yield_mult: float = Field(default=1.0, gt=0)  # x the quantity of every cell here (deeper mines pay more per dig)
    hardness_mult: float = Field(default=1.0, gt=0)  # x the pressure every dig adds here (deeper rock is harder)


class MiningRules(_Data):
    columns: int = Field(ge=1)
    xp_per_column: int = Field(ge=0)
    depth_tables: list[list[str]] = Field(min_length=1)  # the tables of the first mine (and of the reactor's auto-mining)
    mines: list[MineSite] = Field(min_length=1)
    mine_types: list[MineType] = Field(min_length=1)
    wyrmhole: WyrmholeRules
    mini_wyrmhole: MiniWyrmholeRules
    reactor: ReactorRules
    magnet: MagnetRules
    scarab: ScarabRules
    descent: DescentRules

    @model_validator(mode="after")
    def _mine_types_are_sane(self):
        ids = [t.id for t in self.mine_types]
        if len(set(ids)) != len(ids):
            raise ValueError("mining.toml: mine type ids must be unique")
        if "standard" not in ids:
            raise ValueError("mining.toml: there must be a 'standard' mine type")
        standard = self.mine_type("standard")
        if (standard.pressure_mult, standard.xp_mult, standard.yield_mult, standard.rich_chance_add, standard.wyrmhole_mult, standard.ore_boost, standard.ore_yield) != (1.0, 1.0, 1.0, 0.0, 1.0, {}, {}):
            raise ValueError("mining.toml: the 'standard' mine type must change nothing")
        if standard.weight * 2 <= sum(t.weight for t in self.mine_types):
            raise ValueError("mining.toml: the 'standard' mine type must be at least half of all mines")
        return self

    def mine_type(self, type_id: str) -> MineType:
        return next(t for t in self.mine_types if t.id == type_id)

    def site(self, site_id: str) -> MineSite:
        return next(s for s in self.mines if s.id == site_id)

    def tables_of(self, site: "MineSite | None") -> list[list[str]]:
        """The 5 depth tables a mine digs through (the shared ones when it has none of its own)."""
        return site.tables if site is not None and site.tables else self.depth_tables


class MarketRules(_Data):
    """The Farmer's Market: open a couple of times a day (UTC), better prices, blessings for land deeds."""

    min_level: int = Field(ge=1)
    opens: list[int] = Field(min_length=1)  # UTC hours of day the market opens (each day, each of them)
    open_hours: int = Field(ge=1, le=12)  # how many hours it stays open each time (may run past midnight)
    price_bonus: float = Field(ge=0)  # +50% -> 0.5
    deed_chance: float = Field(ge=0, le=1)  # per blessing deposited


class FarmingRules(_Data):
    free_plots: int = Field(ge=1, le=9)  # plots you own from the start
    grow_chance: float = Field(gt=0, le=1)  # per rain (every hour), per growing plot
    blessing_chance: float = Field(ge=0, le=1)  # per rain in which something grew
    water_chance: float = Field(gt=0, le=1)  # watering a plot (once an hour) grows it a cycle with this chance (1: it always does)
    drop_cycles_per_roll: float = Field(gt=0)  # a harvest rolls the farming drop table once per this many of the crop's growth cycles...
    max_drop_rolls: int = Field(ge=1)  # ...but never more than this many times
    starter_seeds: dict[str, int]  # a free gift of seeds the first time you farm
    anomaly_odds: int = Field(ge=1)  # 1 in N per harvest
    anomaly_scroll: CropScroll | None = None  # the scroll an anomaly can drop: 1 in odds anomalies (Golden Sprout)
    xp_per_cycle: int = Field(ge=0)  # xp for a harvest = the seed's growth cycles x this: a long crop pays for the waiting
    deed_item: str
    field_seeds: list[str]  # the seed each field opens, in field order (14, one per farming location)
    zone_materials: list[list[str]]  # per farm zone (same order as field_seeds): the materials its plots' byproducts roll (Tend and harvest)
    byproduct_rolls: list[int] = Field(min_length=1)  # Tend: rolls of the farming drop table per growth cycle, by field (same order as field_seeds): bigger crops, bigger byproducts
    byproduct_max_cycles: int = Field(default=3, ge=1)  # a plot keeps at most this many cycles of byproducts waiting, so you collect by checking in often
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
    default_zone: int = Field(ge=1)      # its zone when nobody has chopped lately
    zone_below: int = Field(ge=0)        # its zone is picked from (the zone most recent choppers can reach) - this ...
    zone_above: int = Field(ge=0)        # ... to + this
    hp_per_active: float = Field(ge=0.1)  # hp = a typical tree of its zone x this x the number of recent choppers
    min_active: int = Field(ge=1)        # (counted as at least this many...
    max_active: int = Field(ge=1)        # ... and at most this many)
    recent_windows: int = Field(ge=1)    # "recent" = the choppers of this many past hours
    min_share: float = Field(ge=0, le=1)
    group_bonus: float = Field(ge=0)
    max_group_bonus: float = Field(ge=0)
    max_share: float = Field(gt=0, le=1, default=1.0)  # one chopper is paid for at most this share of the tree, however much of it they chopped alone
    pool_base: float = Field(gt=0, default=1.0)  # the share of the tree's worth paid out when ONE chopper did their share...
    pool_per_chopper: float = Field(ge=0, default=0.0)  # ...plus this for the second chopper...
    pool_decay: float = Field(ge=0, lt=1, default=0.0)  # ...and each further one adds this times what the one before did (diminishing returns)
    expired_factor: float = Field(ge=0, le=1)
    refresh_seconds: float = Field(gt=0)


class TreeScroll(_Data):
    """A scroll one tree species or one wood grain can drop: 1 in `odds` private trees felled with it (foraging rolls it once per source)."""

    item: str
    odds: int = Field(ge=1)


class Grain(_Data):
    """A kind of wood at the place you chop. It sets how hard the spot is to cut and how fast it wears out, and it wants one chop style."""

    id: str
    name: str
    multiplier: float = Field(gt=0)  # what it does to your damage (and xp): a clean grain is better than a knotty one
    weight: float = Field(gt=0)  # how often a new spot has this grain
    stance: Literal["o", "s", "u"]  # the one style it likes: o = overhead, s = sidecut, u = undercut
    wear: float = Field(gt=0)  # how fast a chop wears the spot out, relative to 1 (good grains last, bad ones go quickly)
    scroll: TreeScroll | None = None  # the scroll this grain alone can drop (see TreeScroll)


class Special(_Data):
    """A rare special spot. Chopped in the grain's right style it does something big; chopped wrong it is just a spot."""

    id: str
    name: str
    emoji: str
    effect: Literal["damage", "xp", "mark"]  # damage: x amount damage. xp: x amount xp for the chop. mark: +amount to the tree's rewards (capped)
    amount: float = Field(gt=0)
    weight: float = Field(gt=0)  # which special it is, among the specials
    wear: float = Field(gt=0)  # relative wear: special spots are short-lived (a big number)
    private_only: bool = False  # a mark only means something on a tree of your own


class Wedge(_Data):
    """A rotation wedge: a consumable item that moves you off a spot onto a new grain. Better ones tilt the roll toward good grains
    and make a special spot more likely."""

    item: str  # the item's id (it must exist in items.toml)
    bias: float = Field(ge=0)  # a new grain's weight is its weight x multiplier ** bias: 0 is a plain random pick
    special_mult: float = Field(ge=0, default=1.0)  # x the chance that the new spot is a special one
    boost: float = Field(ge=0, default=0.0)  # a lasting bonus: every chop hits (and pays xp) this much harder...
    boost_chops: int = Field(ge=0, default=0)  # ...for this many chops, wherever the spot moves


class RotateRules(_Data):
    wedges: list[Wedge] = Field(min_length=1)


class ChoppingRules(_Data):
    """How a swing works: the grain you are on, the one style it likes, how the spot wears, and good chops."""

    good_chop_chance: float = Field(ge=0, le=1)
    good_chop_bonus: float = Field(ge=0)  # +50% -> 0.5
    wrong_stance_factor: float = Field(gt=0, le=1)  # the wrong style chops at this share of the damage (and xp)
    wear_per_chop: float = Field(gt=0)  # a chop on a grain of wear 1 wears the spot out by this much (of a whole 1.0)
    wear_penalty: float = Field(ge=0, lt=1)  # a spot about to wear out chops at (1 - this) of its strength
    special_chance: float = Field(ge=0, le=1)  # the chance a new spot is a special one
    streak_bonus: float = Field(ge=0, default=0.0)  # damage added per right-style chop in a row on the same tree...
    streak_max: int = Field(ge=0, default=0)  # ...up to this many (so the most it can add is streak_bonus x streak_max)
    mark_cap: float = Field(ge=0)  # the most extra reward (+0.5 = +50%) marks can put on one tree
    ember_mult: float = Field(ge=1)  # Ember Bite: a smouldering trunk's next chops hit this much harder
    ember_chops: int = Field(ge=1)  # ...for this many chops
    timber_share: float = Field(ge=0, lt=1)  # Timber!: a tree it toppled into starts with this share of its hp gone
    grains: list[Grain] = Field(min_length=2)
    specials: list[Special] = Field(min_length=1)

    @model_validator(mode="after")
    def _grains_fit(self):
        if len({g.id for g in self.grains}) != len(self.grains):
            raise ValueError("grain ids must be unique")
        if {g.stance for g in self.grains} != {"o", "s", "u"}:
            raise ValueError("every stance needs at least one grain that wants it")
        if len({sp.id for sp in self.specials}) != len(self.specials) or all(sp.private_only for sp in self.specials):
            raise ValueError("special ids must be unique, and at least one special must work on shared trees")
        return self

    def grain(self, grain_id: str) -> Grain:
        return next(g for g in self.grains if g.id == grain_id)

    def special(self, special_id: str) -> Special:
        return next(sp for sp in self.specials if sp.id == special_id)


class ReleafRules(_Data):
    """The Releaf Foundation: the whole server gives rare foraging drops to one shared meter; when it fills, a temporary server-wide Bloom starts."""

    min_level: int = Field(ge=1)  # foraging level to give
    min_rarity: int = Field(ge=1, le=7)  # only items of this rarity or more can be given (a real loss, never the junk)
    points: dict[int, int] = Field(min_length=1)  # rarity -> meter points one item is worth (a rarity with no entry is not accepted)
    share_points: int = Field(ge=1)  # one forager's share of the goal; goal = share_points x active foragers
    share_cap: float = Field(gt=0)  # the most one player can give in one cycle, in shares (1.5 = 1.5 x share_points)
    min_foragers: int = Field(ge=1)  # the goal never counts fewer foragers than this
    active_days: float = Field(gt=0)  # a forager is active if they pressed anything within this many days (and have foraging level >= min_level)
    bloom_hours: float = Field(gt=0)  # how long a Bloom lasts
    bloom_xp: float = Field(ge=0)  # +this to every foraging xp reward during a Bloom (0.10 = +10%)
    bloom_drops: float = Field(ge=0)  # +this to every drop chance of foraging trees during a Bloom (0.10 = +10%)
    top_donors: int = Field(ge=1, default=5)  # how many names the donor list shows

    @model_validator(mode="after")
    def _check(self) -> "ReleafRules":
        if any(r < self.min_rarity or p < 1 for r, p in self.points.items()):
            raise ValueError("releaf points need a rarity of at least min_rarity and at least 1 point")
        return self

    def worth(self, rarity: int) -> int:
        """Meter points one item of this rarity is worth (0 = not accepted)."""
        return self.points.get(rarity, 0) if rarity >= self.min_rarity else 0


class PartyTreeRules(_Data):
    """A tree a party chops together: a little better rewards than the community tree for working as a team."""

    open_minutes: int = Field(ge=1, le=120)
    hp_per_member: float = Field(gt=0)  # tree hp = a typical tree of its zone x this x the party's size
    min_share: float = Field(ge=0, le=1)
    group_bonus: float = Field(ge=0)  # +this per extra member who did their share...
    max_group_bonus: float = Field(ge=0)  # ...up to this
    expired_factor: float = Field(ge=0, le=1)
    refresh_seconds: float = Field(gt=0)


class SpeciesDrop(_Data):
    """One signature drop of a tree species: `rate` is the chance PER DROP ROLL of the tree (0..1), then min..max of the item."""

    item: str  # must exist in items.toml
    rate: float = Field(gt=0, le=1)
    min: int = Field(ge=1)
    max: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max < self.min:
            raise ValueError("species drop max must be >= min")
        return self


class Species(_Data):
    """A kind of tree. Which one a tree is depends on its zone; it adds its own signature drops to the normal pool."""

    id: str
    name: str
    emoji_raw: str = Field(alias="emoji")
    zone_min: int = Field(ge=1)
    zone_max: int = Field(ge=1)
    weight: float = Field(gt=0)  # how common it is among the species of a zone
    drops: list[SpeciesDrop] = Field(default_factory=list)  # optional signature drops (none for now: the materials were cut)
    scroll: TreeScroll | None = None  # the scroll only this species can drop (see TreeScroll)

    _id = field_validator("id")(check_id)

    @model_validator(mode="after")
    def _ordered(self):
        if self.zone_max < self.zone_min:
            raise ValueError("species zone_max must be >= zone_min")
        return self

    def grows_in(self, zone: int) -> bool:
        return self.zone_min <= zone <= self.zone_max

    @property
    def emoji(self) -> str:
        """The bot's emoji named `species_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("species", self.id, self.emoji_raw)


class ForagingRules(_Data):
    zones: int = Field(ge=1)  # the forests (zone N = forest N); their unlock levels are areas.location_levels
    heavy_zone: int = Field(ge=1)
    heavy_solo_power: float = Field(gt=0, le=1)
    zone_hp_growth: float = Field(ge=0)
    xp_per_swing: float = Field(ge=0)  # xp for one chop at full quality. It does not depend on the axe: a better axe fells faster, it does not pay more xp
    bits_per_hp: int = Field(ge=0)
    hp_per_roll: int = Field(ge=1)
    zone_reward_growth: float = Field(ge=0)  # each zone above 1 pays this much more per hp (bits and drop rolls)
    heights: list[TreeHeight] = Field(min_length=1)
    chopping: ChoppingRules
    rotate: RotateRules
    community: CommunityRules
    party_tree: PartyTreeRules
    releaf: ReleafRules
    species: list[Species] = Field(default_factory=list)  # tree species by zone (empty: no species, trees are plain)

    def species_of(self, species_id: str) -> Species | None:
        return next((sp for sp in self.species if sp.id == species_id), None)

    def species_in(self, zone: int) -> list[Species]:
        return [sp for sp in self.species if sp.grows_in(zone)]

    @model_validator(mode="after")
    def _species_cover_zones(self):
        if len({sp.id for sp in self.species}) != len(self.species):
            raise ValueError("species ids must be unique")
        if self.species and (missing := [z for z in range(1, self.zones + 1) if not self.species_in(z)]):
            raise ValueError(f"species: no species grows in zone(s) {missing}")
        return self

    @model_validator(mode="after")
    def _zones_fit(self):
        if not 1 <= self.community.default_zone <= self.zones or self.community.min_active > self.community.max_active:
            raise ValueError("community default_zone must be a real zone and min_active <= max_active")
        return self


class BiteRules(_Data):
    wait_min: float = Field(gt=0)
    wait_max: float = Field(gt=0)
    speedup_per_power: float = Field(ge=0)
    min_wait_factor: float = Field(gt=0, le=1)
    window: float = Field(gt=0)
    grace: float = Field(ge=0)  # extra seconds nobody is told about, to forgive a laggy connection

    @model_validator(mode="after")
    def _ordered(self):
        if self.wait_max < self.wait_min:
            raise ValueError("bite wait_max must be >= wait_min")
        return self


class ReelRules(_Data):
    base_length: int = Field(ge=1)
    power_per_slip: int = Field(ge=1)
    slack_bonus: float = Field(ge=0)  # an unused slack (a forgiven wrong arrow you did not need) pays this share of the catch's worth, each
    max_slips: int = Field(ge=0)  # a rod forgives at most this many wrong arrows by its power alone (enchants add more)
    break_from_rarity: int = Field(ge=1)  # fish of this rarity and up make you stop and Reel now and then
    arrows_per_break: int = Field(ge=1)  # about one Reel break per this many arrows
    mystery_from_rarity: int = Field(ge=1)  # fish of this rarity and up hide some arrows behind a ❓
    window: int = Field(ge=1)  # how many upcoming steps you can see at once
    fog_window: int = Field(ge=1)  # ...and how many in a fog (a boss twist)
    echo_window: float = Field(ge=0)  # pressing the arrow you JUST pressed again within this many seconds is ignored


class QuestSlot(_Data):
    """One quest per slot: "catch N of a fish of this rarity" (which fish is picked per player and period)."""

    rarity: int = Field(ge=1, le=7)
    min_count: int = Field(ge=1)
    max_count: int = Field(ge=1)

    @model_validator(mode="after")
    def _ordered(self):
        if self.max_count < self.min_count:
            raise ValueError("quest max_count must be >= min_count")
        return self


class QuestRules(_Data):
    min_level: int = Field(ge=1)
    xp_per_rarity: int = Field(ge=0)  # a quest's xp = the fish's rarity x its count x this
    daily_bits_multiplier: float = Field(ge=0)  # a quest's bits = the fish's sell price x its count x this
    weekly_bits_multiplier: float = Field(ge=0)
    daily: list[QuestSlot] = Field(min_length=1)  # one daily quest per slot
    weekly: list[QuestSlot] = Field(min_length=1)


class BookRules(_Data):
    """The personal collection book: turn in fish, get rewards, finish it to level it up."""

    min_level: int = Field(ge=1)  # fishing level that opens it
    max_rarity: int = Field(ge=1, le=7)  # it holds every fish up to this rarity
    max_level: int = Field(ge=1)
    need_base: int = Field(ge=1)  # fish per entry at book level 1...
    # ...and for each level after, this many more per rarity (index 0 = common): common fish pile up fast, rare ones
    # barely grow. An entry needs need_base + floor((level - 1) x step).
    need_step_by_rarity: list[float] = Field(min_length=1)
    bits_per_sell: float = Field(ge=0)  # each fish turned in pays this share of its sell price
    xp_per_rarity: int = Field(ge=0)
    completion_bits: int = Field(ge=0)  # finishing the book pays this x its level...
    completion_xp: int = Field(ge=0)  # ...and this x its level

    @model_validator(mode="after")
    def _steps_cover_every_rarity(self):
        if len(self.need_step_by_rarity) < self.max_rarity or any(x < 0 for x in self.need_step_by_rarity):
            raise ValueError("need_step_by_rarity needs one non-negative number per rarity the book holds")
        return self


class TreasureLoot(_Data):
    item: str
    min: int = Field(ge=1)
    max: int = Field(ge=1)
    chance: float = Field(gt=0, le=1)


class TreasureRules(_Data):
    """Hallucinations and treasure chests."""

    hallucination_odds: int = Field(ge=1)  # 1 in N catches triggers a hallucination (4 numbers to remember)
    chest_odds: int = Field(ge=1)  # then 1 in N casts, while it lasts, brings up a chest instead of a fish
    armed_minutes: float = Field(gt=0)  # how long a hallucination keeps chests coming
    flash_seconds: float = Field(gt=0)  # how long the numbers stay on screen
    code_length: int = Field(ge=1, le=9)
    attempts: int = Field(ge=1)  # tries at the lock before the chest sinks
    bits_min: int = Field(ge=0)
    bits_max: int = Field(ge=0)
    xp: int = Field(ge=0)  # the least a chest pays...
    xp_level_fraction: float = Field(ge=0)  # ...or this share of the xp it takes to finish your current level, if more
    loot: list[TreasureLoot]


class CommunityBookRules(_Data):
    """The server-wide collection book: everyone donates the same few rare fish."""

    fish: list[str] = Field(min_length=1)
    max_level: int = Field(ge=1)
    need_base: dict[int, int]  # rarity -> how many of each fish at level 1
    need_step: dict[int, float]  # rarity -> more per level after (need = base + floor((level - 1) x step))
    donor_bits_per_sell: float = Field(ge=0)  # a donated fish pays its donor this share of its sell price
    donor_xp_per_rarity: int = Field(ge=0)
    completion_bits: int = Field(ge=0)  # everyone is paid this x the level when the book is finished...
    completion_xp: int = Field(ge=0)  # ...and this xp x the level


class MonthlySlot(_Data):
    """One community quest each month. kind: any fish | any fish of `rarity` or better | one specific fish of `rarity`."""

    kind: Literal["any", "rarity", "fish"]
    rarity: int = Field(default=1, ge=1, le=7)
    count: int = Field(ge=1)
    bits: int = Field(ge=0)
    xp: int = Field(ge=0)


class CommunityRules(_Data):
    book: CommunityBookRules
    monthly: list[MonthlySlot] = Field(min_length=1)
    min_share: float = Field(ge=0, le=1)  # you must have done this share of a goal to be paid for it


class FishingScroll(_Data):
    """A scroll one boss or one water alone can drop: 1 in `odds` boss fights landed (or catches in that water)."""

    item: str
    odds: int = Field(ge=1)


class BossEntry(_Data):
    """One boss and the twist that makes its reel different."""

    name: str
    modifiers: list[Literal["mirror", "reverse", "shuffle", "fog", "wild"]] = Field(min_length=1)
    scroll: FishingScroll | None = None  # the scroll only this boss can drop (defeat_boss rolls it)


class PartyBossRules(_Data):
    """A boss hooked by a party member can be joined by the rest of the party: each reels their OWN set of arrows, and every one who lands theirs is paid."""

    fight_seconds: int = Field(ge=30)  # how long the fight stays open for joining and reeling, from the moment it is hooked
    bonus_per_extra: float = Field(ge=0)  # +this share of the reward for every EXTRA member who lands their reel
    max_bonus: float = Field(ge=0)  # ...up to this much


class BossRules(_Data):
    """A boss on your line: a long reel with no fish of its own at the end, just a big pile of rewards."""

    party: PartyBossRules

    odds: int = Field(ge=1)  # 1 in N casts
    length: int = Field(ge=1)  # arrows to press
    bosses: list[BossEntry] = Field(min_length=1)
    modifier_text: dict[str, str]  # what each twist means, as shown to the player
    wild_mysteries: int = Field(ge=1)  # a "wild" boss hides this many arrows behind coin-flip ❓
    bits_min: int = Field(ge=0)
    bits_max: int = Field(ge=0)
    xp: int = Field(ge=0)
    loot: list[TreasureLoot]


class RecordRules(_Data):
    personal_xp_per_rarity: int = Field(ge=0)  # a new personal best pays rarity x this xp
    server_bits_multiplier: float = Field(ge=0)  # a new server record pays the fish's sell price x this in bits


class WaterRules(_Data):
    """A place to fish (one per fishing location, same order as configs/locations.toml): its own fish (each `fish = N` means 1 in N,
    rarest rolled first). Its name and emoji come from the location (the loader fills them in), and its unlock level from areas."""

    id: str
    name: str = ""
    emoji_raw: str = Field(default="🌊", alias="emoji")
    description: str = ""
    wait_multiplier: float = Field(gt=0)  # deeper water takes longer to bite
    xp: int = Field(ge=0)  # xp for every fish landed here: deeper waters pay more, a better rod never does
    fish: dict[str, int] = Field(min_length=1)
    scroll: FishingScroll | None = None  # the scroll only this water can drop (land rolls it per catch here)

    @property
    def emoji(self) -> str:
        """The bot's emoji named `water_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("water", self.id, self.emoji_raw)


class PotLevel(_Data):
    """One level of crab pot: how often it catches, how many catches it holds, and what it takes to reach this level."""

    interval_minutes: float = Field(gt=0)
    capacity: int = Field(ge=1)
    upgrade_bits: int = Field(ge=0)
    upgrade_items: dict[str, int] = Field(default_factory=dict)


class PotRules(_Data):
    """Crab pots: craft them, load bait, and they catch rare fish while you are away. An extra, never the main earner."""

    min_level: int = Field(ge=1)  # fishing level to have one
    slot_levels: list[int] = Field(min_length=1)  # the fishing levels at which you may own 1, 2, 3... pots
    min_rarity: int = Field(ge=1, le=7)  # a pot only brings up fish of this rarity or better
    xp_factor: float = Field(ge=0)  # a catch gives this share of the xp it would from your rod
    craft_bits: int = Field(ge=0)
    craft_items: dict[str, int]
    levels: list[PotLevel] = Field(min_length=1)


class RodRules(_Data):
    luck_per_power: float = Field(ge=0)  # every point of rod power above 3 makes the rare fish (rarity 4+) this much likelier
    extra_fish_per_power: float = Field(ge=0)  # ...and adds this to the number of EXTRA fish a catch brings (1.2 = one, and a 20% chance of two)
    low_rarity_boost: float = Field(ge=1)  # a rarity-1 fish multiplies that extra-fish number by this...
    low_rarity_cutoff: int = Field(ge=2)  # ...fading linearly to 1x at this rarity and above


class RadarLevel(_Data):
    """One step of the radar: how much likelier your chosen fish are, how many you can chase at once, and what the upgrade into it costs."""

    multiplier: float = Field(gt=1)
    slots: int = Field(ge=1)
    bits: int = Field(ge=0)
    items: dict[str, int] = Field(default_factory=dict)


class RadarRules(_Data):
    unlock_level: int = Field(ge=1)  # fishing level that opens the radar
    battery: str  # the item one cast with the radar on uses up
    levels: list[RadarLevel] = Field(min_length=1)  # level 1 first; owning level N gives levels[N - 1]


class DoubleHookRules(_Data):
    """Double Hook: after a plain landing, a free "Quick cast" may be offered (the chance comes from the ``double_hook`` stat)."""

    base_chance: float = Field(ge=0, le=1)  # added to everyone's stat (0 = only the enchant and the Mastery node)
    window_seconds: float = Field(gt=0)  # how long the offer stays on the result page
    cap: float = Field(gt=0, le=1)  # the chance never goes above this


class NetRules(_Data):
    """Net Cast: one net hauls this many of the water's commonest fish at once, then it cools down."""

    fish: int = Field(ge=1)
    cooldown_seconds: int = Field(ge=0)  # between two nets


class FishingRules(_Data):
    xp_per_catch: int = Field(ge=0)  # xp for landing a fish when the water does not set its own: one catch pays the same whatever the fish or the rod
    xp_per_rarity: int = Field(ge=0)
    bite: BiteRules
    reel: ReelRules
    rod: RodRules
    quests: QuestRules
    book: BookRules
    treasure: TreasureRules
    community: CommunityRules
    records: RecordRules
    boss: BossRules
    waters: list[WaterRules] = Field(min_length=1)
    pots: PotRules
    radar: RadarRules
    double_hook: DoubleHookRules
    net: NetRules


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


class PetRules(_Data):
    max_level: int = Field(ge=1)
    xp_scale: dict[int, int]  # by pet rarity: a pet's level = 1 + sqrt(xp / its rarity's scale), up to max_level (common pets level quickest)
    max_stars: int = Field(ge=1)
    star_bonus: float = Field(ge=0)  # each star after the first makes every bonus this much bigger
    level_floor: float = Field(gt=0, le=1)  # a level-1 pet gives this share of its bonus; max level gives all of it
    play_xp_share: float = Field(ge=0)  # your ACTIVE pet gains this share of the xp you earn in its own skill, just by playing
    play_xp_global: float = Field(ge=0)  # a pet with no skill (global) gains this share of the xp from every skill
    spirit_bonus: float = Field(ge=0)  # a Spirit given to a pet: +this xp in its skill while that pet is active
    food_xp: list[int] = Field(min_length=3, max_length=3)  # pet xp of a tier 1, 2 and 3 food
    matched_food_multiplier: float = Field(ge=1)  # food of the pet's own skill is worth this many times as much...
    global_food_multiplier: float = Field(ge=1)  # ...and to a pet with no skill, any food is worth this many times as much
    maxed_xp: int = Field(ge=0)  # a duplicate of a pet that already has every star gives it this much xp
    target_boost: float = Field(ge=1)  # a targeted pet is this many times likelier from an orb...
    pity_boost: float = Field(ge=0)  # ...plus this much more for every orb that missed it
    max_boost: float = Field(ge=1)  # ...but never more than this many times
    orbs: dict[str, dict[int, float]]  # orb item id -> chance weight of each pet rarity when you open that orb


class StarAnchor(_Data):
    """One point of the star curve: at `progress` (0 = the first forest / the top of the mine / the shallowest water, 1 = the deepest) a starrable
    drop is plain, 1, 2 or 3 stars with these relative weights. Between anchors the weights are blended in a straight line."""

    progress: float = Field(ge=0, le=1)
    weights: list[float] = Field(min_length=4, max_length=4)  # no star, 1-star, 2-star, 3-star

    @model_validator(mode="after")
    def _sane(self):
        if any(w < 0 for w in self.weights) or sum(self.weights) <= 0:
            raise ValueError("star weights must be non-negative and not all zero")
        if self.weights[3] >= sum(self.weights) / 2:
            raise ValueError("3-star must never be the majority drop")
        return self


class StarRules(_Data):
    """Starred materials: a material in `starrable` also exists as `<id>_s1`, `<id>_s2` and `<id>_s3` (1-, 2- and 3-star), each its own inventory stack.
    The plain id is the no-star one (the default drop; stars are the special, better ones). Stars only drop, they are never crafted up. Which star drops where is `configs/stars.toml` (later)."""

    sell_multipliers: list[float] = Field(default_factory=lambda: [1.0, 1.5, 2.5, 6.0], min_length=4, max_length=4)  # sell price of plain, 1, 2, 3 stars x the base
    starrable: list[str] = Field(default_factory=list)
    curve: list[StarAnchor] = Field(default_factory=lambda: [StarAnchor(progress=0, weights=[1, 0, 0, 0]), StarAnchor(progress=1, weights=[1, 0, 0, 0])])

    @model_validator(mode="after")
    def _climbing(self):
        m = self.sell_multipliers
        if m[0] != 1.0 or any(b <= a for a, b in zip(m, m[1:], strict=False)):
            raise ValueError("stars.sell_multipliers must start at 1 and climb")
        marks = [a.progress for a in self.curve]
        if marks[0] != 0 or marks[-1] != 1 or any(b <= a for a, b in zip(marks, marks[1:], strict=False)):
            raise ValueError("stars.curve must run from progress 0 to 1, in order")
        return self


class EconomyRules(_Data):
    stars: StarRules = Field(default_factory=StarRules)
    pets: PetRules
    token_drop_chance: float = Field(ge=0, le=1)  # each hour you play (press anything), this chance of finding a token
    party_idle_hours: float = Field(gt=0)  # a party member who has pressed nothing for this long is removed from their party
    party_xp_bonus_by_size: list[float] = Field(min_length=1)  # skill xp bonus for a party of 2, 3, ... (the last applies to bigger ones)
    starting_luckbucks: int = Field(ge=0)
    weekly_luckbucks: int = Field(ge=0)
    minigames: MinigameRules
    exchange: ExchangeRules


# ---- Bestiary (configs/bestiary.toml) ------------------------------------------------------------------------------------------------
class BestiaryRules(_Data):
    steps: list[int] = Field(min_length=1)  # the goals the page shows next for a monster
    boss_steps: list[int] = Field(min_length=1)
    fish_steps: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def _ascending(self):
        for steps in (self.steps, self.boss_steps, self.fish_steps):
            if steps != sorted(set(steps)) or steps[0] < 1:
                raise ValueError("bestiary steps must climb from at least 1")
        return self


# ---- Mastery: a small tree per skill; points come from skill levels, every node is a choice -----------------------------------------
class MasteryEffect(_Data):
    stat: str  # the same names tools and enchants use (danger_reduction, ore_yield, bite_speed, slips...)
    amount: float  # may be negative: a trade-off


class MasteryNode(_Data):
    id: str
    name: str
    description: str
    level: int = Field(ge=1)  # the skill level it needs
    cost: int = Field(ge=1)  # mastery points
    effects: list[MasteryEffect] = Field(min_length=1)


class MasteryBranch(_Data):
    id: str
    name: str
    emoji: str
    description: str
    nodes: list[MasteryNode] = Field(min_length=1)  # in order: each needs the one before it


class MasteryTree(_Data):
    skill: Skill
    branches: list[MasteryBranch] = Field(min_length=2)


class MasteryRules(_Data):
    points_every_levels: int = Field(ge=1)  # one point per this many skill levels
    respec_bits: int = Field(ge=0)  # clearing a tree costs this
    trees: list[MasteryTree] = Field(min_length=1)

    @model_validator(mode="after")
    def _fit(self):
        ids = [n.id for t in self.trees for b in t.branches for n in b.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("mastery node ids must be unique")
        if len({t.skill for t in self.trees}) != len(self.trees):
            raise ValueError("one mastery tree per skill")
        for t in self.trees:
            for b in t.branches:
                levels = [n.level for n in b.nodes]
                if levels != sorted(levels):
                    raise ValueError(f"mastery branch {b.id}: node levels must not go down")
        return self

    def tree(self, skill: str) -> "MasteryTree | None":
        return next((t for t in self.trees if t.skill == skill), None)

    def node(self, node_id: str) -> "MasteryNode":
        return next(n for t in self.trees for b in t.branches for n in b.nodes if n.id == node_id)


# ---- what tool power gives besides its main effect (configs/tools.toml) -----------------------------------------------------------------
class PathWeights(_Data):
    """How much of each power-derived extra a road of a forked tool keeps (1 is the normal amount, 0 none of it): a road leans one way."""

    danger_reduction: float = Field(default=1.0, ge=0)
    rich_chance: float = Field(default=1.0, ge=0)
    braces: float = Field(default=1.0, ge=0)


class PickaxePower(_Data):
    danger_reduction: float = Field(ge=0)
    rich_chance: float = Field(ge=0)
    braces_every: int = Field(ge=1)
    paths: dict[str, PathWeights] = Field(default_factory=dict)  # by road name (Warden, Prospector); a tool on no road gets the normal amount


class AxePower(_Data):
    good_chop: float = Field(ge=0)
    wear_slow: float = Field(ge=0)
    paths: dict[str, dict[str, float]] = Field(default_factory=dict)  # by road name (Lumberjack, Forager): a factor on each stat above (missing = 1)


class CanPower(_Data):
    crop_yield: float = Field(ge=0)
    drop_luck: float = Field(ge=0)
    seed_back: float = Field(ge=0, le=1)
    paths: dict[str, dict[str, float]] = Field(default_factory=dict)  # by road name (Sprinkler, Alchemist): a factor on each stat above (missing = 1)


class SwordPower(_Data):
    hp: float = Field(ge=0)
    defense: float = Field(ge=0)


class ToolRules(_Data):
    pickaxe: PickaxePower
    axe: AxePower
    can: CanPower
    sword: SwordPower


# ---- Shipments (configs/shipments.toml) ------------------------------------------------------------------------------------------------
class ShipmentTier(_Data):
    """One kind of personal crate (every skill has one of each tier, once its level reaches `unlock_level`)."""

    unlock_level: int = Field(ge=1)
    kinds: int = Field(ge=2)  # different materials in the crate
    theme_kinds: int = Field(ge=1)  # of which this many are from the crate's own skill
    value_base: int = Field(ge=1)  # bits' worth of materials at skill level 1...
    value_per_level: int = Field(ge=0)  # ...plus this per level of that skill
    bits_factor: float = Field(gt=0)
    xp_per_bit: float = Field(ge=0)

    @model_validator(mode="after")
    def _fit(self):
        if self.theme_kinds >= self.kinds:
            raise ValueError("a shipment must leave room for other skills' materials")
        return self


class PersonalShipments(_Data):
    rate_per_level: int = Field(ge=1)
    foreign_share: float = Field(ge=0, lt=0.5)  # the share of a crate's value that may come from OTHER skills' materials, all together
    foreign_max_quantity: int = Field(ge=1)  # the most of any one foreign material (so it is never a pile of the cheapest thing)
    tiers: dict[str, ShipmentTier] = Field(min_length=1)  # in page order: basic first


class CommunityShipments(_Data):
    enabled: bool = True  # off: the page does not show it (the rules and saved state stay)
    value_per_player: int = Field(ge=1)
    value_per_level: int = Field(ge=0)
    active_days: int = Field(ge=1)
    min_players: int = Field(ge=1)
    kinds: int = Field(ge=2)
    min_share: float = Field(ge=0, le=1)
    bits_factor: float = Field(gt=0)
    xp: int = Field(ge=0)


class ScrollSource(_Data):
    """Where one skill's scrolls come from: a 1-in-`odds` chance per roll (a cell dug, a tree felled, a growth cycle harvested), then one of `pool`."""

    odds: int = Field(ge=2)
    pool: list[str] = Field(min_length=1)


class ScrollRules(_Data):
    mining: ScrollSource | None = None  # no mining scrolls for now (their enchant was retired); the loader and roll skip a missing source
    foraging: ScrollSource | None = None  # none: foraging's scrolls come from one species or grain each (TreeScroll)
    farming: ScrollSource | None = None  # none: farming's scrolls come from one crop or from anomalies each (CropScroll)


class ShipmentRules(_Data):
    personal: PersonalShipments
    community: CommunityShipments


# ---- Areas and the ship (configs/areas.toml) -------------------------------------------------------------------------------------------
class Overdrive(_Data):
    """What burning an area's fuel gives for a while, in every skill: more skill xp and more of every drop (`drop_amount`)."""

    xp: float = Field(ge=0)
    drop_amount: float = Field(ge=0)


class Area(_Data):
    """One area of the world. Each area holds LOCATIONS_PER_AREA locations of every skill (see AreaRules.location_levels).
    `fuel` is what the ship burns to get here for the FIRST time; going back to an area you reached is free."""

    id: str
    name: str
    emoji_raw: str = Field(alias="emoji")
    description: str
    fuel: dict[str, int] = Field(default_factory=dict)  # item -> quantity burned on the first trip here
    overdrive: Overdrive | None = None  # the boost burning this fuel gives anywhere (needs `fuel`)

    @property
    def emoji(self) -> str:
        """The bot's emoji named `area_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("area", self.id, self.emoji_raw)


class ShipTier(_Data):
    """One ship upgrade: tier N lets you sail to area N (tier 1 builds the ship). Costs bits, materials and a level floor in each skill."""

    name: str
    emoji_raw: str = Field(alias="emoji")
    bits: int = Field(ge=0)
    parts: dict[str, int]
    skill_floors: dict[str, int]  # skill -> the level you need in it

    @property
    def emoji(self) -> str:
        """The bot's emoji named `ship_<name as a slug>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("ship", re.sub(r"[^a-z0-9]+", "_", self.name.lower()).strip("_"), self.emoji_raw)


LOCATIONS_PER_AREA = 2


class AreaRules(_Data):
    areas: list[Area] = Field(min_length=2)  # in travel order: the starting area first
    location_levels: list[int]  # the skill level that opens location n (1-based n = index + 1), the same for every skill; two per area
    ship_tiers: list[ShipTier] = Field(min_length=1)  # one per area after the first
    overdrive_minutes: int = Field(default=60, ge=1)  # one burned fuel adds this long
    overdrive_max_minutes: int = Field(default=180, ge=1)  # the timer never goes past this

    @model_validator(mode="after")
    def _fit(self):
        if len(self.ship_tiers) != len(self.areas) - 1:
            raise ValueError("needs one ship tier per area after the first")
        if len({a.id for a in self.areas}) != len(self.areas):
            raise ValueError("area ids must be unique")
        if self.areas[0].fuel:
            raise ValueError("the first area is where you start: it needs no fuel")
        if any(bool(a.fuel) != bool(a.overdrive) for a in self.areas):
            raise ValueError("every area with fuel needs an overdrive (and only those)")
        levels = self.location_levels
        if len(levels) != LOCATIONS_PER_AREA * len(self.areas):
            raise ValueError(f"locations.min_levels needs {LOCATIONS_PER_AREA} levels per area ({LOCATIONS_PER_AREA * len(self.areas)})")
        if levels[0] != 1 or levels != sorted(set(levels)):
            raise ValueError("locations.min_levels must start at 1 and strictly climb")
        return self


class Location(_Data):
    """One named location of a skill (configs/locations.toml). `n` is its 1-based unlock order; `area` and `min_level` are derived
    from it (area = the n-th pair of locations, min_level = AreaRules.location_levels[n - 1]), so they are not written in the TOML."""

    skill: str
    n: int = Field(ge=1)
    id: str
    name: str
    emoji_raw: str = Field(alias="emoji")
    area: str  # area id
    min_level: int = Field(ge=1)

    @property
    def emoji(self) -> str:
        """The bot's emoji named `location_<id>` if uploaded, else the one in the data file (see `cococap.emojis`)."""
        return emojis.for_id("location", self.id, self.emoji_raw)


class Recipe(_Data):
    """One thing the Workbench makes (configs/recipes.toml): `inputs` and `bits` are used up, `quantity` of `output` is made.
    `skill` + `min_level` (optional) ask for a level in a skill first."""

    id: str
    name: str
    emoji: str | None = None
    output: str
    quantity: int = Field(default=1, ge=1)
    inputs: dict[str, int] = Field(min_length=1)
    bits: int = Field(default=0, ge=0)
    skill: Skill | None = None
    min_level: int = Field(default=0, ge=0)

    _id = field_validator("id")(check_id)

    @field_validator("inputs")
    @classmethod
    def _positive(cls, inputs: dict[str, int]) -> dict[str, int]:
        if any(q < 1 for q in inputs.values()):
            raise ValueError("every input quantity must be at least 1")
        return inputs

    @model_validator(mode="after")
    def _level_needs_skill(self):
        if self.min_level and not self.skill:
            raise ValueError("min_level needs a skill")
        return self


class Notice(_Data):
    """A message for players (configs/notices.toml): pops up once per player, then stays on More -> News -> Messages."""

    id: str
    date: date
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=1500)  # one per popup page and per Messages page, well under Discord's limits

    _id = field_validator("id")(check_id)


class ChangelogEntry(_Data):
    """One changelog entry (configs/changelog.toml): a full write-up when `major`, else one grouped list of small changes."""

    date: date
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=1500)
    major: bool = False


# ---- Smithing (configs/smithing.toml) ----------------------------------------------------------------------------------------------
PART_TIERS = 8  # a part's tier IS its rarity (1 Common .. 7 Premium, 8 Celestial)


class AreaWeights(_Data):
    area: int = Field(ge=1)
    weights: list[int] = Field(min_length=PART_TIERS, max_length=PART_TIERS)

    @field_validator("weights")
    @classmethod
    def _weights_sane(cls, v: list[int]) -> list[int]:
        if any(w < 0 for w in v) or sum(v) <= 0:
            raise ValueError("weights must be >= 0 and not all zero")
        return v


class SmithTrait(_Data):
    id: str
    name: str
    stat: str
    amounts: list[float] = Field(min_length=4, max_length=4)  # one per quality grade
    kinds: list[ToolKind] = Field(min_length=1)

    _id = field_validator("id")(check_id)


class Quality(_Data):
    name: str
    mult: float = Field(gt=0)
    base_odds: int = Field(ge=0)


class SmithLevels(_Data):
    xp_per_smith: int = Field(ge=0)
    xp_per_salvage: int = Field(ge=0)
    quality_shift_per_level: float = Field(ge=0)
    swap_unlock_level: int = Field(ge=1)
    max_tier_by_level: list[tuple[int, int]] = Field(min_length=1)


class LegacyGrant(_Data):
    """What an old upgrade-chain tool of this step turns into at the one-time reset: 3 parts of `tier`, each with `traits` traits."""

    step: Literal["plain", "fork", "fork_up"]
    tier: int = Field(ge=1, le=PART_TIERS)
    traits: int = Field(ge=0, le=3)


class LegacyTool(_Data):
    """A frozen record of one OLD upgrade-chain tool (configs/legacy_tools.toml), kept after its template leaves items.toml,
    so the one-time reset can still tell its kind and how far it got."""

    kind: ToolKind
    step: Literal["starter", "plain", "fork", "fork_up"]


class RestrictedRules(_Data):
    chance: float = Field(0.02, ge=0, le=1)


class RemovalRules(_Data):
    enchant_unlock_level: int = Field(20, ge=1)


class SmithingRules(_Data):
    part_types: list[str] = Field(min_length=3, max_length=3)
    area_cap: int = Field(ge=0)
    max_traits: int = Field(ge=1)
    bonus_trait_chance: float = Field(ge=0, le=1)
    cosmetic_chance: float = Field(ge=0, le=1)
    part_drop_chance: float = Field(ge=0, le=1)
    tiers: dict[str, list[int]]  # {"power": [...]}: power per part tier, index 0 = tier 1
    area_weights: list[AreaWeights] = Field(min_length=1)
    trait_pool: list[SmithTrait] = Field(alias="trait", min_length=1)
    fresh_traits: list[int] = Field(min_length=PART_TIERS, max_length=PART_TIERS)  # traits a fresh part rolls, by tier
    grades: list[Quality] = Field(alias="quality", min_length=1)
    levels: SmithLevels
    legacy_grants: list[LegacyGrant] = Field(alias="legacy_grant", min_length=3, max_length=3)
    restricted: RestrictedRules = RestrictedRules()
    removal: RemovalRules = RemovalRules()
    legacy_scroll_cap: int = Field(2, ge=0)  # most scrolls the one-time reset gives back per player

    @model_validator(mode="after")
    def _sane(self):
        if sorted(g.step for g in self.legacy_grants) != ["fork", "fork_up", "plain"]:
            raise ValueError("legacy_grant needs one row each for plain, fork and fork_up")
        if self.part_types != ["base", "trim", "accent"]:
            raise ValueError("part_types must be exactly base, trim, accent")
        power = self.tiers.get("power", [])
        if len(power) != PART_TIERS or any(b <= a for a, b in zip(power, power[1:], strict=False)):
            raise ValueError(f"tiers.power must be {PART_TIERS} strictly increasing ints")
        ids = [t.id for t in self.trait_pool]
        if len(set(ids)) != len(ids):
            raise ValueError("trait ids must be unique")
        if any(n < 0 for n in self.fresh_traits):
            raise ValueError("fresh_traits must be >= 0")
        if self.max_traits != 3:
            raise ValueError("max_traits must be 3")
        mults = [q.mult for q in self.grades]
        if any(b <= a for a, b in zip(mults, mults[1:], strict=False)):
            raise ValueError("quality mults must increase in order")
        return self

    def fresh_trait_count(self, tier: int) -> int:
        return self.fresh_traits[tier - 1]

    @staticmethod
    def part_rarity(tier: int) -> int:
        """A part's rarity is its tier (owner decision): tier 1 Common ... 7 Premium, 8 Celestial."""
        return tier

    def tier_power(self, tier: int) -> int:
        return self.tiers["power"][tier - 1]

    def max_tier_for_area(self, area: int) -> int:
        return min(PART_TIERS, area + self.area_cap)

    def weights_for_area(self, area: int) -> list[int]:
        """Drop weights for tiers 1..8 in this area, with anything above the area cap zeroed (ignored)."""
        row = next(w for w in self.area_weights if w.area == area)
        cap = self.max_tier_for_area(area)
        return [w if i + 1 <= cap else 0 for i, w in enumerate(row.weights)]

    def trait(self, trait_id: str) -> SmithTrait:
        return next(t for t in self.trait_pool if t.id == trait_id)

    def traits_for(self, kind: str) -> list[SmithTrait]:
        return [t for t in self.trait_pool if kind in t.kinds]

    def quality(self, name: str) -> Quality:
        return next(q for q in self.grades if q.name == name)


# ---- Accessories (configs/accessories.toml) ----------------------------------------------------------------------------------
ACCESSORY_SKILLS = ("mining", "foraging", "fishing", "farming")
ACCESSORY_RARITIES = 7


class AccessoryTrait(_Data):
    id: str
    name: str
    stat: str  # a stat the engines read (the same names enchants and part traits use)
    amount: float = Field(gt=0)  # value on a rarity-1 accessory; a rarer one multiplies it (AccessoryRules.value)
    skills: list[str] = Field(min_length=1)

    @field_validator("skills")
    @classmethod
    def _skills_known(cls, v: list[str]) -> list[str]:
        if any(s not in ACCESSORY_SKILLS for s in v):
            raise ValueError(f"accessory trait skills must be among {ACCESSORY_SKILLS}")
        return v


class AccessoryTemplate(_Data):
    id: str  # acc_<skill>_<name>
    name: str
    skill: str
    rarity: int = Field(ge=1, le=ACCESSORY_RARITIES)
    stats: dict[str, float] = Field(default_factory=dict)  # the accessory's own base bonus
    shop_price: int = Field(default=0, ge=0)  # bits in the Shop (0 = drop only)

    @field_validator("skill")
    @classmethod
    def _skill_known(cls, v: str) -> str:
        if v not in ACCESSORY_SKILLS:
            raise ValueError(f"accessory skill must be among {ACCESSORY_SKILLS}")
        return v


class AccessoryRules(_Data):
    slots_per_skill: int = Field(ge=1, le=5)
    drop_chance: float = Field(ge=0, le=1)
    traits_by_rarity: list[int] = Field(min_length=ACCESSORY_RARITIES, max_length=ACCESSORY_RARITIES)
    rarity_mult: list[float] = Field(min_length=ACCESSORY_RARITIES, max_length=ACCESSORY_RARITIES)
    trait_pool: list[AccessoryTrait] = Field(alias="trait", min_length=1)
    templates: list[AccessoryTemplate] = Field(alias="accessory", min_length=1)

    @model_validator(mode="after")
    def _sane(self):
        ids = [t.id for t in self.trait_pool]
        if len(set(ids)) != len(ids):
            raise ValueError("accessory trait ids must be unique")
        tids = [t.id for t in self.templates]
        if len(set(tids)) != len(tids):
            raise ValueError("accessory ids must be unique")
        for t in self.templates:
            if not t.id.startswith(f"acc_{t.skill}_"):
                raise ValueError(f"accessory '{t.id}' must be named acc_{t.skill}_<name>")
        if any(n < 0 for n in self.traits_by_rarity) or any(m <= 0 for m in self.rarity_mult):
            raise ValueError("traits_by_rarity must be >= 0 and rarity_mult > 0")
        return self

    def template(self, template_id: str) -> AccessoryTemplate:
        return next(t for t in self.templates if t.id == template_id)

    def trait(self, trait_id: str) -> AccessoryTrait:
        return next(t for t in self.trait_pool if t.id == trait_id)

    def traits_for(self, skill: str) -> list[AccessoryTrait]:
        return [t for t in self.trait_pool if skill in t.skills]

    def trait_count(self, rarity: int) -> int:
        return self.traits_by_rarity[rarity - 1]

    def value(self, trait: AccessoryTrait, rarity: int) -> float:
        return trait.amount * self.rarity_mult[rarity - 1]


# ---- Part market (configs/market.toml) ---------------------------------------------------------------------------------------------
class MarketShop(_Data):
    """One shop that sells smithing parts for bits. Its stock is rerolled every `refresh_seconds` (services/market.py)."""

    name: str
    unlock_area: str  # area id; the shop stays closed until you have reached it
    refresh_seconds: int = Field(ge=60)
    slots: int = Field(ge=1, le=10)
    tier_weights: list[int] = Field(min_length=PART_TIERS, max_length=PART_TIERS)  # tiers 1..8
    extra_traits: int = Field(ge=0, le=3)  # added to the tier's fresh trait count (capped at the pool)
    tier_price: list[int] = Field(min_length=PART_TIERS, max_length=PART_TIERS)  # bits per part, by tier
    trait_premium: float = Field(ge=0)  # price x (1 + this x traits)

    @field_validator("tier_weights")
    @classmethod
    def _weights_sane(cls, v: list[int]) -> list[int]:
        if any(w < 0 for w in v) or sum(v) <= 0:
            raise ValueError("tier_weights must be >= 0 and not all zero")
        return v


class MarketRules(_Data):
    merchant: MarketShop
    black_market: MarketShop
