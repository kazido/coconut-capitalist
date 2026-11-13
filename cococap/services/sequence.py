"""Sequence: watch the pattern, repeat it, and it grows by one each round until you slip."""

import random

from cococap.registry import Registry, get_registry
from cococap.services.rewards import Reward, pay_minigame
from cococap.user import User

DIFFICULTIES = {
    "easy": ["😂", "😍"],
    "medium": ["🟥", "🟦", "🟧", "🟩"],
    "hard": ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"],
}


class SequenceGame:
    def __init__(self, difficulty: str, rng: random.Random):
        self.difficulty = difficulty
        self.options = DIFFICULTIES[difficulty]
        self.rng = rng
        self.pattern = [rng.choice(self.options)]
        self.index = 0  # how far through the pattern the player has got this round
        self.score = 0  # rounds fully remembered
        self.over = False
        self.settled = False

    def guess(self, option: str) -> str:
        """Pure rule. Returns "ok" (keep going), "round" (round complete, pattern grew) or "wrong"."""
        if self.over:
            raise ValueError("game over")
        if option != self.pattern[self.index]:
            self.over = True
            return "wrong"
        self.index += 1
        if self.index == len(self.pattern):
            self.score += 1
            self.index = 0
            self.pattern.append(self.rng.choice(self.options))
            return "round"
        return "ok"


async def start(user: User, difficulty: str, rng: random.Random) -> SequenceGame:
    await user.inc_stat("sequence_games")
    return SequenceGame(difficulty, rng)


async def finish(user: User, game: SequenceGame, registry: Registry | None = None) -> Reward | None:
    """Pay out when the game ends. Idempotent. Pays per element remembered (capped daily)."""
    if game.settled:
        return None
    game.settled = True
    if game.score > await user.get_stat("longest_sq_streak"):
        await user.set_stat("longest_sq_streak", game.score)
    if game.score == 0:
        return None
    rules = (registry or get_registry()).economy.minigames
    per_element = rules.payout.sequence_per_element * getattr(rules.sequence_difficulty, game.difficulty)
    return await pay_minigame(user, game.score * per_element, streak=1)
