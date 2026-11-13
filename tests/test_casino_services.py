import asyncio
from random import Random

import pytest

from cococap.constants import BOT_ID
from cococap.errors import InvalidAmount
from cococap.services import blackjack as bj
from cococap.services import highlow as hl
from cococap.services.casino import GameOver
from cococap.user import User
from tests.conftest import set_columns


@pytest.fixture(autouse=True)
def stake_bits(monkeypatch):
    """These tests are about the rules, so stake bits (purse); one test below covers luckbucks."""
    monkeypatch.setattr("cococap.constants.CASINO_CURRENCY", "purse")


async def player(purse=1000, uid=1):
    user = await User.get(uid)
    await set_columns(user, purse=purse)
    return user


async def house_balance():
    return (await User.get(BOT_ID)).purse


# ======================= High-Low ================================================================
def test_highlow_rules_are_pure():
    game = hl.HighLowGame(100, Random(1))
    game.roll = 8
    r = game.guess(high=True)
    assert r.correct and r.roll == 8 and game.multiplier == 2 and game.pot == 200
    game.roll = 3
    r = game.guess(high=True)  # 3 is low
    assert not r.correct and game.multiplier == 0 and game.pot == 0


@pytest.mark.parametrize("roll, high, correct", [(1, False, True), (5, False, True), (6, True, True), (10, True, True), (5, True, False), (6, False, False)])
def test_highlow_boundaries(roll, high, correct):
    game = hl.HighLowGame(10, Random(0))
    game.roll = roll
    assert game.guess(high).correct is correct


async def test_highlow_win_then_cash_out_pays_the_pot(db):
    user = await player()
    game = await hl.start(user, "100", Random(1))
    assert user.purse == 900 and await user.get_stat("highlow_games") == 1
    game.roll = 9
    await hl.guess(user, game, True)
    game.roll = 2
    await hl.guess(user, game, False)
    assert game.multiplier == 4
    assert await hl.cash_out(user, game) == 400
    assert await user.get_bits() == 900 + 400
    assert await user.get_stat("hl_wins") == 2 and await user.get_stat("longest_hl_streak") == 2
    assert await user.get_stat("biggest_hl_win") == 300  # net profit
    with pytest.raises(GameOver):
        await hl.cash_out(user, game)  # can't cash out twice
    assert await user.get_bits() == 1300


async def test_highlow_loss_goes_to_the_house_once(db):
    user = await player()
    before = await house_balance()
    game = await hl.start(user, "250", Random(1))
    game.roll = 1
    await hl.guess(user, game, True)
    assert game.finished and await user.get_bits() == 750
    assert await house_balance() == before + 250
    await hl._settle(user, game)  # a duplicate settle (e.g. timeout after a loss) changes nothing
    assert await house_balance() == before + 250 and await user.get_stat("biggest_hl_loss") == -250
    with pytest.raises(GameOver):
        game.guess(True)


async def test_highlow_abandon_pays_what_was_earned_not_nothing(db):
    user = await player()
    game = await hl.start(user, "100", Random(1))
    await hl.abandon(user, game)
    await hl.abandon(user, game)
    assert await user.get_bits() == 1000  # the bet comes back, once


async def test_bad_bets_take_nothing(db):
    user = await player(500)
    for bad in ("0", "501", "abc", "200%", ""):
        with pytest.raises(InvalidAmount):
            await hl.start(user, bad, Random(1))
    assert await user.get_bits() == 500 and await user.get_stat("highlow_games") == 0


async def test_percent_and_max_bets(db):
    user = await player(1000)
    assert (await hl.start(user, "25%", Random(1))).bet == 250
    assert (await hl.start(user, "max", Random(1))).bet == 750 and await user.get_bits() == 0


async def test_concurrent_bets_cannot_overspend(db):
    await player(1000)
    handles = [await User.get(1) for _ in range(5)]
    results = await asyncio.gather(*(hl.start(h, "600", Random(i)) for i, h in enumerate(handles)), return_exceptions=True)
    assert sum(not isinstance(r, Exception) for r in results) == 1
    assert (await User.get(1)).purse == 400


async def test_the_stake_currency_can_be_luckbucks(db):
    user = await player()
    await set_columns(user, luckbucks=500)
    game = await hl.start(user, "100", Random(1), "luckbucks")
    assert user.luckbucks == 400 and user.purse == 1000  # bits untouched
    await hl.abandon(user, game)
    assert (await User.get(1)).luckbucks == 500


# ======================= Blackjack ===============================================================
def rig(game, player=None, dealer=None, deck=None):
    if player is not None:
        game.player = player
    if dealer is not None:
        game.dealer = dealer
    if deck is not None:
        game.deck = deck  # cards are drawn from the end of the list


def test_hand_totals_and_aces():
    t = lambda *ranks: bj.hand_total([(r, "♠") for r in ranks])
    assert t("10", "K") == 20 and t("A", "K") == 21 and t("A", "A") == 12
    assert t("A", "A", "9") == 21 and t("A", "9", "5") == 15 and t("K", "Q", "5") == 25


def test_a_fresh_deck_has_52_unique_cards():
    game = bj.BlackjackGame(10, Random(1))
    seen = game.deck + game.player + game.dealer
    assert len(seen) == 52 and len(set(seen)) == 52


def test_natural_blackjack_is_detected_at_the_deal():
    for seed in range(300):
        game = bj.BlackjackGame(10, Random(seed))
        assert (game.outcome == "blackjack") == (bj.hand_total(game.player) == 21)


def test_bust_stand_push_and_dealer_draws_to_17():
    game = bj.BlackjackGame(10, Random(1))
    rig(game, player=[("10", "♠"), ("6", "♠")], deck=[("K", "♦")])
    game.outcome = None
    game.hit()
    assert game.outcome == "bust"

    game = bj.BlackjackGame(10, Random(1))
    rig(game, player=[("10", "♠"), ("8", "♠")], dealer=[("6", "♥")], deck=[("2", "♣"), ("K", "♦")])  # dealer: 6+K=16, +2=18
    game.outcome = None
    game.stand()
    assert bj.hand_total(game.dealer) == 18 and game.outcome == "push"

    game = bj.BlackjackGame(10, Random(1))
    rig(game, player=[("10", "♠"), ("7", "♠")], dealer=[("10", "♥")], deck=[("9", "♦")])
    game.outcome = None
    game.stand()
    assert game.outcome == "lose" and len(game.dealer) == 2  # dealer sat on 19... after one draw


def test_hitting_to_21_stands_automatically():
    game = bj.BlackjackGame(10, Random(1))
    rig(game, player=[("10", "♠"), ("5", "♠")], dealer=[("10", "♥")], deck=[("7", "♦"), ("6", "♣")])
    game.outcome = None
    game.hit()  # 10+5+6 = 21
    assert game.finished and game.outcome in ("win", "push")


def test_fold_only_on_the_first_move():
    game = bj.BlackjackGame(10, Random(1))
    rig(game, player=[("2", "♠"), ("3", "♠")], deck=[("2", "♦"), ("3", "♦")])
    game.outcome = None
    assert game.can_fold
    game.hit()
    assert not game.can_fold
    with pytest.raises(GameOver):
        game.fold()


async def settle_scenario(db, outcome, bet=100):
    user = await player()
    game = await bj.start(user, str(bet), Random(1))
    if game.finished:  # avoid the natural: rig a plain hand
        game = bj.BlackjackGame(bet, Random(1))
    return user, game


async def test_blackjack_payouts_settle_exactly_once(db):
    for outcome, expected_back in (("win", 200), ("push", 100), ("fold", 50), ("lose", 0), ("bust", 0), ("forfeit", 0)):
        user = await player(1000)
        before_house = await house_balance()
        game = bj.BlackjackGame(100, Random(1))
        await user.spend("purse", 100)  # what start() does
        game.outcome = outcome
        await bj._settle(user, game)
        await bj._settle(user, game)  # idempotent
        assert (await User.get(1)).purse == 900 + expected_back, outcome
        assert await house_balance() - before_house == max(0, 100 - expected_back), outcome


async def test_start_hit_stand_flow_with_stats(db):
    user = await player()
    game = await bj.start(user, "100", Random(7))
    if game.finished:
        pytest.skip("seed dealt a natural")
    rig(game, player=[("10", "♠"), ("8", "♠")], dealer=[("6", "♥")], deck=[("K", "♦"), ("10", "♣")])
    await bj.stand(user, game)
    assert game.outcome == "win" and (await User.get(1)).purse == 900 + 200
    assert await user.get_stat("blackjack_stands") == 1 and await user.get_stat("blackjack_wins") == 1
    with pytest.raises(GameOver):
        await bj.stand(user, game)
    assert (await User.get(1)).purse == 1100


async def test_natural_blackjack_pays_once_at_the_deal(db):
    for seed in range(500):
        user = await player(1000, uid=seed + 10)
        game = await bj.start(user, "100", Random(seed))
        if game.outcome == "blackjack":
            assert (await User.get(user.id)).purse == 900 + 200
            assert await user.get_stat("blackjacks") == 1
            return
    pytest.fail("no natural in 500 deals")


async def test_abandoned_hand_forfeits_once(db):
    user = await player()
    before = await house_balance()
    game = await bj.start(user, "100", Random(7))
    if game.finished:
        pytest.skip("natural")
    await bj.abandon(user, game)
    await bj.abandon(user, game)
    assert (await User.get(1)).purse == 900 and await house_balance() == before + 100
