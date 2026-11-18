import discord

from cococap import emojis
from cococap.exts.economy.top import TopCategories, leaderboard_view
from cococap.ui import Page, Screen
from cococap.ui.components import row, select, sep, text


class TopScreen(Screen):
    id = "top"
    label = "Leaderboards"
    emoji = emojis.Lazy("ui_record", "🏆")
    description = "See who's on top"

    def __init__(self, nav):
        super().__init__(nav)
        self.category = TopCategories.BITS

    async def build(self) -> Page:
        board, circulation, house = await leaderboard_view(self.category, self.user.id)
        options = [
            discord.SelectOption(label=c.display_name, value=c.value, emoji=c.emoji, default=c is self.category)
            for c in TopCategories
        ]
        body = [
            *self.note_block(),
            row(select("Pick a leaderboard...", options, self._pick)),
            sep(),
            text(board),
        ]
        if circulation or house:
            body += [sep(), text("\n".join(filter(None, (circulation, f"-# {house}" if house else None))))]
        return Page(f"{self.category.display_name} Leaderboard", body, accent=int(self.category.color, 16))

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.category = TopCategories.from_name(values[0])
        await self.refresh(interaction)
