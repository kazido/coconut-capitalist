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


def thumb(url: str) -> ui.Thumbnail:
    return ui.Thumbnail(url)


def section_art(markdown: str, url: str | None, fallback: ui.Item | None = None):
    """Text with a big picture on the right; plain text (or `fallback` accessory) when there is no picture."""
    accessory = thumb(url) if url else fallback
    return ui.Section(markdown, accessory=accessory) if accessory else text(markdown)


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


# What each kind of bar is called and its colour (the segments are art/sources/ui_bar_<colour>_<left|mid|right>, cut from the pixel UI pack
# by art/bars_from_pack.py; the empty part is shared: ui_bar_empty_*). XP bars are separate (xp_bar below).
# hp and wear are "health" bars: their colour follows how much is left (see health_colour). progress (a goal filling up) is green; meter
# (Releaf, the reactor magnet) is always blue.
BAR_COLOURS = {"progress": "green", "meter": "blue"}
HEALTH_KINDS = ("hp", "wear")


def health_colour(fraction: float) -> str:
    """Green when full, yellow from 75% down to 25%, red below 25%."""
    return "green" if fraction > 0.75 else "yellow" if fraction >= 0.25 else "red"


def colored_bar(fraction: float, width: int, kind: str) -> str | None:
    """A bar of pixel-art segments: left end, `width` middles, right end. Filled part in the kind's colour, the rest dark. None when the
    segments are not uploaded (the caller then falls back to the plain text bar)."""
    colour = health_colour(fraction) if kind in HEALTH_KINDS else BAR_COLOURS[kind]
    names = {(c, p): emojis.ui(f"bar_{c}_{p}") for c in (colour, "empty") for p in ("left", "mid", "right")}
    if not all(names.values()):
        return None
    filled = max(0, min(width, round(fraction * width)))
    left = names[(colour if filled > 0 else "empty", "left")]
    right = names[(colour if filled == width else "empty", "right")]
    return left + names[(colour, "mid")] * filled + names[("empty", "mid")] * (width - filled) + right


def bar(fraction: float, width: int = 10, kind: str | None = None) -> str:
    """A progress bar. With a `kind` ("hp", "wear", "progress", "meter") it is the coloured pixel-art bar when those emojis are uploaded;
    otherwise (or with no kind) a text bar, e.g. ▰▰▰▱▱▱▱▱▱▱ (which the glyph swap turns into the XP bar emojis)."""
    if kind:
        pretty = colored_bar(fraction, width, kind)
        if pretty:
            return pretty
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


def needs_text(bits_needed: int, bits_have: int, items: dict[str, int], owned: dict[str, int], registry) -> str:
    """What something costs against what you have, one tick or cross each, one per line: "✅ 25,000 bits (you have 1,000,000)",
    "❌ Hardwood 4/10". Used wherever you craft or upgrade, so you can see what is missing before you try."""
    lines = []
    if bits_needed:
        lines.append(f"{emojis.icon('check', '✅') if bits_have >= bits_needed else emojis.icon('cross', '❌')} **{emojis.bits(bits_needed)}** (you have {bits(bits_have)})")
    for item_id, quantity in items.items():
        have = owned.get(item_id, 0)
        item = registry.item(item_id)
        lines.append(f"{emojis.icon('check', '✅') if have >= quantity else emojis.icon('cross', '❌')} {item.display}  **{have:,}/{quantity:,}**")
    return "\n".join(lines)
