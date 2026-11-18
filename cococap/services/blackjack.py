"""Blackjack against the house. ``BlackjackGame`` is a pure state machine (cards, totals, outcome);
the async functions take the bet and settle it exactly once."""

import random

from cococap import constants, emojis
from cococap.constants import BOT_ID
from cococap.services.casino import GameOver, place_bet
from cococap.user import User

SUITS = "♠♥♦♣"  # the plain suit characters stay the card identity; show() swaps them for icons
_SUIT_ICONS = {"♠": lambda: emojis.icon("spade", "♠"), "♥": lambda: emojis.icon("suit_heart", "♥"),
               "♦": lambda: emojis.icon("diamond", "♦"), "♣": lambda: emojis.icon("club", "♣")}
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
Card = tuple[str, str]  # (rank, suit)

# outcome -> how much of the bet comes back (2 = double your money). Same payouts as the old game.
PAYOUT_MULTIPLIER = {"blackjack": 2.0, "win": 2.0, "push": 1.0, "fold": 0.5, "lose": 0.0, "bust": 0.0, "forfeit": 0.0}


def card_value(rank: str) -> int:
    return 11 if rank == "A" else 10 if rank in ("J", "Q", "K") else int(rank)


def hand_total(hand: list[Card]) -> int:
    """Best total: aces count 11 unless that would bust, then 1."""
    total = sum(card_value(rank) for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def show(hand: list[Card]) -> str:
    return " ".join(f"{rank}{_SUIT_ICONS[suit]()}" for rank, suit in hand)


class BlackjackGame:
    def __init__(self, bet: int, rng: random.Random, currency: str | None = None):
        self.bet, self.currency = bet, currency or constants.CASINO_CURRENCY
        self.deck: list[Card] = [(r, s) for r in RANKS for s in SUITS]
        rng.shuffle(self.deck)
        self.player: list[Card] = [self._draw(), self._draw()]
        self.dealer: list[Card] = [self._draw()]
        self.outcome: str | None = "blackjack" if hand_total(self.player) == 21 else None
        self.settled = False

    def _draw(self) -> Card:
        return self.deck.pop()

    @property
    def finished(self) -> bool:
        return self.outcome is not None

    @property
    def can_fold(self) -> bool:
        return not self.finished and len(self.player) == 2

    @property
    def payout(self) -> int:
        return int(self.bet * PAYOUT_MULTIPLIER[self.outcome or "lose"])

    def _require_live(self) -> None:
        if self.finished:
            raise GameOver("This hand is over.")

    def hit(self) -> None:
        self._require_live()
        self.player.append(self._draw())
        total = hand_total(self.player)
        if total > 21:
            self.outcome = "bust"
        elif total == 21:
            self.stand()  # nothing better to do with 21

    def stand(self) -> None:
        self._require_live()
        while hand_total(self.dealer) < 17:  # the dealer draws to 17
            self.dealer.append(self._draw())
        player, dealer = hand_total(self.player), hand_total(self.dealer)
        self.outcome = "win" if dealer > 21 or player > dealer else "push" if player == dealer else "lose"

    def fold(self) -> None:
        self._require_live()
        if not self.can_fold:
            raise GameOver("You can only fold on your first move.")
        self.outcome = "fold"


async def _settle(user: User, game: BlackjackGame) -> int:
    """Pay the player their share and the house the rest. Idempotent: runs once per game."""
    if game.settled:
        return 0
    game.settled = True
    payout = game.payout
    if payout > 0:
        await user.credit(game.currency, payout)
    if game.bet > payout:  # a lost or folded bet goes to the house account
        house = await User.get(BOT_ID)
        await house.credit(game.currency, game.bet - payout)
    if game.outcome in ("win", "blackjack"):
        await user.inc_stat("blackjack_wins")
    if game.outcome == "blackjack":
        await user.inc_stat("blackjacks")
    if game.outcome == "bust":
        await user.inc_stat("blackjack_busts")
    return payout


async def start(user: User, amount: str | int, rng: random.Random, currency: str | None = None) -> BlackjackGame:
    currency = currency or constants.CASINO_CURRENCY
    bet = await place_bet(user, amount, currency, "blackjack_games")
    game = BlackjackGame(bet, rng, currency)
    if game.finished:  # dealt a natural 21
        await _settle(user, game)
    return game


async def hit(user: User, game: BlackjackGame) -> None:
    game.hit()
    await user.inc_stat("blackjack_hits")
    if game.finished:
        await _settle(user, game)


async def stand(user: User, game: BlackjackGame) -> None:
    game.stand()
    await user.inc_stat("blackjack_stands")
    await _settle(user, game)


async def fold(user: User, game: BlackjackGame) -> None:
    game.fold()
    await user.inc_stat("blackjack_folds")
    await _settle(user, game)


async def abandon(user: User, game: BlackjackGame) -> None:
    """The player walked away mid-hand: the bet is forfeited to the house."""
    if not game.finished:
        game.outcome = "forfeit"
    await _settle(user, game)
