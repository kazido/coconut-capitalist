"""High-Low: guess whether the next number is high (6-10) or low (1-5). Each right guess doubles the
pot; cash out any time, or lose it all on a wrong guess.

``HighLowGame`` is a pure state machine. The async functions persist: they take the stake up front and
settle it **exactly once** (cash out, loss, or abandonment all go through ``_settle``).
"""

import random
from dataclasses import dataclass

from cococap import constants
from cococap.constants import BOT_ID
from cococap.services.casino import GameOver, place_bet, record_result
from cococap.user import User

HIGH = range(6, 11)


@dataclass(frozen=True)
class GuessResult:
    correct: bool
    roll: int  # the number that decided this guess
    multiplier: int  # the pot multiplier after this guess (0 after a loss)


class HighLowGame:
    def __init__(self, bet: int, rng: random.Random, currency: str | None = None):
        self.bet = bet
        self.currency = currency or constants.CASINO_CURRENCY
        self.rng = rng
        self.multiplier = 1
        self.roll = rng.randint(1, 10)  # hidden until you guess
        self.last: GuessResult | None = None
        self.settled = False

    @property
    def pot(self) -> int:
        return self.bet * self.multiplier

    @property
    def finished(self) -> bool:
        return self.settled

    def guess(self, high: bool) -> GuessResult:
        """Pure rule: resolve one guess. Doubles the pot or zeroes it."""
        if self.settled:
            raise GameOver("This game is over.")
        correct = (self.roll in HIGH) == high
        decided = self.roll
        if correct:
            self.multiplier *= 2
            self.roll = self.rng.randint(1, 10)
        else:
            self.multiplier = 0
        self.last = GuessResult(correct, decided, self.multiplier)
        return self.last


async def start(user: User, amount: str | int, rng: random.Random, currency: str | None = None) -> HighLowGame:
    currency = currency or constants.CASINO_CURRENCY
    bet = await place_bet(user, amount, currency, "highlow_games")
    return HighLowGame(bet, rng, currency)


async def _settle(user: User, game: HighLowGame) -> int:
    """Pay out the pot (to the player) or the lost bet (to the house). Idempotent."""
    if game.settled:
        return 0
    game.settled = True
    payout = game.pot
    await record_result(user, game.bet, payout)
    if payout > 0:
        await user.credit(game.currency, payout)
    else:
        house = await User.get(BOT_ID)
        await house.credit(game.currency, game.bet)
    return payout


async def guess(user: User, game: HighLowGame, high: bool) -> GuessResult:
    result = game.guess(high)
    if result.correct:
        await user.set_stat("hl_loss_streak")
        await user.inc_stat("hl_win_streak")
        streak = await user.get_stat("hl_win_streak")
        if streak > await user.get_stat("longest_hl_streak"):
            await user.set_stat("longest_hl_streak", streak)
        await user.inc_stat("hl_wins")
    else:
        await user.inc_stat("hl_loss_streak")
        await user.set_stat("hl_win_streak")
        streak = await user.get_stat("hl_loss_streak")
        if streak > await user.get_stat("longest_hl_loss_streak"):
            await user.set_stat("longest_hl_loss_streak", streak)
        if -game.bet < await user.get_stat("biggest_hl_loss"):
            await user.set_stat("biggest_hl_loss", -game.bet)
        await _settle(user, game)
    return result


async def cash_out(user: User, game: HighLowGame) -> int:
    """Take the pot. Returns the payout."""
    if game.settled:
        raise GameOver("This game is over.")
    payout = await _settle(user, game)
    profit = payout - game.bet
    if profit > await user.get_stat("biggest_hl_win"):
        await user.set_stat("biggest_hl_win", profit)
    return payout


async def abandon(user: User, game: HighLowGame) -> None:
    """The player walked away: pay out what they'd earned rather than destroying it."""
    await _settle(user, game)
