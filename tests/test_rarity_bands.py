"""Rarity guard: a drop's rarity is how long an active player waits between finds of that ONE item (docs/DESIGN.md "Rarity"). Tune the two tables below; every
item with a drop table must sit inside its tier's band. Fish are out: what bites is set by the per-water odds in fishing.toml, not the item's own rate."""

import statistics

from cococap.registry import get_registry

REG = get_registry()

# Rolls of a drop table in an hour of active play, by where the item is rolled (see scripts.balance: 12 clicks a minute).
ROLLS_PER_HOUR = {"mining": 720, "foraging": 45, "farming": 400}
# Minutes of active play between finds of one item, by rarity. R1 is found nearly every action (rate 1-3 with a quantity range), and so are bulk
# materials (a material of rarity 1 or 2): the only tier-defined times are the rest. TODO(balance): the owner may tune the top two.
MINUTES_BETWEEN_FINDS = {2: 10, 3: 60, 4: 300, 5: 1500, 6: 6000, 7: 24000}
BAND = 2.0  # an item may sit within x2 of its tier's number


def where(item) -> str | None:
    mined = {i for table in REG.mining.depth_tables for i in table}
    if item.id in mined:
        return "mining"
    return item.skill if item.skill in ROLLS_PER_HOUR else None


def is_bulk(item) -> bool:
    return item.category == "material" and item.rarity <= 2 and "wedge" not in item.id


def tested():
    return [i for i in REG.items.values() if i.drop and i.stars == 1 and i.category not in ("fish", "tool") and where(i)]  # (a bomb is crafted or a prize: no real roll)


def test_every_drop_sits_in_its_rarity_band():
    for item in tested():
        rate = item.drop.rate
        if item.rarity <= 1 or is_bulk(item):
            assert rate <= 3, f"{item.id} (R{item.rarity}, common): 1 in {rate} should be 1-3 with a quantity range"
            continue
        target = ROLLS_PER_HOUR[where(item)] * MINUTES_BETWEEN_FINDS[item.rarity] / 60
        assert target / BAND <= rate <= target * BAND, f"{item.id} R{item.rarity} ({where(item)}): 1 in {rate}, band is {target / BAND:.0f}-{target * BAND:.0f}"


def test_tier_bands_do_not_overlap():
    tiers = sorted(MINUTES_BETWEEN_FINDS)
    for a, b in zip(tiers, tiers[1:], strict=False):
        assert MINUTES_BETWEEN_FINDS[b] / MINUTES_BETWEEN_FINDS[a] >= BAND * BAND, f"R{a} and R{b} bands overlap: tiers must be at least x{BAND * BAND:.0f} apart"


def test_prices_rise_with_rarity():
    medians = {}
    for r in range(1, 8):
        prices = [i.sell_price for i in REG.items.values() if i.stars == 1 and i.rarity == r and i.drop and i.sell_price and i.category not in ("tool", "fish")]  # (fish prices follow the per-water odds)
        if prices:
            medians[r] = statistics.median(prices)
    ranked = [medians[r] for r in sorted(medians)]
    assert all(a < b for a, b in zip(ranked, ranked[1:], strict=False)), medians
