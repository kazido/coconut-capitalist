"""The News page (More -> News): every notice ever sent (Messages), the latest changes (Changelog) and everything older (Older changes), as tabs, newest first and paged.

The text is data: configs/notices.toml and configs/changelog.toml (services/news.py packs it onto pages)."""

from cococap import emojis
from cococap.services import news
from cococap.ui import Page, Screen
from cococap.ui.components import button, row, sep, text
from cococap.ui.tabs import TabsScreen


class _PagedPane(Screen):
    """A tab that shows pages of text with ◀ n/N ▶ under them."""

    title = ""
    empty = "Nothing here yet."

    def __init__(self, nav):
        super().__init__(nav)
        self.page = 0

    def pages(self) -> list[list[str]]:
        raise NotImplementedError

    async def build(self) -> Page:
        pages = self.pages()
        self.page = max(0, min(self.page, len(pages) - 1))
        blocks = pages[self.page]
        body = [*self.note_block()]
        for n, block in enumerate(blocks or [self.empty]):
            if n:
                body.append(sep())
            body.append(text(block))
        if len(pages) > 1:
            body.append(row(
                button(emoji=emojis.icon('prev', '◀️'), disabled=self.page == 0, on_click=self._turn(-1)),
                button(f"{self.page + 1}/{len(pages)}", disabled=True),
                button(emoji=emojis.icon('next', '▶️'), disabled=self.page >= len(pages) - 1, on_click=self._turn(1)),
            ))
        return Page(self.title, body, accent=0xE6B34A)

    def _turn(self, step: int):
        async def turn(interaction) -> None:
            self.page += step
            await self.refresh(interaction)

        return turn


class MessagesPane(_PagedPane):
    label = "Messages"
    emoji = emojis.Lazy("ui_quest", "📜")
    description = "Every message the bot has sent, newest first"
    title = "Messages"
    empty = "No messages yet."

    def pages(self) -> list[list[str]]:
        return news.message_pages()


class ChangelogPane(_PagedPane):
    label = "Changelog"
    emoji = emojis.Lazy("ui_milestone", "📜")
    description = "What changed lately, newest first"
    title = "Changelog"
    empty = "Nothing has changed yet."

    def pages(self) -> list[list[str]]:
        return news.changelog_pages()


class OlderChangesPane(_PagedPane):
    label = "Older changes"
    emoji = emojis.Lazy("ui_milestone", "📜")
    description = "Changes before the latest few, newest first"
    title = "Older changes"
    empty = "No older changes yet."

    def pages(self) -> list[list[str]]:
        return news.older_changelog_pages()


class NewsScreen(TabsScreen):
    id = "news"
    label = "News"
    emoji = emojis.Lazy("ui_quest", "📜")
    description = "Messages from the bot and the changelog"
    panes = {"messages": MessagesPane, "changelog": ChangelogPane, "older": OlderChangesPane}
