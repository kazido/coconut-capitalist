import discord

from cococap import emojis
from cococap.ui import Page, Screen
from cococap.ui.components import button, section, sep, text



class MinigamesScreen(Screen):
    id = "minigames"
    label = "Minigames"
    emoji = emojis.icon('dice', '🎲')
    description = "The casino and other games for fun"
    links = ("casino", "flashcard", "unscramble", "sequence", "trivia")

    async def build(self) -> Page:
        body = [
            *self.note_block(),
            section(
                f"### {emojis.icon('money', '🎰')} Casino\nHigh-Low and Blackjack",
                accessory=button("Open", style=discord.ButtonStyle.primary, on_click=self._open_casino),
            ),
            sep(),
            text("**Brain games**  ·  luckbucks, up to a daily limit"),
            section(f"### {emojis.icon('scroll', '🔢')} Flashcard\nQuick sums against the clock", accessory=button("Play", on_click=self._opener("flashcard"))),
            section(f"### {emojis.icon('page', '📄')} Unscramble\nUnjumble the word", accessory=button("Play", on_click=self._opener("unscramble"))),
            section(f"### {emojis.icon('brain', '🧠')} Sequence\nRemember the growing pattern", accessory=button("Play", on_click=self._opener("sequence"))),
            section(f"### {emojis.icon('unknown', '❓')} Trivia\nAnswer random questions", accessory=button("Play", on_click=self._opener("trivia"))),
            text("-# Two-player: `/tictactoe @friend`"),
        ]
        return Page("Minigames", body, accent=0x2ECC71)

    async def _open_casino(self, interaction: discord.Interaction) -> None:
        await self.go(interaction, "casino")

    def _opener(self, screen_id: str):
        async def go(interaction: discord.Interaction) -> None:
            await self.go(interaction, screen_id)

        return go
