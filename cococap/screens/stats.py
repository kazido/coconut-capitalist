import discord

from cococap.services.stats import StatPage, stat_pages
from cococap.ui import Page, Screen
from cococap.ui.components import row, select, sep, text
from cococap import emojis


class StatsScreen(Screen):
    id = "stats"
    label = "Stats"
    emoji = emojis.Lazy("ui_milestone", "📊")
    description = "Number go up, man happy"

    def __init__(self, nav):
        super().__init__(nav)
        self.key = "general"

    async def build(self) -> Page:
        pages: list[StatPage] = await stat_pages(self.user)
        current = next(p for p in pages if p.key == self.key)
        options = [
            discord.SelectOption(label=p.title, value=p.key, emoji=p.emoji, default=p.key == self.key)
            for p in pages
        ]
        body = [*self.note_block(), row(select("Pick a page...", options, self._pick)), sep()]
        for group, rows in current.groups:
            body.append(text(f"**{group}**\n" + "\n".join(
                f"{label}: `{value:,}`" if isinstance(value, int) else f"{label}: {value}"
                for label, value in rows
            )))
        return Page(f"{current.title} Stats", body, accent=discord.Colour.dark_purple().value)

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.key = values[0]
        await self.refresh(interaction)
