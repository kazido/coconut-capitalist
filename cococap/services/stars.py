"""Starred materials: which quality a starrable drop turns out to be. No Discord here.

A material listed in `economy.toml [stars].starrable` exists as the plain item (1 star) and as `<id>_s2` and `<id>_s3`, each its own
inventory stack. A skill's drop code calls `roll_item` for every starrable drop it hands out, passing how deep the player is as a fraction
(`progress`: 0 = the first forest / top of the mine / shallowest water, 1 = the deepest). The curve is data (`[[stars.curve]]`).
Stars are only ever dropped, never crafted up.
"""

from __future__ import annotations

import random
from collections import Counter

from cococap.registry import Registry, get_registry


def progress(step: int, steps: int) -> float:
    """How deep `step` is out of `steps` (1-based, e.g. forest 7 of 20), as 0..1. One step total is the start."""
    if steps <= 1:
        return 0.0
    return min(1.0, max(0.0, (step - 1) / (steps - 1)))


def weights(at: float, registry: Registry | None = None) -> tuple[float, float, float]:
    """The chance of 1, 2 and 3 stars at this depth (they add up to 1)."""
    curve = (registry or get_registry()).economy.stars.curve
    at = min(1.0, max(0.0, at))
    for a, b in zip(curve, curve[1:], strict=False):
        if a.progress <= at <= b.progress:
            t = (at - a.progress) / (b.progress - a.progress)
            raw = [x + (y - x) * t for x, y in zip(a.weights, b.weights, strict=True)]
            total = sum(raw)
            return raw[0] / total, raw[1] / total, raw[2] / total
    raise ValueError("star curve does not cover this progress")  # unreachable: the registry makes the curve run from 0 to 1


def roll_stars(at: float, rng: random.Random, registry: Registry | None = None) -> int:
    """1, 2 or 3."""
    return _pick(weights(at, registry), rng)


def _pick(w: tuple[float, float, float], rng: random.Random) -> int:
    x = rng.random()
    if x < w[0]:
        return 1
    return 2 if x < w[0] + w[1] else 3


def star_id(item_id: str, stars: int) -> str:
    """The inventory id of `item_id` at that many stars (the plain id for 1)."""
    return item_id if stars <= 1 else f"{item_id}_s{stars}"


def apply(drops: Counter[str], at: float, rng: random.Random, registry: Registry | None = None) -> Counter[str]:
    """Turn a drop bundle's starrable ids into their real stars. ONE roll per item stack: the whole quantity of that item gets the same star
    (decided in drop order, so the rng use is deterministic). Non-starrable ids pass through; counts merge by the final id."""
    out: Counter[str] = Counter()
    for item_id, quantity in drops.items():
        out[roll_item(item_id, at, rng, registry)] += quantity
    return out


def roll_item(item_id: str, at: float, rng: random.Random, registry: Registry | None = None) -> str:
    """The id a drop of `item_id` really is: the same id for anything that is not starrable, else it is rolled to 1, 2 or 3 stars."""
    reg = registry or get_registry()
    if item_id not in reg.economy.stars.starrable:
        return item_id
    return star_id(item_id, roll_stars(at, rng, reg))
