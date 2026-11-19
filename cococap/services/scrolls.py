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
    """The skills whose scroll source (or, for fishing, a boss or a water) can give this scroll."""
    reg = registry or get_registry()
    found = [s for s in ("mining", "foraging", "farming") if reg.scrolls and getattr(reg.scrolls, s) is not None and item_id in getattr(reg.scrolls, s).pool]
    if reg.fishing and (any(b.scroll and b.scroll.item == item_id for b in reg.fishing.boss.bosses)
                        or any(w.scroll and w.scroll.item == item_id for w in reg.fishing.waters)):
        found.append("fishing")  # a boss's or a water's own scroll (fishing.toml `scroll = { item, odds }`)
    if "mining" not in found and reg.mining and (reg.mining.descent.second_wind_item == item_id or any(t.scroll and t.scroll.item == item_id for t in reg.mining.mine_types)):
        found.append("mining")  # a mine's own scroll (mining.toml [[mine_types]] scroll, or [descent] second_wind_item)
    tree_items = {s.scroll.item for s in (*reg.foraging.species, *reg.foraging.chopping.grains) if s.scroll} if reg.foraging else set()
    if item_id in tree_items:
        found.append("foraging")  # a species' or grain's own scroll (foraging.toml `scroll = { item, odds }`)
    return found
