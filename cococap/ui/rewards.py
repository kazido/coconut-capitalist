"""One reward screen for every activity, and a page of its own for each rare drop.

``rewards_result`` builds the ``Result`` a screen shows after a tree, a harvest, a mine, a catch...: the same layout everywhere (what you got as item
lines, then the bits and xp line, then notes). A rare drop (``flair``: level 1 rare, level 2 super rare, scrolls always) is taken OUT of that list and
shown afterwards on its own page with the fanfare and how rare it is. Several rare drops are several pages, in order; the choices (Again, Back, extra
buttons) wait on the last page.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence

from cococap.constants import Rarities
from cococap.registry import Item, get_registry
from cococap.services.odds import Lookup, Odds
from cococap.ui import flair
from cococap.ui.components import bits as bits_text
from cococap.ui.nav import BLURPLE, Handler, Result

GOLD, SPECIAL = 0xF1C40F, 0x9B59B6


def item_line(item: Item, quantity: int) -> str:
    return f"{item.emoji or '▫️'} **+{quantity:,}** " + (f"**{item.name}**" if item.rarity >= 5 else item.name)


def items_block(drops: Mapping[str, int]) -> str:
    """The item lines of a reward: `+3 Copper Ore`, one per line (empty when there is nothing)."""
    reg = get_registry()
    return "\n".join(item_line(reg.item(i), q) for i, q in drops.items() if q > 0)


def totals_line(bits: int = 0, xp: int = 0) -> str:
    parts = ([f"💰 **+{bits_text(bits)}** bits"] if bits else []) + ([f"✨ **+{xp:,}** xp"] if xp else [])
    return "  ·  ".join(parts)


def rarity_name(item: Item) -> str:
    return Rarities.from_value(item.rarity).rarity_name


def drop_rate_line(item: Item, odds: Odds | None) -> str:
    """"Drop rate: 1 in 2,200 cells dug" when the source's table says, else just "Rarity: Legendary"."""
    rarity = f"**{rarity_name(item)}**"
    return f"🎲 **Drop rate:** {odds.text()}  ·  {rarity}" if odds else f"🎲 **Rarity:** {rarity}"


def rare_page(lvl: int, item: Item, quantity: int, odds: Odds | None) -> Result:
    """The special page for one rare drop."""
    super_rare = lvl == 2
    return Result("A super rare find!" if super_rare else "A rare find!", [flair.announce(lvl, item, quantity), drop_rate_line(item, odds)],
                  emoji="🌟" if super_rare else "✨", accent=GOLD if super_rare else SPECIAL)


def rewards_result(
    title: str,
    *,
    items: Mapping[str, int] | None = None,
    bits: int = 0,
    xp: int = 0,
    headline: Iterable[str] = (),
    notes: Iterable[str] = (),
    odds: Lookup | Mapping[str, Odds] | None = None,
    emoji: str = "🎉",
    accent: int = BLURPLE,
    again: Handler | None = None,
    again_label: str = "Again",
    back: Handler | None = None,
    back_label: str = "Continue",
    live: Callable[[], tuple[list[str], bool]] | None = None,
    actions: Sequence[tuple[str, str, Handler]] = (),
) -> Result:
    """The reward screen: `headline` (what happened), the item lines, the bits and xp line, then `notes`. `odds` (a function from item id to ``Odds``
    or None, or a dict) says how rare each rare drop is. The Again / back / actions choices belong to the end of the flow: with rare drops they sit on the
    last rare page, not on this one."""
    items = {i: q for i, q in (items or {}).items() if q > 0}
    rare = flair.finds(items)
    plain = {i: q for i, q in items.items() if i not in {f[1].id for f in rare}}
    lines = list(headline)
    if block := items_block(plain):
        lines.append("🎁 **You got**\n" + block)
    if totals := totals_line(bits, xp):
        lines.append(totals)
    lines += list(notes)
    if not lines and not rare:
        lines.append("Nothing this time.")
    lookup = odds.get if isinstance(odds, Mapping) else odds
    pages = [rare_page(lvl, item, quantity, lookup(item.id) if lookup else None) for lvl, item, quantity in rare]
    ending = dict(again=again, again_label=again_label, back=back, back_label=back_label, actions=list(actions))
    if pages:
        pages[-1] = Result(**{**pages[-1].__dict__, **ending})
        lines = lines or ["🎁 Something special turned up…"]
        return Result(title, lines, emoji=emoji, accent=accent, live=live, then=pages)
    return Result(title, lines, emoji=emoji, accent=accent, live=live, **ending)
