"""Shared by the casino games: taking a bet."""

from cococap.errors import GameRuleError
from cococap.user import User
from utils.utils import parse_bits


class GameOver(GameRuleError):
    pass


async def place_bet(user: User, amount: str | int, currency: str, stat: str) -> int:
    """Validate `amount` against the player's balance and take it. Returns the bet.

    Accepts a number, k/m suffixes, a percentage, or "max". Raises InvalidAmount if it's not a legal
    bet (nothing is taken); the game's service is responsible for settling the bet exactly once.
    """
    await user.refresh()
    unit = "bits" if currency == "purse" else currency
    bet = parse_bits(amount, user.balance(currency), unit)
    await user.spend(currency, bet)
    await user.inc_stat(stat)
    return bet
