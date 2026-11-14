"""Re-leaf: give a tree's drops to the foundation instead of keeping them.

When you finish a tree (from foraging level 10) you may donate everything it dropped. The **rarest** item you give fills your
Re-leaf meter (its rarity x 5: an Aged Feather, rarity 5, is worth 25). You can donate three times a day. When the meter is
full your **next tree is a double tree**: twice the hp, and a jackpot of bits or (1 in 100) a Spirit of the Forest when it falls.
"""

import random
import time
from collections import Counter
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.models.skills.foraging import Foraging
from cococap.registry import Registry, get_registry
from cococap.services import foraging
from cococap.user import User

DAY = 86_400


class ReleafError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class Status:
    unlocked: bool
    meter: int
    goal: int
    left_today: int  # donations you may still make today
    double_ready: bool
    donations: int  # lifetime


def _today(now: float) -> int:
    return int(now // DAY)


async def status(user: User, now: float | None = None, registry: Registry | None = None) -> Status:
    reg = registry or get_registry()
    now = time.time() if now is None else now
    skill = await user.skill("foraging")
    r = reg.foraging.releaf
    used = skill.donations_made_today if skill.donation_day == _today(now) else 0
    return Status(User.xp_to_level(skill.xp) >= r.min_level, skill.releaf_meter, r.meter_goal, max(0, r.daily_limit - used),
                  skill.double_ready, skill.stats.releaf_donations)


def meter_gain(drops: Counter, registry: Registry) -> int:
    """How far these drops fill the meter: the rarest item's rarity x the rate."""
    rarest = max((registry.item(i).rarity for i, q in drops.items() if q > 0), default=0)
    return rarest * registry.foraging.releaf.meter_per_rarity


@dataclass(frozen=True)
class Donation:
    gained: int
    meter: int
    goal: int
    left_today: int
    double_ready: bool
    became_ready: bool  # this donation filled the meter


async def donate(user: User, drops: Counter, now: float | None = None, registry: Registry | None = None) -> Donation:
    """Give these items to Re-leaf. They must still be in your inventory; one donation a go, three a day."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    r = reg.foraging.releaf
    drops = Counter({i: q for i, q in drops.items() if q > 0})
    if not drops:
        raise ReleafError("There is nothing to donate.")
    current = await status(user, now, reg)
    if not current.unlocked:
        raise ReleafError(f"Re-leaf opens at foraging level {r.min_level}.")
    if current.left_today <= 0:
        raise ReleafError(f"You have already made your {r.daily_limit} Re-leaf donations today. The trees thank you!")
    gained = meter_gain(drops, reg)
    taken: Counter = Counter()
    try:
        for item_id, quantity in drops.items():
            await user.remove_item(item_id, quantity)
            taken[item_id] = quantity
    except ValueError:
        for item_id, quantity in taken.items():
            await user.add_item(item_id, quantity)
        raise ReleafError("You no longer have all of those drops.") from None
    outcome: dict = {}

    def give(skill: Foraging) -> None:
        today = _today(now)
        if skill.donation_day != today:
            skill.donation_day, skill.donations_made_today = today, 0
        if skill.donations_made_today >= r.daily_limit:  # (a second click got in first)
            outcome["full"] = True
            return
        skill.donations_made_today += 1
        skill.stats.releaf_donations += 1
        skill.releaf_meter += gained
        if skill.releaf_meter >= r.meter_goal and not skill.double_ready:
            skill.releaf_meter -= r.meter_goal
            skill.double_ready = True
            outcome["ready"] = True
        outcome.update(meter=skill.releaf_meter, left=r.daily_limit - skill.donations_made_today, double=skill.double_ready)

    await user.update_skill("foraging", give)
    if outcome.get("full"):
        for item_id, quantity in taken.items():
            await user.add_item(item_id, quantity)  # no donation went through: your drops come back
        raise ReleafError(f"You have already made your {r.daily_limit} Re-leaf donations today. The trees thank you!")
    return Donation(gained, outcome["meter"], r.meter_goal, outcome["left"], outcome["double"], bool(outcome.get("ready")))


async def new_tree(user: User, zone: int, rng: random.Random, registry: Registry | None = None) -> foraging.Tree:
    """A new private tree for you: a double tree if your Re-leaf meter has filled."""
    reg = registry or get_registry()
    tree = foraging.roll_tree(zone, rng, reg.foraging)
    if (await user.skill("foraging")).double_ready:
        tree.double = True
        tree.max_hp = tree.hp = max(1, round(tree.max_hp * reg.foraging.releaf.double_hp))
    return tree
