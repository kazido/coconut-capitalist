import random
import time

import discord

from cococap.services import unscramble
from cococap.ui import Page, PromptModal, Screen
from cococap.ui.components import button, row, text

from .games import reward_line, streak_line

INTRO = "Unscramble the word before the clock runs out. Longer words pay more."


class UnscrambleScreen(Screen):
    id = "unscramble"
    label = "Unscramble"
    emoji = "📄"
    description = "Unjumble the word"
    links = ("minigames",)

    def __init__(self, nav):
        super().__init__(nav)
        self.game: unscramble.UnscrambleGame | None = None
        self.outcome: unscramble.Outcome | None = None

    async def build(self) -> Page:
        game, body = self.game, [*self.note_block()]
        if game is None:
            body += [text(INTRO), row(button("Start", emoji="▶️", style=discord.ButtonStyle.primary, on_click=self._start))]
            return Page("Unscramble", body, accent=0xA0A39D)
        if self.outcome is None:
            body += [text(f"# {game.scrambled.upper()}"), text(f"{len(game.word)} letters  ·  answer <t:{int(game.deadline)}:R>"),
                     row(button("Answer", emoji="⌨️", style=discord.ButtonStyle.primary, on_click=self._ask))]
            return Page("Unscramble", body, accent=0x3498DB)
        o = self.outcome
        verdict = {"correct": "✅ Correct!", "wrong": "❌ Not it.", "late": "⌛ Too slow!"}[o.result]
        body += [text(f"## {verdict}\n{game.scrambled} → **{game.word}**"), text("\n".join(x for x in (reward_line(o.reward), streak_line(o)) if x)),
                 row(button("Next word", emoji="🔁", style=discord.ButtonStyle.primary, on_click=self._start))]
        return Page("Unscramble", body, accent=0x2ECC71 if o.result == "correct" else 0xE74C3C)

    async def _start(self, interaction: discord.Interaction) -> None:
        self.game = await unscramble.start(self.user, random.Random())
        self.game.reveal(time.time())
        self.outcome = None
        await self.refresh(interaction)

    async def _ask(self, interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, guess: str) -> None:
            if self.outcome is None:
                self.outcome = await unscramble.answer(self.user, self.game, guess, time.time())
            await self.refresh(modal_interaction)

        await interaction.response.send_modal(PromptModal("Unscramble", "Your answer", submitted, max_length=30))
