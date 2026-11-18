import discord

from cococap import constants, emojis
from cococap.registry import get_registry
from cococap.services.rewards import exchange_bits
from cococap.ui import Page, PromptModal, Screen
from cococap.ui.components import bits, button, section, sep, text

from .games import currency_label, start_game
from .shop import parse_quantity


class CasinoScreen(Screen):
    id = "casino"
    label = "Casino"
    emoji = "🎰"
    description = "Gamble for glory (and the leaderboard)"
    links = ("highlow", "blackjack")

    async def build(self) -> Page:
        name = currency_label(constants.CASINO_CURRENCY)
        rate = get_registry().economy.exchange
        body = [
            *self.note_block(),
            text(
                f"**{emojis.luckbucks(self.user.luckbucks)}**  ·  **{emojis.bits(self.user.purse)}**\n"
                f"The casino stakes **{name}**. "
                "Bet a number, `2k`, a percent like `25%`, or `max`."
            ),
            sep(),
            section("### 🔼 High-Low\nGuess high or low; keep doubling or cash out.",
                    accessory=button("Play", style=discord.ButtonStyle.primary, on_click=self._ask("highlow", "High-Low"))),
            section("### 🃏 Blackjack\nBeat the dealer to 21.",
                    accessory=button("Play", style=discord.ButtonStyle.primary, on_click=self._ask("blackjack", "Blackjack"))),
            sep(),
            section(
                f"### 💱 Exchange\n{emojis.bits(rate.bits_per_luckbuck)} = {emojis.luckbucks(1)}  ·  up to {bits(rate.daily_limit)}/day",
                accessory=button("Exchange", on_click=self._ask_exchange),
            ),
        ]
        return Page("Casino", body, accent=0x2ECC71)

    async def _ask_exchange(self, interaction: discord.Interaction) -> None:
        async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
            got, spent = await exchange_bits(self.user, parse_quantity(raw))
            await self.refresh(modal_interaction, f"Exchanged {emojis.bits(spent)} for {emojis.luckbucks(got)}.")

        await interaction.response.send_modal(
            PromptModal("Exchange bits for luckbucks", "How many luckbucks?", submitted, default="10", max_length=7)
        )

    def _ask(self, game: str, title: str):
        async def ask(interaction: discord.Interaction) -> None:
            async def submitted(modal_interaction: discord.Interaction, raw: str) -> None:
                await start_game(self, modal_interaction, game, raw)

            await interaction.response.send_modal(
                PromptModal(f"{title}: place your bet", "Bet", submitted, default="100", placeholder="100, 2k, 25%, max")
            )

        return ask
