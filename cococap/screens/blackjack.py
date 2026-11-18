import discord

from cococap import emojis
from cococap.services import blackjack
from cococap.services.blackjack import hand_total, show
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text

from .games import ask_bet, casino_intro, money, result_buttons


def _outcomes() -> dict:
    return {
        "blackjack": (f"{emojis.icon('cards', '🃏')} BLACKJACK!", 0x9B59B6, "Easy money."),
        "win": (f"{emojis.icon('party', '🎉')} You win!", 0x2ECC71, "Nice win!"),
        "push": (f"{emojis.icon('trade', '🤝')} Push", 0x95A5A6, "Your bet is returned."),
        "lose": (f"{emojis.icon('skull', '😞')} The house wins", 0xE74C3C, "Better luck next time..."),
        "bust": (f"{emojis.icon('boom', '💥')} Bust!", 0xE74C3C, "Over 21."),
        "fold": (f"{emojis.icon('flag_white', '🏳️')} Folded", 0x95A5A6, "Half your bet is returned."),
        "forfeit": (f"{emojis.icon('timer', '⌛')} Hand abandoned", 0x95A5A6, "The bet goes to the house."),
    }


class BlackjackPane(Screen):
    label = "Blackjack"
    emoji = emojis.Lazy("ui_cards", "🃏")
    description = "Beat the dealer to 21"

    def __init__(self, nav):
        super().__init__(nav)
        self.game: blackjack.BlackjackGame | None = None
        self.bet_text = "100"

    @property
    def locked(self) -> bool:
        return self.game is not None and not self.game.finished

    async def on_abandon(self) -> None:
        if self.game is not None and not self.game.finished:
            await blackjack.abandon(self.user, self.game)

    async def build(self) -> Page:
        game = self.game
        if game is None:
            play = row(button("Play", style=discord.ButtonStyle.primary, on_click=ask_bet(self, "blackjack", "Blackjack")))
            return Page("Blackjack", [*self.note_block(), casino_intro(self.user), play], accent=0x3498DB)
        body = [
            *self.note_block(),
            text(f"**Dealer** ({hand_total(game.dealer)})\n# {show(game.dealer)}"),
            text(f"**You** ({hand_total(game.player)})\n# {show(game.player)}"),
            sep(),
            text(f"Bet **{money(game.bet)}**"),
        ]
        if not game.finished:
            actions = [
                button("Hit", emoji=emojis.icon("cards", "🃏"), style=discord.ButtonStyle.primary, on_click=self._act(blackjack.hit)),
                button("Stand", emoji=emojis.icon("fist", "✋"), style=discord.ButtonStyle.success, on_click=self._act(blackjack.stand)),
            ]
            if game.can_fold:
                actions.append(button("Fold", emoji=emojis.icon("flag_white", "🏳️"), style=discord.ButtonStyle.danger, on_click=self._act(blackjack.fold)))
            body.append(row(*actions))
            return Page("Blackjack", body, accent=0x3498DB)
        title, accent, blurb = _outcomes()[game.outcome]
        net = game.payout - game.bet
        sign = "+" if net > 0 else ""
        body += [sep(), text(f"## {title}\n{blurb}  ({sign}{net:,})"), result_buttons(self, "blackjack")]
        return Page("Blackjack", body, accent=accent)

    def _act(self, operation):
        async def act(interaction: discord.Interaction) -> None:
            await operation(self.user, self.game)
            await self.refresh(interaction)

        return act
