"""Where scrolls come from. Each skill hands them out at one steady, rare chance (``configs/scrolls.toml``), then picks one of its six at random: three that
only fit its own tool and three that fit every tool. (Fishing's scrolls come from treasure chests and boss loot instead.)"""

import random

from cococap.registry import Registry, get_registry


def roll(skill: str, rng: random.Random, registry: Registry | None = None, rolls: int = 1) -> str | None:
    """Roll `rolls` times for a scroll of `skill`: the item id of the first one that drops, or None."""
    reg = registry or get_registry()
    source = getattr(reg.scrolls, skill, None) if reg.scrolls else None
    if source is None:
        return None
    for _ in range(max(0, rolls)):
        if rng.randint(1, source.odds) == 1:
            return rng.choice(source.pool)
    return None


def scroll_skills(item_id: str, registry: Registry | None = None) -> list[str]:
    """The skills whose scroll source (or, for fishing, chest and boss loot) can give this scroll."""
    reg = registry or get_registry()
    found = [s for s in ("mining", "foraging", "farming") if reg.scrolls and getattr(reg.scrolls, s) is not None and item_id in getattr(reg.scrolls, s).pool]
    if reg.fishing and any(entry.item == item_id for entry in (*reg.fishing.treasure.loot, *reg.fishing.boss.loot)):
        found.append("fishing")
    if "mining" not in found and reg.mining and any(t.scroll and t.scroll.item == item_id for t in reg.mining.mine_types):
        found.append("mining")  # a mine type's own scroll (mining.toml [[mine_types]] scroll)
    return found
