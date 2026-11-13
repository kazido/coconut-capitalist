import discord

from cococap.services import highlow
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

from .games import money, result_buttons


class HighLowScreen(Screen):
    id = "highlow"
    label = "High-Low"
    emoji = "🔼"
    description = "Guess high or low"
    links = ("casino",)

    def __init__(self, nav):
        super().__init__(nav)
        self.game: highlow.HighLowGame | None = None  # set by the casino when the bet is placed
        self.bet_text = "100"

    @property
    def locked(self) -> bool:
        return self.game is not None and not self.game.finished

    async def on_abandon(self) -> None:
        if self.game is not None and not self.game.finished:
            await highlow.abandon(self.user, self.game)

    async def build(self) -> Page:
        game = self.game
        if game is None:
            return Page("High-Low", [text("No game in progress. Start one from the casino.")])
        body = [*self.note_block(), text("Will the next number be **high (6-10)** or **low (1-5)**?")]
        if game.last:
            verdict = "✅ Correct!" if game.last.correct else "❌ Wrong!"
            body.append(text(f"The number was **{game.last.roll}**. {verdict}"))
        body += [sep(), text(f"Bet **{money(game.bet)}**  ·  Multiplier **{game.multiplier}×**  ·  Pot **{money(game.pot)}**")]
        if not game.finished:
            body.append(
                row(
                    button("High", emoji="🔼", style=discord.ButtonStyle.primary, on_click=self._guess(True)),
                    button("Low", emoji="🔽", style=discord.ButtonStyle.primary, on_click=self._guess(False)),
                    button(f"Cash out {game.pot:,}", emoji="💰", style=discord.ButtonStyle.success, on_click=self._cash_out),
                )
            )
            return Page("High-Low", body, accent=0x666666)
        won = game.pot > 0
        body += [sep(), text(f"## {'💰 Cashed out' if won else '💀 You lost'} {money(game.pot if won else game.bet)}"), result_buttons(self, "highlow")]
        return Page("High-Low", body, accent=0x2ECC71 if won else 0xE74C3C)

    def _guess(self, high: bool):
        async def guess(interaction: discord.Interaction) -> None:
            await highlow.guess(self.user, self.game, high)
            await self.refresh(interaction)

        return guess

    async def _cash_out(self, interaction: discord.Interaction) -> None:
        await highlow.cash_out(self.user, self.game)
        await self.refresh(interaction)
