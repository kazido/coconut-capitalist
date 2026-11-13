"""Shared bookkeeping for the brain games: win streaks and the capped luckbucks payout."""

from cococap.services.rewards import Reward, pay_minigame
from cococap.user import User


async def record_win(user: User, streak_stat: str, longest_stat: str, base_reward: float) -> tuple[int, bool, Reward]:
    """A win: extend the streak and pay luckbucks. Returns (streak, new_record, reward)."""
    await user.inc_stat(streak_stat)
    streak = await user.get_stat(streak_stat)
    record = streak > await user.get_stat(longest_stat)
    if record:
        await user.set_stat(longest_stat, streak)
    return streak, record, await pay_minigame(user, base_reward, streak)


async def record_loss(user: User, streak_stat: str) -> int:
    """A loss or timeout: the streak resets. Returns the streak that was lost."""
    lost = await user.get_stat(streak_stat)
    await user.set_stat(streak_stat, 0)
    return lost
