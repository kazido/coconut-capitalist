from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import flashcard, sequence, trivia, unscramble
from cococap.services.minigame import record_loss, record_win
from cococap.services.trivia import TriviaUnavailable, parse_question
from cococap.user import User

PAY = get_registry().economy.minigames.payout
START = get_registry().economy.starting_luckbucks


async def luck(user=None):
    return (await User.get(1)).luckbucks if user is None else (await User.get(user.id)).luckbucks


# ---- shared streak bookkeeping ---------------------------------------------------------------
async def test_wins_extend_the_streak_and_set_records_losses_reset_it(db):
    user = await User.get(1)
    s1, rec1, r1 = await record_win(user, "s", "longest_s", 10)
    s2, rec2, r2 = await record_win(user, "s", "longest_s", 10)
    assert (s1, rec1, r1.granted) == (1, True, 10) and (s2, rec2, r2.granted) == (2, True, 11)  # +10% at streak 2
    assert await record_loss(user, "s") == 2 and await user.get_stat("s") == 0
    s3, rec3, _ = await record_win(user, "s", "longest_s", 10)
    assert (s3, rec3) == (1, False)  # below the record of 2
    assert await user.get_stat("longest_s") == 2


# ---- flashcard ---------------------------------------------------------------------------------
def test_flashcard_problem_and_options():
    for seed in range(200):
        g = flashcard.FlashcardGame(Random(seed))
        assert g.answer in g.options and len(set(g.options)) == 4
        assert g.answer == eval(g.problem)  # the sum shown is the sum solved


def test_flashcard_timing_with_a_little_grace():
    g = flashcard.FlashcardGame(Random(1))
    g.reveal(now=100.0)
    assert g.check(g.answer, 100 + g.time_limit + flashcard.GRACE - 0.1) == "correct"
    g2 = flashcard.FlashcardGame(Random(1))
    g2.reveal(100.0)
    assert g2.check(g2.answer, 100 + g2.time_limit + flashcard.GRACE + 0.1) == "late"
    g3 = flashcard.FlashcardGame(Random(1))
    g3.reveal(100.0)
    assert g3.check(g3.answer + 1, 101) == "wrong"
    assert g3.check(g3.answer, 101) == "wrong"  # only the first answer counts


async def test_flashcard_pays_luckbucks_not_bits_and_resets_on_a_miss(db):
    user = await User.get(1)
    game = await flashcard.start(user, Random(1))
    game.reveal(0.0)
    out = await flashcard.answer(user, game, game.answer, 1.0)
    assert out.result == "correct" and out.streak == 1 and out.reward.granted == getattr(PAY, game.payout_key)
    assert (await User.get(1)).luckbucks == START + out.reward.granted and user.purse == 1000
    nxt = await flashcard.start(user, Random(2))
    nxt.reveal(0.0)
    miss = await flashcard.answer(user, nxt, nxt.answer + 1, 1.0)
    assert miss.result == "wrong" and miss.lost_streak == 1 and miss.reward is None
    assert await user.get_stat("flashcard_games") == 2 and await user.get_stat("flashcard_streak") == 0
    with pytest.raises(ValueError):
        await flashcard.answer(user, nxt, nxt.answer, 1.0)


# ---- unscramble ---------------------------------------------------------------------------------
def test_word_list_is_usable():
    words = unscramble.load_words()
    assert len(words) > 1000 and all(w.islower() and len(w) >= 4 for w in words)


def test_scramble_is_a_real_shuffle():
    for seed in range(100):
        word = "garden"
        s = unscramble.scramble(word, Random(seed))
        assert s != word and sorted(s) == sorted(word)
    assert unscramble.scramble("aaaa", Random(1)) == "aaaa"  # can't shuffle identical letters (no infinite loop)


async def test_unscramble_pays_by_length_and_accepts_any_case_and_spaces(db):
    user = await User.get(1)
    game = await unscramble.start(user, Random(1), words=["garden"])
    game.reveal(0.0)
    out = await unscramble.answer(user, game, "  GARDEN ", 5.0)
    assert out.result == "correct" and out.reward.granted == round(6 * PAY.unscramble_per_letter)


async def test_unscramble_late_and_wrong(db):
    user = await User.get(1)
    for text, now, result in (("garden", 10 + 12 + unscramble.GRACE + 1, "late"), ("nope", 3.0, "wrong")):
        game = await unscramble.start(user, Random(1), words=["garden"])
        game.reveal(0.0)
        out = await unscramble.answer(user, game, text, now)
        assert out.result == result and out.reward is None
    assert (await User.get(1)).luckbucks == START


# ---- sequence ---------------------------------------------------------------------------------------
def test_sequence_rounds_grow_and_a_mistake_ends_it():
    g = sequence.SequenceGame("easy", Random(3))
    assert len(g.pattern) == 1
    assert g.guess(g.pattern[0]) == "round" and g.score == 1 and len(g.pattern) == 2
    assert g.guess(g.pattern[0]) == "ok"
    assert g.guess(g.pattern[1]) == "round" and g.score == 2 and len(g.pattern) == 3
    wrong = next(o for o in g.options if o != g.pattern[0])
    assert g.guess(wrong) == "wrong" and g.over
    with pytest.raises(ValueError):
        g.guess(g.pattern[0])


@pytest.mark.parametrize("difficulty, multiplier", [("easy", 1), ("medium", 2), ("hard", 3)])
async def test_sequence_pays_per_element_scaled_by_difficulty_once(db, difficulty, multiplier):
    user = await User.get(1)
    game = await sequence.start(user, difficulty, Random(1))
    game.score = 5
    reward = await sequence.finish(user, game)
    assert reward.granted == 5 * PAY.sequence_per_element * multiplier
    assert await sequence.finish(user, game) is None  # not twice
    assert (await User.get(1)).luckbucks == START + reward.granted and await user.get_stat("longest_sq_streak") == 5


async def test_sequence_with_nothing_remembered_pays_nothing(db):
    user = await User.get(1)
    game = await sequence.start(user, "easy", Random(1))
    assert await sequence.finish(user, game) is None and (await User.get(1)).luckbucks == START


# ---- trivia -------------------------------------------------------------------------------------------
RAW = {"category": "science", "difficulty": "hard", "correctAnswer": "Mars",
       "incorrectAnswers": ["Venus", "Earth", "Pluto"], "question": {"text": "Which is the red planet?"}}


def test_parse_question():
    q = parse_question(RAW)
    assert (q.text, q.category, q.difficulty, q.correct) == ("Which is the red planet?", "Science", "hard", "Mars")
    for broken in ({}, {"question": {}}, None):
        with pytest.raises(TriviaUnavailable):
            parse_question(broken)


async def fetch_ok():
    return RAW


async def fetch_down():
    raise TriviaUnavailable("down")


async def test_trivia_answer_flow_pays_by_difficulty(db):
    user = await User.get(1)
    game = await trivia.start(user, Random(1), fetch_ok)
    assert sorted(game.answers) == sorted(["Mars", "Venus", "Earth", "Pluto"])
    game.reveal(0.0)
    out = await trivia.answer(user, game, game.answers.index("Mars"), 3.0)
    assert out.result == "correct" and out.reward.granted == PAY.trivia_hard
    assert await user.get_stat("trivia_wins") == 1 and await user.get_stat("trivia_games") == 1


async def test_trivia_wrong_and_late_reset_the_streak(db):
    user = await User.get(1)
    for index_fn, now, expected in ((lambda g: g.answers.index("Venus"), 3.0, "wrong"), (lambda g: g.answers.index("Mars"), 999.0, "late")):
        game = await trivia.start(user, Random(1), fetch_ok)
        game.reveal(0.0)
        out = await trivia.answer(user, game, index_fn(game), now)
        assert out.result == expected and out.reward is None
    assert (await User.get(1)).luckbucks == START


async def test_trivia_outage_records_nothing(db):
    user = await User.get(1)
    with pytest.raises(TriviaUnavailable):
        await trivia.start(user, Random(1), fetch_down)
    assert await user.get_stat("trivia_games") == 0


async def test_spamming_trivia_all_day_cannot_out_earn_the_cap(db):
    user = await User.get(1)
    for i in range(200):
        game = await trivia.start(user, Random(i), fetch_ok)
        game.reveal(0.0)
        await trivia.answer(user, game, game.answers.index("Mars"), 1.0)
    cap = get_registry().economy.minigames.daily_cap
    assert (await User.get(1)).luckbucks == START + cap
