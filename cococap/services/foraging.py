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

import random
import time
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from cococap.db import get_database
from cococap.db.tables import CommunityTreeRow, TreeChopRow, TreeRewardRow
from cococap.errors import GameRuleError
from cococap.models.skills.foraging import Foraging
from cococap.registry import Registry, get_registry
from cococap.registry.models import ForagingRules
from cococap.services.equipment import EffectiveStats, equipped_stats
from cococap.services.loot import roll_drop
from cococap.services.party import xp_multiplier
from cococap.user import User

HOUR = 3600


class ForagingError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


# ---- zones --------------------------------------------------------------------------------------------
def zone_level(zone: int, rules: ForagingRules) -> int:
    """The foraging level a zone needs."""
    return 1 + (zone - 1) * rules.levels_per_zone


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


@dataclass(frozen=True)
class Swing:
    damage: int
    good: bool  # a "good chop": extra damage
    freshness: float  # how fresh the spot was for this swing (1.0 = untouched)


@dataclass
class Spot:
    """The place on the trunk you are chopping. Spots differ (``quality``: knotty, plain, clean grain), and each chop
    has a chance to wear the spot down a step. Rotating (a click that does no damage) moves you to a random new spot,
    so it is worth it when your spot has worn below what an average new one would give."""

    name: str = "Plain"
    quality: float = 1.0
    wear: int = 0  # how many steps this spot has worn down

    @classmethod
    def pick(cls, rules: ForagingRules, rng: random.Random) -> "Spot":
        kind = rng.choices(rules.chopping.spots, weights=[k.weight for k in rules.chopping.spots])[0]
        return cls(kind.name, kind.multiplier)

    def freshness(self, rules: ForagingRules) -> float:
        c = rules.chopping
        return max(c.spot_floor, 1 - c.wear_step * self.wear)

    def multiplier(self, rules: ForagingRules) -> float:
        """What this spot does to your axe's power right now."""
        return self.quality * self.freshness(rules)

    def condition(self, rules: ForagingRules) -> str:
        fresh = self.freshness(rules)
        return "fresh" if fresh >= 0.85 else "worn" if fresh >= 0.6 else "dull"

    def preview(self, power: int, rules: ForagingRules) -> int:
        """What the next ordinary (not good) chop would do."""
        return max(1, round(power * self.multiplier(rules)))

    def swing(self, power: int, rules: ForagingRules, rng: random.Random) -> Swing:
        c = rules.chopping
        fresh = self.freshness(rules)
        good = rng.random() < c.good_chop_chance
        damage = max(1, round(power * self.multiplier(rules) * (1 + c.good_chop_bonus if good else 1)))
        if rng.random() < c.wear_chance:
            self.wear += 1
        return Swing(damage, good, fresh)

    def rotate(self, rules: ForagingRules, rng: random.Random) -> None:
        """Move to a new spot: a random kind, and unworn."""
        new = Spot.pick(rules, rng)
        self.name, self.quality, self.wear = new.name, new.quality, 0


def average_spot_multiplier(rules: ForagingRules) -> float:
    spots = rules.chopping.spots
    return sum(k.multiplier * k.weight for k in spots) / sum(k.weight for k in spots)


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

    @property
    def felled(self) -> bool:
        return self.hp <= 0

    def chop(self, power: int) -> int:
        """Take `power` hp off. Returns what was actually removed."""
        if self.felled:
            raise ForagingError("This tree is already down.")
        applied = min(power, self.hp)
        self.hp -= applied
        return applied


def roll_tree(zone: int, rng: random.Random, rules: ForagingRules) -> Tree:
    height = rng.choices(rules.heights, weights=[h.weight for h in rules.heights])[0]
    hp = max(1, round(rng.randint(height.min, height.max) * (1 + rules.zone_hp_growth * (zone - 1))))
    return Tree(zone, hp, hp)


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


def roll_drops(rolls: int, rng: random.Random, registry: Registry) -> Counter[str]:
    pool, found = drop_pool(registry), Counter()
    for _ in range(rolls):
        for item in pool:
            if quantity := roll_drop(item, rng):
                found[item.id] += quantity
    return found


@dataclass(frozen=True)
class Reward:
    drops: Counter
    bits: int
    xp: int
    felled: bool = True  # False: the tree fell over unfinished (a consolation prize)
    window: int | None = None  # the community tree it came from


async def _pay(user: User, drops: Counter, bits: int, xp: int, trees: int) -> None:
    for item_id, quantity in drops.items():
        await user.add_item(item_id, quantity)
    if bits:
        await user.add_bits(bits)

    def grant(m: Foraging) -> None:
        m.xp += xp
        m.stats.trees_chopped += trees

    await user.update_skill("foraging", grant)


async def axe_stats(user: User, registry: Registry | None = None) -> EffectiveStats:
    stats = await equipped_stats(user, "foraging", registry)
    if stats is None:
        raise ForagingError("You need an axe. Buy a Starter Axe in the shop (it's equipped for you).")
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
    drops = roll_drops(whole_rolls(expected_rolls(tree.max_hp, rules, tree.zone), rng), rng, reg)
    bits = round(tree.max_hp * rules.bits_per_hp * zone_reward_factor(tree.zone, rules))
    xp = round(tree.max_hp * rules.xp_per_hp * await xp_multiplier(user.id, reg))
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


def community_spec(window: int, rules: ForagingRules) -> tuple[int, int]:
    """(zone, hp) of the hour's tree: the same for everybody, from the clock alone."""
    rng = random.Random(f"community-tree:{window}")
    zone = rng.randint(rules.community.min_zone, rules.community.max_zone)
    hp = round(average_hp(zone, rules) * rules.community.hp_multiplier * rng.uniform(0.85, 1.15))
    return zone, max(1, hp)


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
        zone, hp = community_spec(window, rules)
        await session.execute(
            sqlite_insert(CommunityTreeRow)
            .values(window=window, zone=zone, max_hp=hp, hp=hp, status="growing", opens_at=opens, closes_at=closes,
                    settled=False)
            .on_conflict_do_nothing()
        )
    return await session.get(CommunityTreeRow, window)


async def _view(session, row: CommunityTreeRow, user_id: int) -> CommunityView:
    choppers = await session.scalar(select(func.count()).select_from(TreeChopRow).where(TreeChopRow.window == row.window))
    yours = await session.scalar(
        select(TreeChopRow.damage).where(TreeChopRow.window == row.window, TreeChopRow.user_id == user_id)
    )
    return CommunityView(row.window, row.zone, row.max_hp, row.hp, row.status, row.opens_at, row.closes_at,
                         choppers or 0, yours or 0)


async def community_tree(user: User, now: float | None = None, registry: Registry | None = None) -> CommunityView | None:
    """This hour's community tree as `user` sees it (created if it is time and nobody has looked yet)."""
    rules = (registry or get_registry()).foraging
    now = time.time() if now is None else now
    async with get_database().session() as session:
        row = await _ensure(session, now, rules)
        return await _view(session, row, user.id) if row else None


@dataclass(frozen=True)
class CommunityChop:
    applied: int
    tree: CommunityView
    felled_now: bool  # this chop brought it down


async def chop_community(
    user: User, power: int, now: float | None = None, registry: Registry | None = None
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
        await session.execute(
            sqlite_insert(TreeChopRow)
            .values(window=row.window, user_id=user.id, damage=applied)
            .on_conflict_do_update(
                index_elements=[TreeChopRow.window, TreeChopRow.user_id],
                set_={"damage": TreeChopRow.damage + applied},
            )
        )
        view = await _view(session, row, user.id)
    return CommunityChop(applied, view, felled_now=view.status == "felled")


# ---- the community tree: rewards ---------------------------------------------------------------------------------
@dataclass(frozen=True)
class Share:
    damage: int
    drops: dict
    bits: int
    xp: int


def community_shares(
    max_hp: int, felled: bool, chops: dict[int, int], rules: ForagingRules, rng: random.Random, registry: Registry,
    zone: int = 1,
) -> dict[int, Share]:
    """Who gets what from a finished community tree. Pure. Drops and bits go by share of the tree's hp (only for
    those with at least ``min_share``); xp is for work done, whatever the share."""
    c = rules.community
    qualifying = [u for u, d in chops.items() if d / max_hp >= c.min_share]
    bonus = min(c.max_group_bonus, c.group_bonus * max(0, len(qualifying) - 1)) if felled else 0.0
    factor = 1.0 if felled else c.expired_factor
    total_rolls = expected_rolls(max_hp, rules, zone)
    pay = zone_reward_factor(zone, rules)
    shares = {}
    for user_id, damage in sorted(chops.items()):
        drops, bits = {}, 0
        if user_id in qualifying:
            rolls = whole_rolls(total_rolls * (damage / max_hp) * (1 + bonus) * factor, rng)
            drops = dict(roll_drops(rolls, rng, registry))
            bits = round(damage * rules.bits_per_hp * pay * (1 + bonus) * factor)
        shares[user_id] = Share(damage, drops, bits, round(damage * rules.xp_per_hp))
    return shares


async def settle_due(now: float | None = None, rng: random.Random | None = None, registry: Registry | None = None) -> int:
    """Work out the rewards of every community tree that is felled or fallen over and not yet settled. One
    transaction per call, and the `settled` flag is set in it, so a tree is never settled twice. Returns how many."""
    reg = registry or get_registry()
    rules, rng = reg.foraging, rng or random.Random()
    now = time.time() if now is None else now
    done = 0
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
                select(TreeChopRow.user_id, TreeChopRow.damage).where(TreeChopRow.window == tree.window)
            )).all()
            shares = community_shares(tree.max_hp, tree.status == "felled", {u: d for u, d in rows if d > 0}, rules, rng, reg, tree.zone)
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
    mult = await xp_multiplier(user.id, reg)
    rewards = []
    for window, drops, bits, xp, felled in snapshot:
        boosted = round(xp * mult)
        await _pay(user, drops, bits, boosted, trees=1 if felled else 0)
        rewards.append(Reward(drops, bits, boosted, felled, window))
    return rewards
