"""Typed game-data models. One instance per entry in ``configs/*.toml``.

All models are frozen and reject unknown keys, so a typo in a data file fails at startup with the
file/entry named, instead of surfacing as an AttributeError in the middle of a command.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cococap import emojis

Skill = Literal["farming", "foraging", "fishing", "mining", "combat", "shepherding"]
Category = Literal["material", "tool", "key_item", "pet_item", "pet_food", "crop", "seed", "fish", "scroll", "bait"]
ToolKind = Literal["pickaxe", "axe", "sword", "rod", "can"]

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


class Bait(_Data):
    """Bait for crab pots: each catch uses one. `luck` multiplies the chance of rare fish (rarity 4+), `speed` the catches per hour."""

    luck: float = Field(gt=0)
    speed: float = Field(gt=0)


class ReelTell(_Data):
    """How a fish's mystery arrow (❓) behaves. left/right: always that arrow. same/opposite: the arrow before it, or its
    opposite. random: a fresh coin flip every time (can't be learned, only gambled on)."""

    tell: Literal["left", "right", "same", "opposite", "random"]


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

    _id = field_validator("id")(check_id)

    @model_validator(mode="after")
    def _category_matches_sections(self):
        for section, category in (("crop", "crop"), ("seed", "seed")):
            if (getattr(self, section) is not None) != (self.category == category):
                raise ValueError(f"'{section}' section must be present iff category is '{category}'")
        if (self.pet_food is not None) != (self.category == "pet_food"):
            raise ValueError("'pet_food' section must be present iff category is 'pet_food'")
        if self.category == "pet_food" and not self.skill:
            raise ValueError("pet food belongs to a skill")
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


class PetBonus(_Data):
    """One thing a pet does while it is your active pet. `stat` is what the game looks up (see services/pets.py)."""

    stat: str
    value: float = Field(gt=0)  # at one star and the TOP level (a fresh pet gives about half; see [pets] level_floor in economy.toml)
    text: str  # how it reads, with {v} for the number


class Pet(_Data):
    id: str
    name: str
    skill: Literal["global", "mining", "farming", "foraging", "fishing", "combat"] = "global"  # the one skill it looks after
    emoji: str | None = None
    rarity: int = Field(default=1, ge=1, le=5)
    description: str = ""
    bonuses: list[PetBonus] = Field(default_factory=list)

    _id = field_validator("id")(check_id)


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
    emoji: str
    color: str = Field(pattern=r"^[0-9a-fA-F]{6}$")  # hex without '#'
    token_price: int = Field(ge=0)
    wage: int = Field(ge=0)
    xp_bonus: float = Field(default=0.0, ge=0, le=1)  # a global bonus to every skill's xp, for as long as you hold the rank


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
    bomb_pressure: float = Field(ge=0)  # a bomb clears a whole row for this flat pressure
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
    water_chance: float = Field(gt=0, le=1)  # watering a plot (once an hour) grows it a cycle with this chance (1: it always does)
    drop_cycles_per_roll: float = Field(gt=0)  # a harvest rolls the farming drop table once per this many of the crop's growth cycles...
    max_drop_rolls: int = Field(ge=1)  # ...but never more than this many times
    starter_seeds: dict[str, int]  # a free gift of seeds the first time you farm
    anomaly_odds: int = Field(ge=1)  # 1 in N per harvest
    xp_per_cycle: int = Field(ge=0)  # xp for a harvest = the seed's growth cycles x this: a long crop pays for the waiting
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
    expired_factor: float = Field(ge=0, le=1)
    refresh_seconds: float = Field(gt=0)


class Grain(_Data):
    """A kind of wood at the place you chop. It sets how hard the spot is to cut and how fast it wears out, and it wants one chop style."""

    id: str
    name: str
    multiplier: float = Field(gt=0)  # what it does to your damage (and xp): a clean grain is better than a knotty one
    weight: float = Field(gt=0)  # how often a new spot has this grain
    stance: Literal["o", "s", "u"]  # the one style it likes: o = overhead, s = sidecut, u = undercut
    wear: float = Field(gt=0)  # how fast a chop wears the spot out, relative to 1 (good grains last, bad ones go quickly)


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
    mark_cap: float = Field(ge=0)  # the most extra reward (+0.5 = +50%) marks can put on one tree
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
    """Re-leaf: give a tree's drops to the foundation instead of keeping them, fill a meter, and your next tree is a double tree."""

    min_level: int = Field(ge=1)
    daily_limit: int = Field(ge=1)
    meter_per_rarity: int = Field(ge=1)
    meter_goal: int = Field(ge=1)
    double_hp: float = Field(ge=1)
    double_xp: int = Field(ge=0)
    double_spirit_chance: float = Field(ge=0, le=1)
    double_items: dict[str, int] = Field(default_factory=dict)  # a double tree also drops this haul of materials (like the mining vault)
    spirit_item: str
    growth_donations: int = Field(ge=1)


class PartyTreeRules(_Data):
    """A tree a party chops together: a little better rewards than the community tree for working as a team."""

    open_minutes: int = Field(ge=1, le=120)
    hp_per_member: float = Field(gt=0)  # tree hp = a typical tree of its zone x this x the party's size
    min_share: float = Field(ge=0, le=1)
    group_bonus: float = Field(ge=0)  # +this per extra member who did their share...
    max_group_bonus: float = Field(ge=0)  # ...up to this
    expired_factor: float = Field(ge=0, le=1)
    refresh_seconds: float = Field(gt=0)


class ForagingRules(_Data):
    zones: int = Field(ge=1)
    zone_levels: list[int] = Field(min_length=1)  # the foraging level each zone needs (zone 1 first; must climb)
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

    @model_validator(mode="after")
    def _zones_fit(self):
        if len(self.zone_levels) != self.zones or self.zone_levels[0] != 1:
            raise ValueError("zone_levels needs one level per zone, starting at level 1")
        if any(b <= a for a, b in zip(self.zone_levels, self.zone_levels[1:], strict=False)):
            raise ValueError("zone_levels must climb")
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
    max_random_mysteries: int = Field(ge=1)  # a coin-flip ❓ can't be learned, so a fish has at most this many of them
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


class BossEntry(_Data):
    """One boss and the twist that makes its reel different."""

    name: str
    modifiers: list[Literal["mirror", "reverse", "shuffle", "fog", "wild"]] = Field(min_length=1)


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
    """A place to fish: unlocked by fishing level, with its own fish (each `fish = N` means 1 in N, rarest rolled first)."""

    id: str
    name: str
    emoji: str = "🌊"
    description: str = ""
    min_level: int = Field(ge=1)
    wait_multiplier: float = Field(gt=0)  # deeper water takes longer to bite
    xp: int = Field(ge=0)  # xp for every fish landed here: deeper waters pay more, a better rod never does
    fish: dict[str, int] = Field(min_length=1)


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
    xp_scale: int = Field(ge=1)  # a pet's level = 1 + sqrt(xp / this), up to max_level
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
    orb_weights: dict[int, float]  # chance weight of each rarity when you open a Familiar Orb


class EconomyRules(_Data):
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


class ShipmentRules(_Data):
    personal: PersonalShipments
    community: CommunityShipments
