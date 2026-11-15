"""A little fanfare when something rare drops, so a good find does not scroll by unnoticed.

Two levels, worked out from the item itself (its rarity and how rare its drop is), so new items need no extra data:

* **rare** (level 1): rarity 4+ and a drop odds of 1 in 100 or worse -- a scroll, a good wedge, a gem. A short highlighted line.
* **super rare** (level 2): rarity 5+ (or 1 in 700 or worse) -- Spirits, gemstones, aged feathers. A big banner.

Plain finds (ores you dig all day, fish -- which have their own colours -- and crops) never get one.
"""

from collections.abc import Mapping

from cococap.registry import Item, get_registry

RARE_ODDS, SUPER_ODDS = 100, 700  # a drop's 1-in-N
NO_FLAIR = {"fish", "crop"}


def level(item: Item) -> int:
    """0 = nothing special, 1 = a rare find, 2 = a super rare find."""
    if item.category in NO_FLAIR or item.rarity < 4:
        return 0
    if item.category == "scroll":  # scrolls are rare by design (see scrolls.toml): always a big moment
        return 2
    odds = item.drop.rate if item.drop else None
    if odds is not None and odds < RARE_ODDS:  # something that drops all the time is not a surprise
        return 0
    if item.rarity >= 5 or (odds is not None and odds >= SUPER_ODDS):
        return 2
    return 1


def banner(drops: Mapping[str, int]) -> str:
    """The announcement for the best find in `drops` (item id -> quantity), or "" when there is none."""
    reg = get_registry()
    found = [(level(reg.item(i)), reg.item(i), q) for i, q in drops.items() if q > 0]
    found = [f for f in found if f[0]]
    if not found:
        return ""
    found.sort(key=lambda f: (-f[0], -f[1].rarity))
    lines = []
    for lvl, item, quantity in found:
        what = f"{quantity:,} {item.display}"
        if lvl == 2:
            lines.append(f"## 🌟✨ SUPER RARE DROP! ✨🌟\n### {what}\n*{item.description}*" if item.description else f"## 🌟✨ SUPER RARE DROP! ✨🌟\n### {what}")
        else:
            lines.append(f"✨ **Rare drop!** {what}")
    return "\n".join(lines)
