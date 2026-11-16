"""Everyday income: the work / daily / weekly check-in rewards.

Each claim starts its cooldown *atomically* (``User.claim_cooldown``) before paying out, so a stale
button or two simultaneous requests can never pay twice.
"""

import math
import time
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.user import Cooldowns, User

DAILY_TOKENS = 1


class OnCooldown(GameRuleError):
    def __init__(self, seconds_left: float):
        super().__init__("That isn't ready yet.")
        self.seconds_left = seconds_left


@dataclass(frozen=True)
class CooldownState:
    ready: bool
    seconds_left: float  # 0 when ready


def cooldown_state(user: User, cooldown: Cooldowns, now: float | None = None) -> CooldownState:
    now = time.time() if now is None else now
    left = user.get_cooldown(cooldown) + cooldown.value * 3600 - now
    return CooldownState(ready=left <= 0, seconds_left=max(0.0, left))


async def _claim(user: User, cooldown: Cooldowns) -> None:
    if not await user.claim_cooldown(cooldown):
        await user.refresh()
        raise OnCooldown(cooldown_state(user, cooldown).seconds_left)


@dataclass(frozen=True)
class WorkReward:
    wage: int


async def claim_work(user: User, registry: Registry | None = None) -> WorkReward:
    """Collect this rank's wage."""
    await _claim(user, Cooldowns.WORK)
    from cococap.services import pets

    reg = registry or get_registry()
    wage = round(reg.rank(user.rank).wage * (1 + (await pets.bonuses(user, reg)).get("work_bonus", 0.0)))
    await user.add_bits(wage)
    await user.inc_stat("claimed_work")
    return WorkReward(wage)


def daily_interest(purse: int) -> int:
    """Interest on the bits you carry, paid with the daily: a rate that shrinks as the purse grows, so a huge one can't snowball."""
    rate = 0.003 + 0.027 * math.exp(-purse / 20_000_000)
    return round(purse * rate)


@dataclass(frozen=True)
class DailyReward:
    interest: int
    tokens: int


async def claim_daily(user: User) -> DailyReward:
    await _claim(user, Cooldowns.DAILY)
    await user.refresh()
    from cococap.services import pets

    interest = await pets.payout(user, daily_interest(user.purse))  # (a Raven pays a few % more)
    await user.add_bits(interest)
    await user.add_tokens(DAILY_TOKENS)
    await user.inc_stat("claimed_daily")
    return DailyReward(interest, DAILY_TOKENS)


async def claim_weekly(user: User, registry: Registry | None = None) -> int:
    await _claim(user, Cooldowns.WEEKLY)
    amount = (registry or get_registry()).economy.weekly_luckbucks
    await user.add_luckbucks(amount)
    await user.inc_stat("claimed_weekly")
    return amount
