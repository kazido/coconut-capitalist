"""Flashcard: pick the answer to a quick sum before the clock runs out."""

import random
from dataclasses import dataclass

from cococap.registry import Registry, get_registry
from cococap.services.minigame import record_loss, record_win
from cococap.services.rewards import Reward
from cococap.user import User

OPERATORS = {  # operator: (seconds allowed, payout key in economy.toml)
    "+": (6, "flashcard_add"),
    "-": (8, "flashcard_sub"),
    "*": (15, "flashcard_mul"),
}
GRACE = 1.5  # seconds of network slack, so a fair click never counts as late


class FlashcardGame:
    def __init__(self, rng: random.Random):
        self.operator = rng.choice(list(OPERATORS))
        self.x, self.y = rng.randint(10, 20), rng.randint(10, 20)
        self.answer = {"+": self.x + self.y, "-": self.x - self.y, "*": self.x * self.y}[self.operator]
        self.time_limit, self.payout_key = OPERATORS[self.operator]
        wrong: set[int] = set()
        while len(wrong) < 3:  # near misses make it a real question
            guess = self.answer + rng.choice([-1, 1]) * rng.randint(1, 10 if self.operator != "*" else 30)
            if guess != self.answer:
                wrong.add(guess)
        self.options = sorted([self.answer, *wrong])
        self.deadline: float | None = None  # set by reveal()
        self.result: str | None = None  # "correct" | "wrong" | "late"

    @property
    def problem(self) -> str:
        return f"{self.x} {self.operator} {self.y}"

    def reveal(self, now: float) -> None:
        self.deadline = now + self.time_limit

    def check(self, choice: int, now: float) -> str:
        """Pure rule: judge an answer. Only the first answer counts."""
        if self.result is None:
            if self.deadline is None or now > self.deadline + GRACE:
                self.result = "late"
            else:
                self.result = "correct" if choice == self.answer else "wrong"
        return self.result


@dataclass(frozen=True)
class Outcome:
    result: str
    streak: int  # the streak after this answer (0 after a miss)
    lost_streak: int
    new_record: bool
    reward: Reward | None


async def start(user: User, rng: random.Random) -> FlashcardGame:
    await user.inc_stat("flashcard_games")
    return FlashcardGame(rng)


async def answer(user: User, game: FlashcardGame, choice: int, now: float, registry: Registry | None = None) -> Outcome:
    if game.result is not None:
        raise ValueError("already answered")
    result = game.check(choice, now)
    if result != "correct":
        return Outcome(result, 0, await record_loss(user, "flashcard_streak"), False, None)
    base = getattr((registry or get_registry()).economy.minigames.payout, game.payout_key)
    streak, record, reward = await record_win(user, "flashcard_streak", "longest_flashcard_streak", base)
    return Outcome(result, streak, 0, record, reward)
