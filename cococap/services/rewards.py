"""Luckbucks from minigames (capped per day) and the one-way bits -> luckbucks exchange."""

from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.user import InsufficientFunds, User


@dataclass(frozen=True)
class Reward:
    granted: int  # what the player actually received
    earned: int  # what the win was worth before the daily cap
    capped: bool  # the daily cap trimmed (or removed) the reward
    streak_bonus: float  # e.g. 0.3 for +30%


def with_streak(base: float, streak: int, registry: Registry | None = None) -> tuple[int, float]:
    """Apply the win-streak bonus to a base payout. Returns (amount, bonus fraction)."""
    rules = (registry or get_registry()).economy.minigames
    steps = max(0, min(streak - 1, rules.streak_bonus_max_steps))
    bonus = steps * rules.streak_bonus
    return round(base * (1 + bonus)), bonus


async def pay_minigame(user: User, base: float, streak: int = 1, registry: Registry | None = None) -> Reward:
    """Pay a minigame win in luckbucks: streak bonus, then the shared daily cap."""
    rules = (registry or get_registry()).economy.minigames
    earned, bonus = with_streak(base, streak, registry)
    granted = await user.grant_daily_capped("minigames", "luckbucks", earned, rules.daily_cap)
    if granted:
        await user.inc_stat("luckbucks_earned", granted)
    return Reward(granted, earned, capped=granted < earned, streak_bonus=bonus)


class ExchangeError(GameRuleError):
    pass


async def exchange_bits(user: User, luckbucks: int, registry: Registry | None = None) -> tuple[int, int]:
    """Buy `luckbucks` with bits. Returns (luckbucks received, bits spent).

    Limited per day; if the limit trims the order, the unused bits are returned.
    """
    rules = (registry or get_registry()).economy.exchange
    if luckbucks < 1:
        raise ExchangeError("Exchange at least 1 luckbuck.")
    cost = luckbucks * rules.bits_per_luckbuck
    try:
        await user.spend("purse", cost)
    except InsufficientFunds:
        raise ExchangeError(f"You need {cost:,} bits for that.") from None
    try:
        granted = await user.grant_daily_capped("exchange", "luckbucks", luckbucks, rules.daily_limit)
    except Exception:
        await user.credit("purse", cost)
        raise
    if granted < luckbucks:
        await user.credit("purse", (luckbucks - granted) * rules.bits_per_luckbuck)
    if granted == 0:
        raise ExchangeError(f"You've reached today's exchange limit of {rules.daily_limit:,} luckbucks.")
    return granted, granted * rules.bits_per_luckbuck
