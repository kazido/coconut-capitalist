import asyncio
import random

import discord

from cococap.services import sequence
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

from .games import reward_line

SHOW_SECONDS = 1.1  # one frame per element; Discord allows roughly 5 edits per 5 seconds
BLANK = "⬛"


class SequenceScreen(Screen):
    id = "sequence"
    label = "Sequence"
    emoji = "🧠"
    description = "Remember the pattern; it grows every round"
    links = ("minigames",)

    def __init__(self, nav):
        super().__init__(nav)
        self.game: sequence.SequenceGame | None = None
        self.phase = "choose"  # choose -> showing -> recall -> over
        self.frame = BLANK
        self.reward = None
        self.pause = SHOW_SECONDS  # tests set this to 0

    @property
    def locked(self) -> bool:
        return self.phase in ("showing", "recall")

    async def on_abandon(self) -> None:
        if self.game is not None and self.locked:
            self.game.over = True
            await sequence.finish(self.user, self.game)

    async def build(self) -> Page:
        game, body = self.game, [*self.note_block()]
        if self.phase == "choose":
            body += [text("Watch the pattern, then repeat it. It grows by one each round. Harder levels pay more per element."),
                     row(*(button(d.title(), style=discord.ButtonStyle.primary, on_click=self._begin(d)) for d in sequence.DIFFICULTIES))]
            return Page("Sequence", body, accent=0xA0A39D)
        body.append(text(f"Round **{game.score + 1}**  ·  score **{game.score}**"))
        if self.phase == "showing":
            body += [text(f"# {self.frame * 6}"), text("Remember this...")]
            return Page("Sequence", body, accent=0x3498DB)
        if self.phase == "recall":
            progress = " ".join(game.pattern[: game.index]) or "—"
            body += [text(f"Repeat the pattern ({game.index + 1}/{len(game.pattern)})\n{progress}"),
                     *self._option_rows()]
            return Page("Sequence", body, accent=0x3498DB)
        body += [sep(), text(f"## 💥 Game over\nYou remembered **{game.score}** round(s). The pattern was:\n{' '.join(game.pattern)}"),
                 text(reward_line(self.reward) or "Nothing earned this time."),
                 row(button("Play again", emoji="🔁", style=discord.ButtonStyle.primary, on_click=self._reset))]
        return Page("Sequence", body, accent=0xE74C3C)

    def _option_rows(self):
        buttons = [button(emoji=o, on_click=self._guess(o)) for o in self.game.options]
        return [row(*buttons[i : i + 4]) for i in range(0, len(buttons), 4)]

    def _begin(self, difficulty: str):
        async def begin(interaction: discord.Interaction) -> None:
            self.game = await sequence.start(self.user, difficulty, random.Random())
            self.reward = None
            await self._show(interaction, first=True)

        return begin

    async def _show(self, interaction: discord.Interaction, first: bool = False) -> None:
        """Flash the pattern one element at a time, then hand over to the player."""
        self.phase, self.frame = "showing", BLANK
        if first:
            await self.refresh(interaction)
        else:
            await self.nav.update(interaction)
        previous = None
        for element in self.game.pattern:
            if element == previous:  # a blank frame so repeated elements are visibly separate
                self.frame = BLANK
                await asyncio.sleep(self.pause)
                await self.nav.update(interaction)
            self.frame = element
            await self.nav.update(interaction)
            await asyncio.sleep(self.pause)
            previous = element
        self.phase = "recall"
        await self.nav.update(interaction)

    def _guess(self, option: str):
        async def guess(interaction: discord.Interaction) -> None:
            result = self.game.guess(option)
            if result == "wrong":
                self.phase = "over"
                self.reward = await sequence.finish(self.user, self.game)
                await self.refresh(interaction)
            elif result == "round":
                await self.refresh(interaction, "✅ Pattern remembered! Here comes the next round...")
                await asyncio.sleep(self.pause)
                await self._show_next(interaction)
            else:
                await self.refresh(interaction)

        return guess

    async def _show_next(self, interaction: discord.Interaction) -> None:
        await self._show(interaction)

    async def _reset(self, interaction: discord.Interaction) -> None:
        self.game, self.phase, self.reward = None, "choose", None
        await self.refresh(interaction)
