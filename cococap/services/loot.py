"""Drop-table rolling. Every function takes the random generator so tests can fix the outcome."""

import random

from cococap.registry import Item, Registry


def skewed_roll(rng: random.Random, low: int, high: int) -> int:
    """An integer in [low, high], skewed toward `low`."""
    return low + round((rng.random() ** 3) * (high - low))


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
