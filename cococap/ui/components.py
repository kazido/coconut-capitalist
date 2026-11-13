"""Tiny helpers for building Components V2 panels, so screens read like layouts."""

from typing import Awaitable, Callable

import discord
from discord import ui

from cococap import emojis

Handler = Callable[[discord.Interaction], Awaitable[None]]


def text(markdown: str) -> ui.TextDisplay:
    return ui.TextDisplay(markdown)


def sep(*, visible: bool = True, large: bool = False) -> ui.Separator:
    spacing = discord.SeparatorSpacing.large if large else discord.SeparatorSpacing.small
    return ui.Separator(visible=visible, spacing=spacing)


def button(
    label: str | None = None,
    *,
    emoji: str | None = None,
    style: discord.ButtonStyle = discord.ButtonStyle.secondary,
    on_click: Handler | None = None,
    disabled: bool = False,
) -> ui.Button:
    b = ui.Button(label=label, emoji=emoji, style=style, disabled=disabled)
    if on_click is not None:
        b.callback = on_click  # type: ignore[method-assign]
    return b


def row(*items: ui.Item) -> ui.ActionRow:
    return ui.ActionRow(*items)


def section(*lines: str, accessory: ui.Item) -> ui.Section:
    """Up to three lines of text with a button (or thumbnail) on the right."""
    return ui.Section(*lines, accessory=accessory)


def select(
    placeholder: str,
    options: list[discord.SelectOption],
    on_select: Callable[[discord.Interaction, list[str]], Awaitable[None]],
    *,
    disabled: bool = False,
) -> ui.Select:
    menu = ui.Select(placeholder=placeholder, options=options[:25], disabled=disabled)

    async def callback(interaction: discord.Interaction) -> None:
        await on_select(interaction, list(menu.values))

    menu.callback = callback  # type: ignore[method-assign]
    return menu


def user_select(
    placeholder: str,
    on_select: Callable[[discord.Interaction, discord.abc.User], Awaitable[None]],
) -> ui.UserSelect:
    """A menu for picking one server member."""
    menu = ui.UserSelect(placeholder=placeholder, min_values=1, max_values=1)

    async def callback(interaction: discord.Interaction) -> None:
        await on_select(interaction, menu.values[0])

    menu.callback = callback  # type: ignore[method-assign]
    return menu


def bar(fraction: float, width: int = 10) -> str:
    """A text progress bar, e.g. ▰▰▰▱▱▱▱▱▱▱"""
    filled = max(0, min(width, round(fraction * width)))
    return "▰" * filled + "▱" * (width - filled)


def xp_bar(fraction: float, width: int = 10) -> str:
    """The XP bar built from the bot's own xp_bar_* emojis (falls back to the text bar if they aren't uploaded)."""
    full, empty = emojis.get("xp_bar_full"), emojis.get("xp_bar_empty")
    if not (full and empty):
        return bar(fraction, width)
    filled = max(0, min(width, int(fraction * width)))
    return emojis.get("xp_bar_left") + full * filled + empty * (width - filled) + emojis.get("xp_bar_right")


def duration(seconds: float) -> str:
    """3725 -> '1h 2m'. Under a minute shows seconds."""
    seconds = int(seconds)
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [f"{days}d" if days else "", f"{hours}h" if hours else "", f"{minutes}m" if minutes else ""]
    shown = " ".join(p for p in parts if p)
    return shown or f"{secs}s"


def bits(amount: int) -> str:
    return f"{amount:,}"
