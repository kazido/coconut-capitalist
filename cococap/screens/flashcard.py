import random
import time

import discord

from cococap.services import flashcard
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

from .games import reward_line, streak_line

INTRO = "Solve the sum before the clock runs out. Wins pay luckbucks, and a streak pays more."


class FlashcardScreen(Screen):
    id = "flashcard"
    label = "Flashcard"
    emoji = "🔢"
    description = "Quick sums against the clock"
    links = ("minigames",)

    def __init__(self, nav):
        super().__init__(nav)
        self.game: flashcard.FlashcardGame | None = None
        self.outcome: flashcard.Outcome | None = None

    async def build(self) -> Page:
        game, body = self.game, [*self.note_block()]
        if game is None:
            body += [text(INTRO), row(button("Start", emoji="▶️", style=discord.ButtonStyle.primary, on_click=self._start))]
            return Page("Flashcard", body, accent=0xA0A39D)
        if self.outcome is None:
            body += [
                text(f"# {game.problem} = ?"),
                text(f"Answer <t:{int(game.deadline)}:R>"),
                row(*(button(str(option), on_click=self._pick(option)) for option in game.options)),
            ]
            return Page("Flashcard", body, accent=0x3498DB)
        o = self.outcome
        verdict = {"correct": "✅ Correct!", "wrong": "❌ Not quite.", "late": "⌛ Too slow!"}[o.result]
        body += [text(f"## {verdict}\n{game.problem} = **{game.answer}**"), text("\n".join(x for x in (reward_line(o.reward), streak_line(o)) if x)),
                 row(button("Next card", emoji="🔁", style=discord.ButtonStyle.primary, on_click=self._start))]
        return Page("Flashcard", body, accent=0x2ECC71 if o.result == "correct" else 0xE74C3C)

    async def _start(self, interaction: discord.Interaction) -> None:
        self.game = await flashcard.start(self.user, random.Random())
        self.game.reveal(time.time())
        self.outcome = None
        await self.refresh(interaction)

    def _pick(self, option: int):
        async def pick(interaction: discord.Interaction) -> None:
            self.outcome = await flashcard.answer(self.user, self.game, option, time.time())
            await self.refresh(interaction)

        return pick
