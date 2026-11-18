import random
import time

import discord

from cococap.services import trivia
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

from .games import reward_line, streak_line
from cococap import emojis

INTRO = "Answer a random trivia question. Harder questions pay more, and you can play all day (to a daily limit)."
DIFFICULTY_ACCENT = {"easy": 0x2ECC71, "medium": 0xF1C40F, "hard": 0xE74C3C}


class TriviaPane(Screen):
    label = "Trivia"
    emoji = emojis.Lazy("ui_unknown", "❓")
    description = "Answer questions, earn luckbucks"

    def __init__(self, nav):
        super().__init__(nav)
        self.game: trivia.TriviaGame | None = None
        self.outcome: trivia.Outcome | None = None

    async def build(self) -> Page:
        game, body = self.game, [*self.note_block()]
        if game is None:
            body += [text(INTRO), row(button("Start", emoji=emojis.icon('next', '▶️'), style=discord.ButtonStyle.primary, on_click=self._start))]
            return Page("Trivia", body, accent=0xA0A39D)
        q = game.question
        lines = []
        for i, answer in enumerate(game.answers):
            mark = ""
            if self.outcome is not None:
                mark = f" {emojis.icon('check', '✅')}" if answer == q.correct else (f" {emojis.icon('cross', '❌')}" if i == game.picked else "")
            lines.append(f"**{trivia.LETTERS[i]}**  {answer}{mark}")
        body += [text(f"*{q.text}*\n-# {q.category} · {q.difficulty.title()}"), text("\n".join(lines))]
        accent = DIFFICULTY_ACCENT.get(q.difficulty, 0x3498DB)
        if self.outcome is None:
            body += [text(f"Answer <t:{int(game.deadline)}:R>"),
                     row(*(button(trivia.LETTERS[i], style=discord.ButtonStyle.primary, on_click=self._pick(i)) for i in range(len(game.answers))))]
            return Page("Trivia", body, accent=accent)
        o = self.outcome
        verdict = {"correct": f"{emojis.icon('check', '✅')} Correct!", "wrong": f"{emojis.icon('cross', '❌')} Incorrect.", "late": f"{emojis.icon('timer', '⌛')} Time's up!"}[o.result]
        body += [sep(), text(f"## {verdict}\n" + "\n".join(x for x in (reward_line(o.reward), streak_line(o)) if x)),
                 row(button("Next question", emoji=emojis.icon('again', '🔁'), style=discord.ButtonStyle.primary, on_click=self._start))]
        return Page("Trivia", body, accent=0x2ECC71 if o.result == "correct" else 0xE74C3C)

    async def _start(self, interaction: discord.Interaction) -> None:
        self.game = await trivia.start(self.user, random.Random())
        self.game.reveal(time.time())
        self.outcome = None
        await self.refresh(interaction)

    def _pick(self, index: int):
        async def pick(interaction: discord.Interaction) -> None:
            self.outcome = await trivia.answer(self.user, self.game, index, time.time())
            await self.refresh(interaction)

        return pick
