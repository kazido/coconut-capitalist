"""Unscramble: type the word before the clock runs out. Longer words pay more."""

import random
from dataclasses import dataclass

from cococap.constants import PROJECT_ROOT
from cococap.registry import Registry, get_registry
from cococap.services.minigame import record_loss, record_win
from cococap.services.rewards import Reward
from cococap.user import User

GRACE = 2.0  # opening a pop-up and typing needs slack


def load_words(min_length: int = 4) -> list[str]:
    path = PROJECT_ROOT / "resources" / "unscramble_words.txt"
    return [w for w in (line.strip() for line in path.read_text().splitlines()) if w.islower() and len(w) >= min_length]


def scramble(word: str, rng: random.Random) -> str:
    """A shuffle that is never the word itself (unless every letter is the same)."""
    letters = list(word)
    if len(set(word)) == 1:
        return word
    while True:
        rng.shuffle(letters)
        if "".join(letters) != word:
            return "".join(letters)


class UnscrambleGame:
    def __init__(self, word: str, rng: random.Random):
        self.word = word
        self.scrambled = scramble(word, rng)
        self.time_limit = 10 + 2 * len(word)
        self.deadline: float | None = None
        self.result: str | None = None

    def reveal(self, now: float) -> None:
        self.deadline = now + self.time_limit

    def check(self, text: str, now: float) -> str:
        if self.result is None:
            if self.deadline is None or now > self.deadline + GRACE:
                self.result = "late"
            else:
                self.result = "correct" if text.strip().lower() == self.word else "wrong"
        return self.result


@dataclass(frozen=True)
class Outcome:
    result: str
    streak: int
    lost_streak: int
    new_record: bool
    reward: Reward | None


async def start(user: User, rng: random.Random, words: list[str] | None = None) -> UnscrambleGame:
    await user.inc_stat("unscramble_games")
    return UnscrambleGame(rng.choice(words or load_words()), rng)


async def answer(user: User, game: UnscrambleGame, text: str, now: float, registry: Registry | None = None) -> Outcome:
    if game.result is not None:
        raise ValueError("already answered")
    result = game.check(text, now)
    if result != "correct":
        return Outcome(result, 0, await record_loss(user, "unscramble_streak"), False, None)
    per_letter = (registry or get_registry()).economy.minigames.payout.unscramble_per_letter
    streak, record, reward = await record_win(user, "unscramble_streak", "longest_unscramble_streak", len(game.word) * per_letter)
    return Outcome(result, streak, 0, record, reward)
