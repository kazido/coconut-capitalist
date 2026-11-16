"""How rare a drop really is, worked out from the loot tables (never typed in twice), so the special rare-drop screen can say "1 in 2,200".

Each source (foraging trees, a mine, a harvest, a fishing chest...) has one function that answers for an item id: an `Odds`, or None when the
source has no table that gives the item (the screen then shows the rarity name only). `for_source(name)` returns that function.
"""

from collections.abc import Callable
from dataclasses import dataclass

from cococap.registry import Registry, get_registry


@dataclass(frozen=True)
class Odds:
    """A drop chance of 1 in `one_in`, for every `per` (a cell dug, a tree felled, a chest...)."""

    one_in: float
    per: str = ""

    def text(self) -> str:
        n = max(1, round(self.one_in))
        return f"1 in {n:,}" + (f" {self.per}" if self.per else "")


Lookup = Callable[[str], Odds | None]


def _scroll(skill: str, item_id: str, reg: Registry) -> Odds | None:
    source = getattr(reg.scrolls, skill, None) if reg.scrolls else None
    if source is None or item_id not in source.pool:
        return None
    return Odds(source.odds * len(source.pool), {"mining": "cells dug", "foraging": "trees felled", "farming": "growth cycles"}[skill])  # the source fires 1 in odds, then picks one of the pool


def _own_drop(item_id: str, reg: Registry, per: str) -> Odds | None:
    item = reg.item(item_id)
    return Odds(item.drop.rate, per) if item.drop else None


def species_odds(item_id: str, reg: Registry) -> Odds | None:
    """A tree species' signature drop: 1 in (1 / rate) drop rolls of a tree of that species (the best rate if several species share it)."""
    rate = max((d.rate for sp in reg.foraging.species for d in sp.drops if d.item == item_id), default=0.0)
    return Odds(1 / rate, "drop rolls") if rate > 0 else None


def foraging(reg: Registry | None = None) -> Lookup:
    reg = reg or get_registry()

    def lookup(item_id: str) -> Odds | None:
        if found := _scroll("foraging", item_id, reg) or species_odds(item_id, reg):
            return found
        releaf = reg.foraging.releaf
        if item_id == releaf.spirit_item and releaf.double_spirit_chance > 0:
            return Odds(1 / releaf.double_spirit_chance, "double trees")
        return _own_drop(item_id, reg, "drop rolls")

    return lookup


def farming(reg: Registry | None = None) -> Lookup:
    reg = reg or get_registry()

    def lookup(item_id: str) -> Odds | None:
        return _scroll("farming", item_id, reg) or _own_drop(item_id, reg, "drop rolls")

    return lookup


def table_chance(table: list[str], item_id: str, reg: Registry) -> float:
    """The chance one roll of a rarest-first table (the first item that drops wins) gives `item_id`: 0 when it is not in the table."""
    miss = 1.0
    for other in table:
        drop = reg.item(other).drop
        chance = 1 / drop.rate if drop else 0.0
        if other == item_id:
            return miss * chance
        miss *= 1 - chance
    return 0.0


def mining(reg: Registry | None = None, depth: int | None = None) -> Lookup:
    """`depth` (the deepest row reached, 0-based) limits which depth tables count; the best of them is the one quoted."""
    reg = reg or get_registry()
    rules = reg.mining

    def lookup(item_id: str) -> Odds | None:
        if found := _scroll("mining", item_id, reg):
            return found
        tiers = rules.depth_tables if depth is None else rules.depth_tables[: min(depth // rules.descent.rows_per_tier, len(rules.depth_tables) - 1) + 1]
        best = max((table_chance(t, item_id, reg) for t in tiers), default=0.0)
        return Odds(1 / best, "cells dug") if best > 0 else None

    return lookup


def _treasure(item_id: str, loot, per: str) -> Odds | None:
    chance = max((e.chance for e in loot if e.item == item_id), default=0.0)
    return Odds(1 / chance, per) if chance > 0 else None


def fishing_chest(reg: Registry | None = None) -> Lookup:
    reg = reg or get_registry()
    return lambda item_id: _treasure(item_id, reg.fishing.treasure.loot, "chests")


def fishing_boss(reg: Registry | None = None) -> Lookup:
    reg = reg or get_registry()
    return lambda item_id: _treasure(item_id, reg.fishing.boss.loot, "boss fights")


def fishing_catch(reg: Registry | None = None) -> Lookup:
    """What washes up with a catch: an item's own drop odds, or (Salvage) a chest's loot."""
    reg = reg or get_registry()
    chest = fishing_chest(reg)
    return lambda item_id: _own_drop(item_id, reg, "catches") or chest(item_id)


def for_source(name: str, reg: Registry | None = None, **kw) -> Lookup:
    """`name` is one of foraging, farming, mining, fishing_chest, fishing_boss, fishing_catch."""
    return {"foraging": foraging, "farming": farming, "mining": mining, "fishing_chest": fishing_chest,
            "fishing_boss": fishing_boss, "fishing_catch": fishing_catch}[name](reg, **kw)
