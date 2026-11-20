"""Drop-table rolling. Every function takes the random generator so tests can fix the outcome."""

import random
from dataclasses import dataclass

from cococap.registry import DropTable, Item, Registry


def skewed_roll(rng: random.Random, low: int, high: int) -> int:
    """An integer in [low, high], skewed toward `low`."""
    return low + round((rng.random() ** 3) * (high - low))


def scale_amount(rng: random.Random, quantity: int, bonus: float) -> int:
    """`quantity` made `bonus` bigger (0.10 = +10%), the fraction rounded at random. With no bonus the dice are left alone."""
    if not bonus:
        return quantity
    more = quantity * bonus
    return quantity + int(more) + (1 if rng.random() < more - int(more) else 0)


def roll_drop(item: Item, rng: random.Random) -> int | None:
    """Roll `item`'s own drop table once: the quantity dropped, or None."""
    if item.drop is None or rng.randint(1, item.drop.rate) != 1:
        return None
    return skewed_roll(rng, item.drop.min, item.drop.max)


def roll_table(item_ids: list[str], registry: Registry, rng: random.Random) -> tuple[str, int] | None:
    """Roll items in order (rarest first); the first that drops wins. None if nothing dropped."""
    for item_id in item_ids:
        quantity = roll_drop(registry.item(item_id), rng)
        if quantity:
            return item_id, quantity
    return None


@dataclass(frozen=True)
class Loot:
    """One thing that dropped: `quantity` of an item, or `bits`."""

    item_id: str | None = None
    quantity: int = 0
    bits: int = 0


def roll_drop_table(table: DropTable, rng: random.Random) -> Loot:
    """Pick one entry of `table` by weight and roll how much of it."""
    entry = rng.choices(table.entries, weights=[e.weight for e in table.entries])[0]
    if entry.item is not None:
        return Loot(item_id=entry.item, quantity=skewed_roll(rng, entry.min, entry.max))
    return Loot(bits=rng.randint(entry.bits_min, entry.bits_max))


def roll_kill(drops: str | None, drop_chance: int, registry: Registry, rng: random.Random) -> Loot | None:
    """What one kill drops, if anything: `drop_chance` percent of the time it rolls the table `drops`."""
    if not drops or rng.random() * 100 >= drop_chance:
        return None
    return roll_drop_table(registry.drop_tables[drops], rng)
