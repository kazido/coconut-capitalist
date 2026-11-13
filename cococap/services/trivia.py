"""Trivia from the-trivia-api.com. The network call is injectable so tests never touch the internet."""

import random
from dataclasses import dataclass
from typing import Awaitable, Callable

import aiohttp

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.services.minigame import record_loss, record_win
from cococap.services.rewards import Reward
from cococap.user import User

API_URL = "https://the-trivia-api.com/v2/questions?limit=1"
TIME_LIMIT = 15
GRACE = 1.5
LETTERS = "ABCD"


class TriviaUnavailable(GameRuleError):
    pass


@dataclass(frozen=True)
class Question:
    text: str
    category: str
    difficulty: str
    correct: str
    incorrect: list[str]


Fetcher = Callable[[], Awaitable[dict]]


async def fetch_from_api() -> dict:
    timeout = aiohttp.ClientTimeout(total=6)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as http, http.get(API_URL) as response:
            response.raise_for_status()
            return (await response.json())[0]
    except (aiohttp.ClientError, TimeoutError, IndexError, ValueError) as e:
        raise TriviaUnavailable("Trivia is taking a break. Try again in a moment.") from e


def parse_question(raw: dict) -> Question:
    try:
        return Question(
            text=raw["question"]["text"],
            category=str(raw.get("category", "general")).replace("_", " ").title(),
            difficulty=raw.get("difficulty", "medium"),
            correct=raw["correctAnswer"],
            incorrect=list(raw["incorrectAnswers"])[:3],
        )
    except (KeyError, TypeError) as e:
        raise TriviaUnavailable("Trivia sent something I couldn't read. Try again.") from e


class TriviaGame:
    def __init__(self, question: Question, rng: random.Random):
        self.question = question
        self.answers = [question.correct, *question.incorrect]
        rng.shuffle(self.answers)
        self.deadline: float | None = None
        self.picked: int | None = None
        self.result: str | None = None

    def reveal(self, now: float) -> None:
        self.deadline = now + TIME_LIMIT

    def check(self, index: int, now: float) -> str:
        if self.result is None:
            self.picked = index
            if self.deadline is None or now > self.deadline + GRACE:
                self.result = "late"
            else:
                self.result = "correct" if self.answers[index] == self.question.correct else "wrong"
        return self.result


@dataclass(frozen=True)
class Outcome:
    result: str
    streak: int
    lost_streak: int
    new_record: bool
    reward: Reward | None


async def start(user: User, rng: random.Random, fetch: Fetcher | None = None) -> TriviaGame:
    question = parse_question(await (fetch or fetch_from_api)())  # looked up at call time so tests can swap it  # nothing is recorded if the question can't be fetched
    await user.inc_stat("trivia_games")
    return TriviaGame(question, rng)


async def answer(user: User, game: TriviaGame, index: int, now: float, registry: Registry | None = None) -> Outcome:
    if game.result is not None:
        raise ValueError("already answered")
    result = game.check(index, now)
    if result != "correct":
        return Outcome(result, 0, await record_loss(user, "trivia_streak"), False, None)
    payout = (registry or get_registry()).economy.minigames.payout
    base = getattr(payout, f"trivia_{game.question.difficulty}", payout.trivia_medium)
    streak, record, reward = await record_win(user, "trivia_streak", "longest_trivia_streak", base)
    await user.inc_stat("trivia_wins")
    return Outcome(result, streak, 0, record, reward)
