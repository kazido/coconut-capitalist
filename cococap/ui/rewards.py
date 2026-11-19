"""One reward screen for every activity: the LAST screen of an action, with the next-action buttons on it.

``rewards_result`` builds the ``Result`` a screen shows after a tree, a harvest, a mine, a catch...: the same layout everywhere (what you got as item
lines, then the bits and xp line, then notes). A rare drop (``flair``: level 1 rare, level 2 super rare, scrolls always) is listed like any item and ALSO
handed to the navigator in ``Result.rare``, which sends one ephemeral popup embed (``ui/popup.py``) after the screen is shown.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence

from cococap import emojis
from cococap.constants import Rarities
from cococap.registry import Item, get_registry
from cococap.services.odds import Lookup, Odds
from cococap.ui import popup
from cococap.ui.components import bits as bits_text
from cococap.ui.nav import BLURPLE, Handler, Result

GOLD, SPECIAL = 0xF1C40F, 0x9B59B6


def item_line(item: Item, quantity: int) -> str:
    return f"{item.emoji or emojis.icon('pip', '▫️')} **+{quantity:,}** " + (f"**{item.name}**" if item.rarity >= 5 else item.name)


def items_block(drops: Mapping[str, int]) -> str:
    """The item lines of a reward: `+3 Copper Ore`, one per line (empty when there is nothing)."""
    reg = get_registry()
    return "\n".join(item_line(reg.item(i), q) for i, q in drops.items() if q > 0)


def totals_line(bits: int = 0, xp: int = 0) -> str:
    parts = ([f"{emojis.icon('sell', '💰')} **+{emojis.bits(bits)}**"] if bits else []) + ([f"{emojis.icon('sparkle', '✨')} **+{xp:,}** xp"] if xp else [])
    return "  ·  ".join(parts)


def rarity_name(item: Item) -> str:
    return Rarities.from_value(item.rarity).rarity_name


def drop_rate_line(item: Item, odds: Odds | None) -> str:
    """"Drop rate: 1 in 2,200 cells dug" when the source's table says, else just "Rarity: Legendary"."""
    rarity = f"**{rarity_name(item)}**"
    return f"{emojis.icon('dice', '🎲')} **Drop rate:** {odds.text()}  ·  {rarity}" if odds else f"{emojis.icon('dice', '🎲')} **Rarity:** {rarity}"


def rewards_result(
    title: str,
    *,
    items: Mapping[str, int] | None = None,
    bits: int = 0,
    xp: int = 0,
    headline: Iterable[str] = (),
    notes: Iterable[str] = (),
    odds: Lookup | Mapping[str, Odds] | None = None,
    emoji: str | None = None,
    accent: int = BLURPLE,
    again: Handler | None = None,
    again_label: str = "Again",
    back: Handler | None = None,
    back_label: str = "Continue",
    live: Callable[[], tuple[list[str], bool]] | None = None,
    actions: Sequence[tuple[str, str, Handler]] = (),
    again_locked: bool = False,
) -> Result:
    """The reward screen: `headline` (what happened), the item lines, the bits and xp line, then `notes`. `odds` (a function from item id to ``Odds``
    or None, or a dict) says how rare each rare drop is (shown in the popup). `again_locked` greys Again out while a timed event (the scarab) waits."""
    emoji = emoji or emojis.icon("party", "🎉")
    items = {i: q for i, q in (items or {}).items() if q > 0}
    lines = list(headline)
    if block := items_block(items):
        lines.append(f"{emojis.ui('chest', '🧰')} **You got**\n" + block)
    if totals := totals_line(bits, xp):
        lines.append(totals)
    lines += list(notes)
    if not lines:
        lines.append("Nothing this time.")
    lookup = odds.get if isinstance(odds, Mapping) else odds
    return Result(title, lines, emoji=emoji, accent=accent, live=live, again=again, again_label=again_label, back=back, back_label=back_label,
                  actions=list(actions), again_locked=again_locked, rare=popup.sorted_finds(items, lookup))
