"""A page with tabs: ONE registered screen that shows one of several "panes" (small Screen classes) chosen from a dropdown.

Rule of the hub: a new feature goes into an existing page as a tab, not as a new screen. A pane is an ordinary `Screen` subclass that is NOT
registered in `screens/__init__.py`; the host builds it with the same navigator, so its handlers, `self.refresh`, notes, results, self-refresh and
"locked" behave exactly as before. The host only adds the tab dropdown on top of the pane's page (only the ACTIVE pane renders, which keeps a page
under Discord's component limit). Open a tab directly with `open_screen(interaction, "player", tab="stats")` or `nav.show(i, "player", tab="stats")`.
"""

import discord

from cococap.ui.components import select
from cococap.ui.nav import Page, Screen


class TabsScreen(Screen):
    # key -> pane class. Order is the dropdown order; the first is the default tab.
    panes: dict[str, type[Screen]] = {}
    tab_placeholder = "Choose a tab"

    def __init__(self, nav):
        super().__init__(nav)
        self._tab = next(iter(self.panes))
        self._live: dict[str, Screen] = {}

    # ---- the active pane -------------------------------------------------------------------------
    @property
    def tab(self) -> str:
        return self._tab

    @tab.setter
    def tab(self, key: str) -> None:
        if key not in self.panes:
            raise KeyError(f"unknown tab {key!r} on {self.id}")
        self._tab = key

    @property
    def pane(self) -> Screen:
        if self._tab not in self._live:
            self._live[self._tab] = self.panes[self._tab](self.nav)
        return self._live[self._tab]

    def pane_for(self, key: str) -> Screen:
        """The pane of tab `key` (created on demand), e.g. to hand it state before showing it."""
        if key not in self._live:
            self._live[key] = self.panes[key](self.nav)
        return self._live[key]

    # The navigator reads these from the screen it shows: pass them through to the active pane.
    @property
    def result(self):  # type: ignore[override]
        return self.pane.result

    @result.setter
    def result(self, value) -> None:
        if hasattr(self, "_live"):
            self.pane.result = value

    @property
    def locked(self) -> bool:
        return self.pane.locked

    @property
    def hides_nav(self) -> bool:
        return self.pane.hides_nav

    @property
    def refresh_every(self) -> float | None:  # type: ignore[override]
        return self.pane.refresh_every if hasattr(self, "_live") else None

    async def on_abandon(self) -> None:
        await self.pane.on_abandon()

    # ---- drawing ---------------------------------------------------------------------------------
    async def build(self) -> Page:
        page = await self.pane.build()
        if len(self.panes) > 1:
            options = [
                discord.SelectOption(label=cls.label, value=key, emoji=cls.emoji or None, default=key == self._tab)
                for key, cls in self.panes.items()
            ]
            menu = select(self.tab_placeholder, options, self._pick, disabled=self.pane.locked)
            page.body.insert(0, discord.ui.ActionRow(menu))
        return page

    async def _pick(self, interaction: discord.Interaction, values: list[str]) -> None:
        self.tab = values[0]
        await self.nav.refresh(interaction)
