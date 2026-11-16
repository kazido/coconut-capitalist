"""Foraging rules: private trees, the hourly community tree, and what a felled tree pays.

* A **private tree** is a plain object held by the screen (like a mining run): chop it down on your own, any time.
  From the heavy zone up a lone chopper swings at reduced power, unless their axe has the Soloist enchant.
* The **community tree** is shared. One grows each hour and stands for ``open_minutes``. It lives in the database as
  hit points plus each player's contribution. Every chop is one atomic update ("take this much hp off the tree and
  add it to this player's total"), so any number of people can chop at once without losing or double-counting
  anything. Which tree exists is a function of the clock, so no background job is needed: whoever looks first in an
  hour creates that hour's row.
* When a community tree is felled or falls over, its rewards are **worked out once** (inside one transaction, so
  never twice) and stored per player. Each player claims theirs from their own panel, even if they were offline.

All randomness comes from an injected ``random.Random``.
"""

import math
import random
import time
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cococap.db import get_database
from cococap.db.tables import CommunityTreeRow, SkillRow, TreeChopRow, TreeRewardRow
from cococap.errors import GameRuleError
from cococap.models.skills.foraging import Foraging
from cococap.registry import Registry, get_registry
from cococap.registry.models import ForagingRules, Grain, Species, Wedge
from cococap.services import releaf, scrolls
from cococap.services.equipment import EffectiveStats, equipped_stats
from cococap.services import pets
from cococap.services.loot import roll_drop, skewed_roll
from cococap.services.party import xp_multiplier
from cococap.user import User

HOUR = 3600


class ForagingError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


# ---- zones --------------------------------------------------------------------------------------------
def zone_level(zone: int, rules: ForagingRules) -> int:
    """The foraging level a zone needs."""
    return rules.zone_levels[min(max(zone, 1), rules.zones) - 1]


def unlocked_zones(level: int, rules: ForagingRules) -> list[int]:
    return [z for z in range(1, rules.zones + 1) if level >= zone_level(z, rules)]


def is_heavy(zone: int, rules: ForagingRules) -> bool:
    return zone >= rules.heavy_zone


def swing_power(stats: EffectiveStats, zone: int, rules: ForagingRules, *, community: bool = False) -> int:
    """How much hp one chop takes off. A lone chopper on a heavy private tree swings at reduced power unless
    their axe has the Soloist enchant; community trees are chopped at full power."""
    power = stats.power
    if not community and is_heavy(zone, rules) and not stats.has("soloist"):
        power = round(power * rules.heavy_solo_power)
    return max(1, power)


STANCES = {"o": ("Overhead", "⬆️"), "s": ("Sidecut", "↔️"), "u": ("Undercut", "⬇️")}
MIN_WEAR_FACTOR = 0.25  # no enchant can make a spot last more than four times as long


@dataclass(frozen=True)
class Swing:
    damage: int
    good: bool  # a "good chop": extra damage
    correct: bool | None = None  # was it the grain's style? (None: no stance was used)
    ended: bool = False  # the spot wore out on this chop: you are on a new one now
    doubled: bool = False  # a double chop (the enchant): it hit twice
    special: str = ""  # the special spot's effect that fired on this chop ("damage", "xp" or "mark"), if any
    mark: float = 0.0  # reward this chop added to the tree (a Rich Seam)
    clean_grain: bool = False  # this chop finished a grain with every chop on it in the right style (Windfall pays on these)
    effort: float = 1.0  # how good the chop was, whatever axe made it (grain x wear x style x a good chop's bonus): this is what pays xp


@dataclass
class Spot:
    """The place on the trunk you are chopping. Its **grain** (plain, knotty, clean...) sets how hard it is, how fast it wears and the one
    chop style it likes. Now and then a spot is a **special** one (Heartwood, Golden Knot, Rich Seam): chopped in the right style it does
    something big, and it wears out fast. Chopping wears the spot (the good grains slowest) and a worn spot chops weaker; when it is
    fully worn you are moved to a new spot by yourself, or you can spend a rotation wedge to leave early."""

    name: str = "Plain"
    quality: float = 1.0
    grain: str = "plain"
    wear: float = 0.0  # 0 fresh .. 1 worn out
    special: str = ""  # a special spot's id, or ""
    private: bool = True  # a tree of your own (marks only work there)
    boost: float = 0.0  # a wedge's lasting bonus: every chop hits (and pays xp) this much harder...
    boost_chops: int = 0  # ...for this many more chops (it follows you when a worn spot moves you on)
    streak: int = 0  # grains in a row you finished with every chop in the right style (a small, capped damage bonus; one slip or a new tree resets it)
    clean: bool = True  # no wrong-style chop on THIS grain yet
    streak_tree: object = None  # which tree the streak belongs to (a different one starts it over)

    @classmethod
    def pick(cls, rules: ForagingRules, rng: random.Random, bias: float = 0.0, exclude: str | None = None,
             special_mult: float = 1.0, private: bool = True) -> "Spot":
        """A new spot. `bias` tilts the roll toward good grains and `special_mult` makes a special spot likelier (a wedge); `exclude` is the
        grain you are leaving; `private` is False on a shared tree (no marks there)."""
        c = rules.chopping
        grains = [g for g in c.grains if g.id != exclude] or c.grains
        g = rng.choices(grains, weights=[g.weight * g.multiplier**bias for g in grains])[0]
        special = ""
        if rng.random() < min(1.0, c.special_chance * special_mult):
            kinds = [sp for sp in c.specials if private or not sp.private_only]
            special = rng.choices(kinds, weights=[sp.weight for sp in kinds])[0].id
        return cls(g.name, g.multiplier, g.id, 0.0, special, private)

    def on_tree(self, tree_key: object) -> None:
        """Tell the spot which tree you are chopping: starting a different one starts the streak over."""
        if self.streak_tree != tree_key:
            self.streak, self.streak_tree = 0, tree_key

    def stance(self, rules: ForagingRules) -> str:
        return rules.chopping.grain(self.grain).stance

    def kind(self, rules: ForagingRules):
        """The special this spot is, if it is one."""
        return rules.chopping.special(self.special) if self.special else None

    def title(self, rules: ForagingRules) -> str:
        sp = self.kind(rules)
        return f"{sp.emoji} {sp.name}: {self.name}" if sp else self.name

    def strength(self, rules: ForagingRules) -> float:
        """What this spot does to your axe's power right now: the grain's quality, less what the wear has taken."""
        return self.quality * (1 - rules.chopping.wear_penalty * min(1.0, self.wear))

    def preview(self, power: int, rules: ForagingRules) -> int:
        """What a chop in the right style would do right now (a Heartwood's big hit included)."""
        sp = self.kind(rules)
        return max(1, round(power * self.strength(rules) * (sp.amount if sp and sp.effect == "damage" else 1)))

    def swing(self, power: int, rules: ForagingRules, rng: random.Random, good_bonus: float = 0.0,
              stance: str | None = None, wear_slow: float = 0.0, double_chance: float = 0.0, clean_cut: float = 0.0) -> Swing:
        """One chop. In the grain's style it hits fully, in another style it glances off (`wrong_stance_factor`). It also wears the spot,
        and when that is used up you are on a new one. ``good_bonus`` is extra good-chop chance (Sharp Eye), ``wear_slow`` how much slower a plain or good grain wears (Seasoned) and how much FASTER a bad grain does, and ``double_chance`` the chance of a double chop (Double Strike). On a special spot a RIGHT chop also fires its
        effect: bigger damage, more xp, or a mark on the tree."""
        c = rules.chopping
        good = rng.random() < c.good_chop_chance + good_bonus
        doubled = rng.random() < double_chance
        correct = None if stance is None else stance == self.stance(rules)
        quality = self.strength(rules) * (c.wrong_stance_factor if correct is False else 1.0) * (1 + c.good_chop_bonus if good else 1)
        if self.boost_chops > 0:  # a wedge's bonus: harder hits, and the xp goes up with them
            quality *= 1 + self.boost
            self.boost_chops -= 1
        hits, effort, fired, mark = 2.0 if doubled else 1.0, quality, "", 0.0  # (the effort is what pays xp: a double chop is still one swing)
        if correct is False:  # a wrong-style chop breaks the streak at once, on this very swing (and this grain is no longer clean)
            self.clean, self.streak = False, 0
        hits *= 1 + c.streak_bonus * min(self.streak, c.streak_max)  # (the streak adds damage only, never xp)
        sp = self.kind(rules)
        if sp and correct is not False:  # (a chop with no style at all counts as right)
            fired = sp.effect
            if sp.effect == "damage":
                hits *= sp.amount
            elif sp.effect == "xp":
                effort *= sp.amount
            elif self.private:
                mark = sp.amount
        if correct and clean_cut:  # Clean Cut (Mastery): a chop in the grain's own style hits harder
            quality *= 1 + clean_cut
        damage = max(1, round(power * quality * hits))
        self.wear += self.wear_per_chop(rules, wear_slow)
        ended = self.wear >= 1
        clean_grain = ended and self.clean
        if ended:  # the grain is finished: done right all the way through, the streak grows; one wrong chop and it starts over
            self.streak = min(c.streak_max, self.streak + 1) if self.clean else 0
            self.rotate(rules, rng)
        return Swing(damage, good, correct, ended, doubled, fired, mark, clean_grain, effort)

    def wear_per_chop(self, rules: ForagingRules, wear_slow: float = 0.0) -> float:
        """How much one chop wears this spot. Seasoning keeps a spot lasting, but it is a trade: it slows a plain or good grain and speeds a BAD one (wear above
        normal) up by the same amount, so a tool that wears slowly makes the good grains better and the bad ones worth leaving sooner."""
        c = rules.chopping
        grain_wear = c.grain(self.grain).wear
        seasoning = 1 + wear_slow if grain_wear > 1 else max(MIN_WEAR_FACTOR, 1 - wear_slow)
        sp = self.kind(rules)
        return c.wear_per_chop * grain_wear * (sp.wear if sp else 1.0) * seasoning

    def chops_left(self, rules: ForagingRules, wear_slow: float = 0.0) -> int:
        """About how many more chops this spot lasts (so you can tell when you will be moved on)."""
        return max(1, math.ceil(max(0.0, 1 - self.wear) / self.wear_per_chop(rules, wear_slow) - 1e-9))

    def rotate(self, rules: ForagingRules, rng: random.Random, bias: float = 0.0, special_mult: float = 1.0) -> None:
        """Move to a new spot: a different grain (tilted by `bias`), unworn. Happens by itself when a spot wears out, or with a wedge."""
        new = Spot.pick(rules, rng, bias, exclude=self.grain, special_mult=special_mult, private=self.private)
        self.name, self.quality, self.grain, self.wear, self.special, self.clean = new.name, new.quality, new.grain, 0.0, new.special, True


def average_spot_multiplier(rules: ForagingRules) -> float:
    grains = rules.chopping.grains
    return sum(g.multiplier * g.weight for g in grains) / sum(g.weight for g in grains)


# ---- rotation wedges ------------------------------------------------------------------------------------------------
async def wedges(user: User, registry: Registry | None = None) -> list[tuple[Wedge, int]]:
    """The wedges you hold, worst first: (wedge, how many)."""
    reg = registry or get_registry()
    held = [(w, await user.item_quantity(w.item)) for w in reg.foraging.rotate.wedges]
    return [(w, q) for w, q in held if q > 0]


async def spend_wedge(user: User, spot: Spot, item_id: str, rng: random.Random, registry: Registry | None = None) -> None:
    """Use one wedge: you leave this spot for a new grain (leaning good for the better wedges)."""
    reg = registry or get_registry()
    wedge = next((w for w in reg.foraging.rotate.wedges if w.item == item_id), None)
    if wedge is None:
        raise ForagingError("That is not a rotation wedge.")
    try:
        await user.remove_item(item_id, 1)
    except ValueError:
        raise ForagingError(f"You have no {reg.item(item_id).name}.") from None
    spot.rotate(reg.foraging, rng, wedge.bias, wedge.special_mult)
    if wedge.boost_chops:  # a better wedge also leaves a lasting bonus (a new one replaces the old, it does not stack)
        spot.boost, spot.boost_chops = wedge.boost, wedge.boost_chops


# ---- grain notes: which style each grain likes, as you have found out -----------------------------------------------
@dataclass(frozen=True)
class GrainNote:
    grain: Grain
    known: str | None  # the style letter once you have seen it work
    ruled_out: str  # style letters you have seen fail


async def grain_notes(user: User, registry: Registry | None = None) -> list[GrainNote]:
    """Your notes: each grain with the style you know for it, or the ones you have crossed off."""
    reg = registry or get_registry()
    saved = (await user.skill("foraging")).styles
    notes = []
    for g in reg.foraging.chopping.grains:
        entry = saved.get(g.id, "")
        known = next((c.lower() for c in entry if c.isupper()), None)
        notes.append(GrainNote(g, known, "" if known else "".join(c for c in entry if c.islower())))
    return notes


async def note_style(user: User, grain: str, stance: str, correct: bool) -> bool:
    """Write down what happened: the right style is remembered for good, a wrong one is crossed off. True if that told you something new."""
    outcome: dict = {}

    def write(skill: Foraging) -> None:
        entry = skill.styles.get(grain, "")
        if correct and stance.upper() not in entry:
            skill.styles[grain] = stance.upper()  # known: the crossed-off guesses no longer matter
            outcome["new"] = True
        elif not correct and not any(c.isupper() for c in entry) and stance not in entry:
            skill.styles[grain] = entry + stance
            outcome["new"] = True

    await user.update_skill("foraging", write)
    return bool(outcome)


def average_hp(zone: int, rules: ForagingRules) -> float:
    """What a typical tree of this zone is worth in hp."""
    total = sum(h.weight for h in rules.heights)
    height = sum(h.weight * (h.min + h.max) / 2 for h in rules.heights) / total
    return height * (1 + rules.zone_hp_growth * (zone - 1))


# ---- private trees --------------------------------------------------------------------------------------
@dataclass
class Tree:
    zone: int
    max_hp: int
    hp: int
    collected: bool = False  # its reward has been paid
    effort: float = 0.0  # the quality of every chop made on it so far: its xp
    bonus: float = 0.0  # marked by Rich Seams: +this to its bits and drops when it falls (0.25 = +25%)
    species: str = ""  # the species id (set by the zone when it is rolled; "" = none, no signature drops)

    @property
    def felled(self) -> bool:
        return self.hp <= 0

    def chop(self, power: int, effort: float = 1.0) -> int:
        """Take `power` hp off (a last chop only counts for the part that was needed). Returns what was actually removed."""
        if self.felled:
            raise ForagingError("This tree is already down.")
        applied = min(power, self.hp)
        self.hp -= applied
        self.effort += effort * applied / max(1, power)
        return applied


def roll_species(zone: int, rng: random.Random, rules: ForagingRules) -> Species | None:
    """The species of a tree in `zone`: one of the species that grow there, by weight (None when the rules have no species)."""
    kinds = rules.species_in(zone)
    return rng.choices(kinds, weights=[sp.weight for sp in kinds])[0] if kinds else None


def community_species(window: int, zone: int, rules: ForagingRules) -> str:
    """The species of an hour's community tree: a pure function of the hour and its zone (seeded like the zone is), so everybody, and the
    settling of its rewards, sees the same one."""
    sp = roll_species(zone, random.Random(f"community-tree:{window}:species:{zone}"), rules)
    return sp.id if sp else ""


def roll_tree(zone: int, rng: random.Random, rules: ForagingRules, species: str | None = None) -> Tree:
    """A new tree: its height and hp, then its species (rolled by the zone's weights after the hp, unless one is given)."""
    height = rng.choices(rules.heights, weights=[h.weight for h in rules.heights])[0]
    hp = max(1, round(rng.randint(height.min, height.max) * (1 + rules.zone_hp_growth * (zone - 1))))
    if species is None:
        sp = roll_species(zone, rng, rules)
        species = sp.id if sp else ""
    return Tree(zone, hp, hp, species=species)


# ---- what trees pay ---------------------------------------------------------------------------------------
def drop_pool(registry: Registry):
    return [i for i in registry.items_for_skill("foraging") if i.drop]


def zone_reward_factor(zone: int, rules: ForagingRules) -> float:
    """Deeper zones pay more per hp."""
    return 1 + rules.zone_reward_growth * (zone - 1)


def expected_rolls(hp: float, rules: ForagingRules, zone: int = 1) -> float:
    """How many drop-table rolls `hp` of tree is worth, as a fraction (so small trees aren't over-paid)."""
    return hp / rules.hp_per_roll * zone_reward_factor(zone, rules)


def whole_rolls(expected: float, rng: random.Random) -> int:
    """Turn a fractional number of rolls into a whole one by chance: 2.3 is 2 rolls, plus a 30% chance of a third."""
    whole = int(expected)
    return whole + (1 if rng.random() < expected - whole else 0)


def _roll_boosted(item, rng: random.Random, boost: float) -> int | None:
    """`roll_drop` with every chance multiplied by (1 + boost) (the Releaf Bloom). With no boost it is exactly `roll_drop`."""
    if not boost:
        return roll_drop(item, rng)
    if item.drop is None or rng.random() >= min(1.0, (1 + boost) / item.drop.rate):
        return None
    return skewed_roll(rng, item.drop.min, item.drop.max)


def roll_drops(rolls: int, rng: random.Random, registry: Registry, rare_reroll: float = 0.0, species: str = "", boost: float = 0.0) -> Counter[str]:
    """Roll the forest's drops `rolls` times. `rare_reroll` (a Fox): each rare item (rarity 4+) that misses has this chance of one free second roll.
    `species` (a tree's species id): its signature drops are rolled on every roll too, on top of the normal pool.
    `boost` (a Releaf Bloom): every drop chance, signature ones too, is multiplied by 1 + boost (0.10 = +10%)."""
    pool, found = drop_pool(registry), Counter()
    signature = sp.drops if (sp := registry.foraging.species_of(species)) else []
    for _ in range(rolls):
        for d in signature:
            chance = min(1.0, d.rate * (1 + boost))
            hit = rng.random() < chance
            if not hit and rare_reroll and registry.item(d.item).rarity >= pets.RARE_FROM and rng.random() < rare_reroll:
                hit = rng.random() < chance
            if hit:
                found[d.item] += skewed_roll(rng, d.min, d.max)
        for item in pool:
            quantity = _roll_boosted(item, rng, boost)
            if not quantity and rare_reroll and item.rarity >= pets.RARE_FROM and rng.random() < rare_reroll:
                quantity = _roll_boosted(item, rng, boost)
            if quantity:
                found[item.id] += quantity
    return found


@dataclass(frozen=True)
class Reward:
    drops: Counter
    bits: int
    xp: int
    felled: bool = True  # False: the tree fell over unfinished (a consolation prize)
    window: int | None = None  # the community tree it came from
    party: bool = False  # ...or it came from a party tree


async def _pay(user: User, drops: Counter, bits: int, xp: int, trees: int) -> None:
    for item_id, quantity in drops.items():
        await user.add_item(item_id, quantity)
    if bits:
        await user.add_bits(bits)

    def grant(m: Foraging) -> None:
        m.xp += xp
        m.stats.trees_chopped += trees

    await user.update_skill("foraging", grant)


async def shake(user: User, chance: float, rng: random.Random, registry: Registry | None = None) -> Counter:
    """A Forager's axe (`shake`): a chop has this chance to shake loose exactly ONE extra item (one of the forest's drops, the commoner ones likelier),
    paid at once. Returns what fell."""
    if chance <= 0 or rng.random() >= chance:
        return Counter()
    pool = drop_pool(registry or get_registry())
    item = rng.choices(pool, weights=[1 / i.drop.rate for i in pool])[0]
    await user.add_item(item.id, 1)
    return Counter({item.id: 1})


async def windfall(user: User, every: int, rng: random.Random, registry: Registry | None = None, *, grain_done: bool = False, species: str = "") -> Counter:
    """Windfall (Mastery): every `every`th grain you finish clean (every chop on it in the grain's own style; `Swing.clean_grain`, passed as
    `grain_done`) shakes loose a full roll of drops, paid at once. Counts clean grains, not chops. Returns what fell."""
    if every <= 0 or not grain_done:
        return Counter()
    hit: list[bool] = []

    def count(skill: Foraging) -> None:
        skill.stats.grains += 1
        if skill.stats.grains % every == 0:
            hit.append(True)

    await user.update_skill("foraging", count)
    if not hit:
        return Counter()
    reg = registry or get_registry()
    drops = roll_drops(1, rng, reg, (await pets.bonuses(user, reg)).get("rare_reroll", 0.0), species, await releaf.drop_boost(reg))
    for item_id, quantity in drops.items():
        await user.add_item(item_id, quantity)
    return drops


async def axe_stats(user: User, registry: Registry | None = None) -> EffectiveStats:
    stats = await equipped_stats(user, "foraging", registry)
    if stats is None:
        raise ForagingError("You need an axe. Claim your free Starter Axe on the Tools page.")
    return stats


async def fell_private(user: User, tree: Tree, rng: random.Random, registry: Registry | None = None) -> Reward:
    """Pay out a private tree that has been chopped down (once)."""
    reg = registry or get_registry()
    rules = reg.foraging
    if not tree.felled:
        raise ForagingError("This tree is still standing.")
    if tree.collected:
        raise ForagingError("You already collected this tree.")
    tree.collected = True
    axe = await equipped_stats(user, "foraging", reg)
    final_cut = axe.stats.get("final_cut", 0.0) if axe else 0.0  # Final Cut (Mastery): a tree you fell yourself pays more
    fox = (await pets.bonuses(user, reg)).get("rare_reroll", 0.0)
    drops = roll_drops(whole_rolls(expected_rolls(tree.max_hp, rules, tree.zone) * (1 + tree.bonus + final_cut), rng), rng, reg, fox, tree.species,
                       await releaf.drop_boost(reg))
    if scroll := scrolls.roll("foraging", rng, reg):  # (a rare scroll, one chance per tree whatever its size)
        drops[scroll] += 1
    bits = round(tree.max_hp * rules.bits_per_hp * zone_reward_factor(tree.zone, rules) * (1 + tree.bonus + final_cut))
    xp = round(tree.effort * rules.xp_per_swing * await xp_multiplier(user.id, reg, "foraging"))
    await _pay(user, drops, bits, xp, trees=1)
    return Reward(drops, bits, xp)


# ---- the community tree: the clock ---------------------------------------------------------------------------
def window_of(now: float) -> int:
    return int(now // HOUR)


def window_times(window: int, rules: ForagingRules) -> tuple[float, float]:
    opens = window * HOUR
    return opens, opens + rules.community.open_minutes * 60


def next_tree_at(now: float) -> float:
    """When the next community tree grows (the start of the next hour)."""
    return (window_of(now) + 1) * HOUR


def community_spec(window: int, rules: ForagingRules, crowd: list[int] | tuple[int, ...] = ()) -> tuple[int, int]:
    """(zone, hp) of the hour's tree. `crowd` is the foraging levels of the people who chopped lately: the tree is picked
    around what the typical one of them can reach, and is as big as that many choppers can finish. It is worked out once,
    when the hour's tree is made, and stored, so everybody sees the same tree."""
    c = rules.community
    rng = random.Random(f"community-tree:{window}")
    if crowd:
        middle = sorted(crowd)[len(crowd) // 2]
        reach = unlocked_zones(middle, rules)[-1]
    else:
        reach = c.default_zone
    zone = rng.randint(max(1, reach - c.zone_below), min(rules.zones, reach + c.zone_above))
    people = min(max(len(crowd), c.min_active), c.max_active)
    hp = round(average_hp(zone, rules) * c.hp_per_active * people * rng.uniform(0.85, 1.15))
    return zone, max(1, hp)


async def recent_crowd(session, window: int, rules: ForagingRules) -> list[int]:
    """The foraging levels of everyone who chopped a community tree in the last few hours."""
    first = window - rules.community.recent_windows
    rows = await session.execute(
        select(SkillRow.xp)
        .join(TreeChopRow, TreeChopRow.user_id == SkillRow.user_id)
        .where(SkillRow.skill == "foraging", TreeChopRow.window >= first, TreeChopRow.window < window)
        .distinct()
    )
    return [User.xp_to_level(xp) for (xp,) in rows]


@dataclass(frozen=True)
class CommunityView:
    window: int
    zone: int
    max_hp: int
    hp: int
    status: str  # growing | felled | expired
    opens_at: float
    closes_at: float
    choppers: int
    yours: int  # hp you have chopped off it
    species: str = ""  # the tree's species id

    @property
    def standing(self) -> bool:
        return self.status == "growing"

    @property
    def fraction_left(self) -> float:
        return self.hp / self.max_hp if self.max_hp else 0.0

    @property
    def share(self) -> float:
        return self.yours / self.max_hp if self.max_hp else 0.0


async def _ensure(session, now: float, rules: ForagingRules) -> CommunityTreeRow | None:
    """Mark overdue trees as fallen over, and make sure this hour's tree exists while it is open. Returns this
    hour's row (or None before/without one)."""
    await session.execute(
        update(CommunityTreeRow)
        .where(CommunityTreeRow.status == "growing", CommunityTreeRow.closes_at <= now)
        .values(status="expired")
    )
    window = window_of(now)
    opens, closes = window_times(window, rules)
    if now < closes:
        zone, hp = community_spec(window, rules, await recent_crowd(session, window, rules))
        await session.execute(
            sqlite_insert(CommunityTreeRow)
            .values(window=window, zone=zone, max_hp=hp, hp=hp, status="growing", opens_at=opens, closes_at=closes,
                    settled=False)
            .on_conflict_do_nothing()
        )
    return await session.get(CommunityTreeRow, window)


async def _view(session, row: CommunityTreeRow, user_id: int, rules: ForagingRules) -> CommunityView:
    choppers = await session.scalar(select(func.count()).select_from(TreeChopRow).where(TreeChopRow.window == row.window))
    yours = await session.scalar(
        select(TreeChopRow.damage).where(TreeChopRow.window == row.window, TreeChopRow.user_id == user_id)
    )
    return CommunityView(row.window, row.zone, row.max_hp, row.hp, row.status, row.opens_at, row.closes_at,
                         choppers or 0, yours or 0, community_species(row.window, row.zone, rules))


async def community_tree(user: User, now: float | None = None, registry: Registry | None = None) -> CommunityView | None:
    """This hour's community tree as `user` sees it (created if it is time and nobody has looked yet)."""
    rules = (registry or get_registry()).foraging
    now = time.time() if now is None else now
    async with get_database().session() as session:
        row = await _ensure(session, now, rules)
        return await _view(session, row, user.id, rules) if row else None


@dataclass(frozen=True)
class CommunityChop:
    applied: int
    tree: CommunityView
    felled_now: bool  # this chop brought it down


async def chop_community(
    user: User, power: int, now: float | None = None, registry: Registry | None = None, effort: float = 1.0
) -> CommunityChop:
    """One chop on the community tree. Atomic: concurrent chops from any number of players all count."""
    rules = (registry or get_registry()).foraging
    now = time.time() if now is None else now
    async with get_database().session() as session:
        row = await _ensure(session, now, rules)
        if row is None or row.status != "growing" or now >= row.closes_at:
            raise ForagingError("There's no community tree to chop right now.")
        applied = min(max(1, power), row.hp)
        row.hp -= applied
        if row.hp == 0:
            row.status = "felled"
        await session.flush()
        earned = effort * applied / max(1, power)  # (a last chop only counts for the part that was needed)
        await session.execute(
            sqlite_insert(TreeChopRow)
            .values(window=row.window, user_id=user.id, damage=applied, effort=earned)
            .on_conflict_do_update(
                index_elements=[TreeChopRow.window, TreeChopRow.user_id],
                set_={"damage": TreeChopRow.damage + applied, "effort": TreeChopRow.effort + earned},
            )
        )
        view = await _view(session, row, user.id, rules)
    return CommunityChop(applied, view, felled_now=view.status == "felled")


# ---- the community tree: rewards ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class Share:
    damage: int
    drops: dict
    bits: int
    xp: int


def community_pool(choppers: int, rules: ForagingRules) -> float:
    """How much of the tree's worth is paid out to ``choppers`` distinct choppers (those who did their share). One chopper gets `pool_base` of it; each
    further one adds `pool_per_chopper`, but every new one adds `pool_decay` times what the last one did, so the pool climbs toward a ceiling instead of growing
    forever. With the defaults (base 1, no increment) the pool is the whole tree, which is how a party tree pays."""
    c = rules.community
    extra = sum(c.pool_decay**k for k in range(max(0, choppers - 1)))
    return c.pool_base + c.pool_per_chopper * extra


def community_shares(
    max_hp: int, felled: bool, chops: dict[int, int], rules: ForagingRules, rng: random.Random, registry: Registry,
    zone: int = 1, *, efforts: dict[int, float] | None = None, species: str = "", boost: float = 0.0,
) -> dict[int, Share]:
    """Who gets what from a finished community tree. Pure. Drops and bits go by share of the tree's hp, out of a pool that grows with the number of choppers (only for
    those with at least ``min_share``); xp is for work done (the quality of each chop, in `efforts`), whatever the share."""
    c = rules.community
    qualifying = [u for u, d in chops.items() if d / max_hp >= c.min_share]
    bonus = min(c.max_group_bonus, c.group_bonus * max(0, len(qualifying) - 1)) if felled else 0.0
    factor = 1.0 if felled else c.expired_factor
    total_rolls = expected_rolls(max_hp, rules, zone) * community_pool(len(qualifying), rules)  # (the pool grows with the number of choppers, so a crowd is balanced against solo play)
    pay = zone_reward_factor(zone, rules)
    shares = {}
    for user_id, damage in sorted(chops.items()):
        drops, bits = {}, 0
        if user_id in qualifying:
            paid_share = min(damage / max_hp, c.max_share)
            pool = community_pool(len(qualifying), rules)
            rolls = whole_rolls(total_rolls * paid_share * (1 + bonus) * factor, rng)
            drops = dict(roll_drops(rolls, rng, registry, species=species, boost=boost))
            bits = round(paid_share * max_hp * rules.bits_per_hp * pay * pool * (1 + bonus) * factor)
        shares[user_id] = Share(damage, drops, bits, round((efforts or {}).get(user_id, 0.0) * rules.xp_per_swing))
    return shares


async def settle_due(now: float | None = None, rng: random.Random | None = None, registry: Registry | None = None) -> int:
    """Work out the rewards of every community tree that is felled or fallen over and not yet settled. One
    transaction per call, and the `settled` flag is set in it, so a tree is never settled twice. Returns how many."""
    reg = registry or get_registry()
    rules, rng = reg.foraging, rng or random.Random()
    now = time.time() if now is None else now
    done = 0
    blooms = await releaf.windows()  # (read before the transaction: the Bloom's drop bonus for a tree is on if a Bloom was up during its hour)
    async with get_database().session() as session:
        await session.execute(
            update(CommunityTreeRow)
            .where(CommunityTreeRow.status == "growing", CommunityTreeRow.closes_at <= now)
            .values(status="expired")
        )
        trees = (await session.scalars(
            select(CommunityTreeRow).where(CommunityTreeRow.settled.is_(False), CommunityTreeRow.status != "growing")
        )).all()
        for tree in trees:
            rows = (await session.execute(
                select(TreeChopRow.user_id, TreeChopRow.damage, TreeChopRow.effort).where(TreeChopRow.window == tree.window)
            )).all()
            shares = community_shares(tree.max_hp, tree.status == "felled", {u: d for u, d, _ in rows if d > 0}, rules, rng, reg, tree.zone,
                                      efforts={u: e for u, d, e in rows if d > 0},
                                      species=community_species(tree.window, tree.zone, rules), boost=releaf.boost_between(blooms, *window_times(tree.window, rules), rules.releaf))
            for user_id, share in shares.items():
                session.add(TreeRewardRow(window=tree.window, user_id=user_id, damage=share.damage,
                                          felled=tree.status == "felled", drops=share.drops, bits=share.bits,
                                          xp=share.xp, claimed=False))
            tree.settled = True
            done += 1
    return done


async def claim_rewards(
    user: User, now: float | None = None, rng: random.Random | None = None, registry: Registry | None = None
) -> list[Reward]:
    """Collect everything you are owed from finished community trees (settling any that are due first)."""
    reg = registry or get_registry()
    await settle_due(now, rng, reg)
    claimed: list[tuple[int, TreeRewardRow]] = []
    async with get_database().session() as session:
        rows = (await session.scalars(
            select(TreeRewardRow).where(TreeRewardRow.user_id == user.id, TreeRewardRow.claimed.is_(False))
            .order_by(TreeRewardRow.window)
        )).all()
        for row in rows:
            row.claimed = True  # in the same transaction as the read: a second click finds nothing to claim
            claimed.append((row.window, row))
        snapshot = [(w, Counter(r.drops), r.bits, r.xp, r.felled) for w, r in claimed]
    if not snapshot:
        return []
    mult = await xp_multiplier(user.id, reg, "foraging")
    rewards = []
    for window, drops, bits, xp, felled in snapshot:
        boosted = round(xp * mult)
        await _pay(user, drops, bits, boosted, trees=1 if felled else 0)
        rewards.append(Reward(drops, bits, boosted, felled, window))
    return rewards
