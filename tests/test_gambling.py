from types import SimpleNamespace
from unittest.mock import AsyncMock

import pydealer

from cococap.constants import BOT_ID
from cococap.exts.gambling.blackjack import Actions, BlackjackGame, GameStates
from cococap.exts.gambling.high_low import HighlowGame
from cococap.user import User
from tests.conftest import set_columns


async def start_game(cls, db_bet=100, purse=1000):
    """Mimic the cog's interaction_check: load the user and take the bet up front."""
    user = await User.get(1)
    await set_columns(user, purse=purse)
    await user.remove_bits(db_bet)
    interaction = SimpleNamespace(
        user=SimpleNamespace(display_name="tester", display_avatar="http://x/a.png"),
        extras={"user": user, "bet": db_bet},
        edit_original_response=AsyncMock(),
    )
    return cls(interaction=interaction), user


def card(value, suit="Spades"):
    return pydealer.Card(value, suit)


async def test_natural_blackjack_pays_exactly_once(db):
    game, user = await start_game(BlackjackGame)
    game.player.hand = [card("Ace"), card("King")]
    # update() runs after every deal (player cards, then the dealer's card); it used to pay each time
    for _ in range(3):
        embed = await game.update(Actions.DEAL)
    assert game.state == GameStates.BLACKJACK
    assert await user.get_bits() == 900 + 200  # bet back + 1x winnings, paid once
    assert await user.get_stat("blackjacks") == 1
    assert embed is not None


async def test_abandoned_blackjack_hand_forfeits_bet_to_house_once(db):
    game, user = await start_game(BlackjackGame)
    await game.on_timeout()
    await game.on_timeout()
    house = await User.get(BOT_ID)
    assert await house.get_bits() == 1000 + 100
    assert await user.get_bits() == 900


async def test_highlow_timeout_returns_the_bet(db):
    game, user = await start_game(HighlowGame)
    assert await user.get_bits() == 900
    await game.on_timeout()
    assert await user.get_bits() == 1000
    await game.on_timeout()  # idempotent
    assert await user.get_bits() == 1000


async def test_highlow_timeout_after_wins_pays_current_multiplier(db):
    game, user = await start_game(HighlowGame)
    game.multiplier = 4
    await game.on_timeout()
    assert await user.get_bits() == 900 + 400


async def test_highlow_double_cashout_pays_once(db):
    game, user = await start_game(HighlowGame)
    game.multiplier = 2
    inter = SimpleNamespace(
        response=SimpleNamespace(edit_message=AsyncMock(), defer=AsyncMock())
    )
    await game.process_cashout(inter)
    await game.process_cashout(inter)
    assert await user.get_bits() == 900 + 200
