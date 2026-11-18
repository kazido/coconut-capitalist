import discord

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import highlow
from cococap.services.rewards import exchange_bits
from cococap.ui import Page, PromptModal, Screen
from cococap.ui.components import bits, button, row, section, sep, text

from .games import ask_bet, casino_intro, money, result_buttons
from .shop import parse_quantity


class HighLowPane(Screen):
    """High-Low on the Games page. Idle, it also holds the bits -> luckbucks exchange (the casino stakes luckbucks)."""

    label = "High-Low"
    emoji = emojis.Lazy("ui_up", "🔼")
    description = "Guess high or low"

    def __init__(self, nav):
        super().__init__(nav)
        self.game: highlow.HighLowGame | None = None  # set when the bet is placed
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
            return self._idle()
        body = [*self.note_block(), text("Will the next number be **high (6-10)** or **low (1-5)**?")]
        if game.last:
            verdict = f"{emojis.icon('check', '✅')} Correct!" if game.last.correct else f"{emojis.icon('cross', '❌')} Wrong!"
            body.append(text(f"The number was **{game.last.roll}**. {verdict}"))
        body += [sep(), text(f"Bet **{money(game.bet)}**  ·  Multiplier **{game.multiplier}×**  ·  Pot **{money(game.pot)}**")]
        if not game.finished:
            body.append(
                row(
                    button("High", emoji=emojis.icon('up', '🔼'), style=discord.ButtonStyle.primary, on_click=self._guess(True)),
                    button("Low", emoji=emojis.icon('down', '🔽'), style=discord.ButtonStyle.primary, on_click=self._guess(False)),
                    button(f"Cash out {game.pot:,}", emoji=emojis.icon('sell', '💰'), style=discord.ButtonStyle.success, on_click=self._cash_out),
                )
            )
            return Page("High-Low", body, accent=0x666666)
        won = game.pot > 0
        head = f"{emojis.icon('sell', '💰')} Cashed out" if won else f"{emojis.icon('skull', '💀')} You lost"
        body += [sep(), text(f"## {head} {money(game.pot if won else game.bet)}"), result_buttons(self, "highlow")]
        return Page("High-Low", body, accent=0x2ECC71 if won else 0xE74C3C)

    def _idle(self) -> Page:
        rate = get_registry().economy.exchange
        body = [
            *self.note_block(),
            casino_intro(self.user),
            row(button("Play", style=discord.ButtonStyle.primary, on_click=ask_bet(self, "highlow", "High-Low"))),
            sep(),
            section(
                f"### {emojis.icon('money', '💱')} Exchange\n{emojis.bits(rate.bits_per_luckbuck)} = {emojis.luckbucks(1)}  ·  up to {bits(rate.daily_limit)}/day",
                accessory=button("Exchange", on_click=self._ask_exchange),
            ),
            text("-# Two-player: `/tictactoe @friend`"),
        ]
        return Page("High-Low", body, accent=0x2ECC71)

    async def _ask_exchange(self, interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            got, spent = await exchange_bits(self.user, parse_quantity(raw))
            await self.refresh(modal_interaction, f"Exchanged {emojis.bits(spent)} for {emojis.luckbucks(got)}.")

        await interaction.response.send_modal(
            PromptModal("Exchange bits for luckbucks", "How many luckbucks?", submitted, default="10", max_length=7)
        )

    def _guess(self, high: bool):
        async def guess(interaction: discord.Interaction) -> None:
            await highlow.guess(self.user, self.game, high)
            await self.refresh(interaction)

        return guess

    async def _cash_out(self, interaction: discord.Interaction) -> None:
        await highlow.cash_out(self.user, self.game)
        await self.refresh(interaction)
