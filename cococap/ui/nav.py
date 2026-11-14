"""One message, many screens.

``/play`` opens a single message (a Components V2 ``LayoutView``). Every screen is a small class that
returns a ``Page`` (title + body components); the ``Navigator`` wraps it in a panel, adds the
Home / Back buttons and the "go to..." menu, and swaps the page in place. A screen never has to
think about navigation, so no screen can be a dead end.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import ClassVar

import discord
from discord import ui

from cococap.errors import CustomError, GameRuleError
from cococap.user import InsufficientFunds, User

from .components import button, row, sep, text

log = logging.getLogger(__name__)

BLURPLE = 0x5865F2
TICKER_TASK = "nav-ticker"  # the name of every panel's self-refresh task
TICK_EDIT_TIMEOUT = 2.0  # seconds a self-refresh may take to reach Discord before it is skipped


async def stop_all_tickers() -> None:
    """Cancel every panel's self-refresh and wait until each has really finished. Call this before closing the
    database: a refresh cancelled in the middle of a query would otherwise wait forever on a closed connection."""
    tasks = [t for t in asyncio.all_tasks() if t.get_name() == TICKER_TASK]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


@dataclass
class Page:
    title: str
    body: list[ui.Item]
    accent: int = BLURPLE


Handler = Callable[[discord.Interaction], Awaitable[None]]


@dataclass
class Result:
    """What happened when you won or lost something: shown on its own screen, so it is not missed at the top of the
    page you were playing on. A screen sets ``self.result = Result(...)`` and redraws; the hub does the rest."""

    title: str  # "You caught a Cod!"
    lines: list[str] = field(default_factory=list)  # markdown, one block each
    emoji: str = "🎉"
    accent: int = BLURPLE
    again: Handler | None = None  # "do it again": a handler of the screen it came from
    again_label: str = "Again"
    back: Handler | None = None  # what "Continue" does (default: back to the screen it came from)
    back_label: str = "Continue"
    live: Callable[[], tuple[list[str], bool]] | None = None  # (extra lines for now, keep redrawing?): fading numbers...
    actions: list[tuple[str, str, Handler]] = field(default_factory=list)  # extra buttons: (label, emoji, handler of the origin screen)


async def report_error(interaction: discord.Interaction, error: Exception, where: str) -> None:
    """Tell the player what went wrong: rule violations verbatim, anything else generically."""
    if isinstance(error, (GameRuleError, CustomError)):
        message = str(error) or "That didn't work."
    elif isinstance(error, InsufficientFunds):
        message = "You don't have enough bits for that."
    else:
        log.error("Error in %s", where, exc_info=error)
        message = "Something went wrong on my end. It has been logged."
    send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
    await send(message, ephemeral=True)


class Screen:
    """Base class for a screen. Subclasses set the class attributes and implement ``build``."""

    id: ClassVar[str] = ""
    label: ClassVar[str] = ""
    emoji: ClassVar[str] = ""
    description: ClassVar[str] = ""
    links: ClassVar[tuple[str, ...]] = ()  # screens this one can open (checked by a test)
    # Redraw the panel by itself every this many seconds while it is showing (for things other players change,
    # like the community tree). None = only redraw when the player clicks.
    refresh_every: float | None = None

    def __init__(self, nav: "Navigator"):
        self.nav = nav
        self.note: str | None = None  # shown once at the top of the next render
        self.result: Result | None = None  # set it to show a win/loss screen at the next redraw

    @property
    def user(self) -> User:
        return self.nav.user

    @property
    def locked(self) -> bool:
        """True while leaving would abandon something (a live game): Home/Back are disabled."""
        return False

    async def on_abandon(self) -> None:
        """Called if the hub times out while this screen is showing (settle any live game)."""

    async def build(self) -> Page:
        raise NotImplementedError

    # conveniences for handlers ---------------------------------------------------------------
    async def refresh(self, interaction: discord.Interaction, note: str | None = None) -> None:
        self.note = note
        await self.nav.refresh(interaction)

    async def go(self, interaction: discord.Interaction, screen_id: str, **state) -> None:
        await self.nav.show(interaction, screen_id, **state)

    def note_block(self) -> list[ui.Item]:
        from cococap.services import activity

        found = activity.pop_notices(self.nav.user.id)
        if found:
            self.note = "\n".join(filter(None, [self.note, *found]))
        if not self.note:
            return []
        note, self.note = self.note, None
        return [text(f"> {note}")]


class Navigator(ui.LayoutView):
    """The hub message. Holds the back-stack and swaps screens in place."""

    def __init__(self, owner: discord.abc.User, user: User, screens: dict[str, type[Screen]], *, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.owner, self.user, self.screens = owner, user, screens
        self.stack: list[str] = []
        self.screen: Screen | None = None
        self.message: discord.Message | discord.InteractionMessage | None = None
        self.client: discord.Client | None = None  # set when the hub is opened (to look other players up)
        self._names: dict[int, str] = {}
        self._lock = asyncio.Lock()  # one redraw at a time (a click and the self-refresh must not interleave)
        self._ticker: asyncio.Task | None = None

    async def name_of(self, user_id: int) -> str:
        """A player's display name, without mentioning (pinging) them."""
        if user_id == self.owner.id:
            return self.owner.display_name
        if user_id not in self._names:
            name = None
            if self.client is not None:
                try:
                    found = self.client.get_user(user_id) or await self.client.fetch_user(user_id)
                    name = found.display_name
                except discord.HTTPException:
                    pass
            self._names[user_id] = name or f"Player {str(user_id)[-4:]}"
        return self._names[user_id]

    # ---- navigation -------------------------------------------------------------------------
    async def open(self, interaction: discord.Interaction, screen_id: str, **state) -> None:
        """Send the hub as a new message, starting on `screen_id`."""
        if screen_id != "home" and "home" in self.screens:
            self.stack = ["home"]  # so Back from a shortcut lands on the home page
        self.client = interaction.client
        await self._enter(screen_id, push=True, **state)
        await interaction.response.send_message(view=self)
        self.message = await interaction.original_response()
        self._restart_ticker()

    async def _respond(self, interaction: discord.Interaction) -> None:
        """Answer a click by showing the new panel. If Discord won't take the answer any more (the click was
        acknowledged too late, so "this interaction failed"), the game state has already changed, so show the new panel
        by editing the message directly instead of leaving the player staring at a stale one."""
        try:
            await interaction.response.edit_message(view=self)
        except (discord.NotFound, discord.InteractionResponded) as error:
            log.warning("interaction response failed (%s); editing the message directly", error)
            if self.message is None:
                raise
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                raise error from None

    async def show(self, interaction: discord.Interaction, screen_id: str, *, push: bool = True, **state) -> None:
        async with self._lock:
            await self._enter(screen_id, push=push, **state)
            await self._respond(interaction)
        self._restart_ticker()

    async def refresh(self, interaction: discord.Interaction) -> None:
        async with self._lock:
            await self._render()
            await self._respond(interaction)
        self._restart_ticker()  # a screen can switch its self-refresh on or off as its state changes

    async def update(self, interaction: discord.Interaction) -> None:
        """Redraw again after the first response was used (for animations: keep it to ~1 per second)."""
        async with self._lock:
            await self._render()
            await interaction.edit_original_response(view=self)

    # ---- self-refresh -------------------------------------------------------------------------------
    async def stop_ticker(self) -> None:
        """Stop this panel's self-refresh and wait for it to finish."""
        task, self._ticker = self._ticker, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def _restart_ticker(self) -> None:
        """(Re)start the timer that redraws the current screen, if it asks for one."""
        if self._ticker is not None:
            self._ticker.cancel()
            self._ticker = None
        screen = self.screen
        if screen is not None and screen.refresh_every and self.message is not None and not self.is_finished():
            self._ticker = asyncio.create_task(self._tick(screen, screen.refresh_every), name=TICKER_TASK)

    async def _tick(self, screen: Screen, seconds: float) -> None:
        try:
            while self.screen is screen and not self.is_finished():
                await asyncio.sleep(seconds)
                if self._lock.locked():
                    continue  # the player just clicked: never make their click wait for a redraw
                async with self._lock:
                    if self.screen is not screen:
                        return
                    await self._render()
                    if self.screen is not screen:  # it turned into a result page: that has its own redraw timer
                        self._ticker = None
                        self._restart_ticker()
                        await asyncio.wait_for(self.message.edit(view=self), TICK_EDIT_TIMEOUT)
                        return
                    try:
                        # (a slow edit, e.g. waiting out a rate limit, must not hold up the next click)
                        await asyncio.wait_for(self.message.edit(view=self), TICK_EDIT_TIMEOUT)
                    except asyncio.TimeoutError:
                        log.warning("self-refresh of %s was too slow; skipping this one", screen.id)
                    if not screen.refresh_every:
                        return  # the screen no longer needs redrawing (e.g. the line is out of the water)
        except (discord.HTTPException, asyncio.CancelledError):
            pass  # the message is gone, or its 15-minute edit window closed: the next click revives the panel
        except Exception:
            log.exception("self-refresh of %s failed", screen.id)

    async def back(self, interaction: discord.Interaction) -> None:
        if len(self.stack) > 1:
            self.stack.pop()
        await self.show(interaction, self.stack[-1], push=False)

    async def _enter(self, screen_id: str, *, push: bool, **state) -> None:
        if screen_id not in self.screens:
            raise KeyError(f"unknown screen {screen_id!r}")
        self.screen = self.screens[screen_id](self)
        for key, value in state.items():  # e.g. open the leaderboard on a chosen category
            setattr(self.screen, key, value)
        if push and (not self.stack or self.stack[-1] != screen_id):
            self.stack.append(screen_id)
        await self._render()

    # ---- rendering --------------------------------------------------------------------------
    async def _render(self) -> None:
        screen = self.screen
        await self.user.refresh()  # every render shows current data
        page = await screen.build()
        if screen.result is not None:  # a win or a loss: show what happened on a page of its own first
            result, screen.result = screen.result, None
            screen = self.screen = ResultScreen(self, result, screen)
            page = await screen.build()
        self._swap_items()
        header = f"## {screen.emoji} {page.title}".strip()
        self.add_item(
            ui.Container(
                text(header),
                sep(),
                *page.body,
                sep(),
                self._controls(),
                accent_colour=discord.Colour(page.accent),
            )
        )

    def _swap_items(self) -> None:
        """Drop the old items WITHOUT detaching them from this view.

        `clear_items()` sets every old item's view to None. Until Discord applies the edit, a fast second click
        still carries the old button's id; discord.py then logs "View interaction referencing unknown view" and
        throws the click away. Keeping the old items attached lets that click run (the handlers are tolerant of
        stale clicks), and the new items replace them in the store once the edit is sent.
        """
        self._children.clear()
        self._total_children = 0

    def _controls(self) -> ui.ActionRow:
        locked = self.screen.locked
        return row(
            button("Home", emoji="🏠", on_click=self._on_home, disabled=locked or self.screen.id == "home"),
            button("Back", emoji="⬅️", on_click=self.back, disabled=locked or len(self.stack) <= 1),
        )

    async def _on_home(self, interaction: discord.Interaction) -> None:
        self.stack = ["home"]
        await self.show(interaction, "home", push=False)

    # ---- safety -----------------------------------------------------------------------------
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner.id:
            return True
        await interaction.response.send_message("This isn't your menu. Use /play to open your own.", ephemeral=True)
        return False

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item) -> None:
        await report_error(interaction, error, self.screen.id if self.screen else "?")

    async def on_timeout(self) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
        if self.screen is not None:
            try:
                await self.screen.on_abandon()
            except Exception:
                log.exception("on_abandon failed for %s", self.screen.id)
        for child in self.walk_children():
            if isinstance(child, (ui.Button, ui.Select)):
                child.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class ResultScreen(Screen):
    """A win or a loss, on a page of its own. "Again" runs the handler of the screen it came from; "Continue" returns to
    that screen. Home/Back are locked so the result is seen, not skipped."""

    id = "result"
    label = "Result"

    def __init__(self, nav: "Navigator", result: Result, origin: Screen):
        super().__init__(nav)
        self.shown = result
        self.origin = origin
        self.emoji = result.emoji
        self._ticking = False

    @property
    def refresh_every(self) -> float | None:  # type: ignore[override]
        return 1.5 if self._ticking else None

    @property
    def locked(self) -> bool:
        return True

    async def on_abandon(self) -> None:
        await self.origin.on_abandon()  # (e.g. a mine you left mid-run still gets settled)

    async def build(self) -> Page:
        r = self.shown
        lines = list(r.lines)
        if r.live is not None:
            extra, self._ticking = r.live()
            lines += extra
        body = [text(line) for line in lines]  # (the panel header already shows the title)
        buttons = [button(label, emoji=emoji, on_click=self._act(handler)) for label, emoji, handler in r.actions]
        if r.again is not None:
            buttons.append(button(r.again_label, emoji="🔁", style=discord.ButtonStyle.primary, on_click=self._again))
        buttons.append(button(r.back_label, emoji="➡️", on_click=self._back))
        body.append(row(*buttons))
        return Page(r.title, body, accent=r.accent)

    def _act(self, handler: Handler):
        async def run(interaction: discord.Interaction) -> None:
            self.nav.screen = self.origin  # an extra choice (like donating): the screen it came from carries it out
            await handler(interaction)

        return run

    async def _again(self, interaction: discord.Interaction) -> None:
        self.nav.screen = self.origin  # back on the screen it came from, then do it again from there
        await self.shown.again(interaction)

    async def _back(self, interaction: discord.Interaction) -> None:
        self.nav.screen = self.origin
        if self.shown.back is not None:
            await self.shown.back(interaction)
        else:
            await self.origin.refresh(interaction)
