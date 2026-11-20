"""Lucky Charm (rare_luck) and Bountiful (drop_amount): generic smithing part traits that work in all four skills."""

from collections import Counter
from random import Random

import pytest

from cococap.registry import get_registry
from cococap.services import farming, fishing, foraging, mining, pets
from cococap.services.equipment import EffectiveStats
from cococap.user import User

REG = get_registry()
LUCKY, BOUNTY = REG.smithing.trait("lucky_charm"), REG.smithing.trait("bountiful")
LUCK, AMOUNT = LUCKY.amounts[-1], BOUNTY.amounts[-1]


def test_the_traits_exist_for_every_tool_kind_and_grow_with_quality():
    assert (LUCKY.stat, BOUNTY.stat) == ("rare_luck", "drop_amount")
    for trait in (LUCKY, BOUNTY):
        assert set(trait.kinds) == {"pickaxe", "rod", "axe", "can"}
        assert list(trait.amounts) == sorted(trait.amounts) and len(trait.amounts) == 4


async def _run_with(monkeypatch, **stats):
    async def fake(user, skill, reg):
        return EffectiveStats(power=3, requirement=0, stats={"power": 3.0, **stats})

    monkeypatch.setattr(mining, "equipped_stats", fake)
    return await mining.start_run(await User.get(1), Random(1), mine_type="standard")


async def test_mining_reads_both_stats(db, monkeypatch):
    base = await _run_with(monkeypatch)
    assert (await _run_with(monkeypatch, rare_luck=LUCK)).rare_reroll == pytest.approx(base.rare_reroll + LUCK)
    assert (await _run_with(monkeypatch, drop_amount=AMOUNT)).yield_factor == pytest.approx(base.yield_factor + AMOUNT)


def test_fishing_rare_luck_stat_makes_rare_fish_likelier_and_drop_amount_adds_fish():
    water = REG.fishing.waters[2]

    def rare(stats):
        es = EffectiveStats(power=3, requirement=0, stats={"power": 3.0, **stats})
        rng = Random(7)
        return sum(fishing.cast_line(es, rng, 0.0, REG, water=water).fish.rarity >= pets.RARE_FROM for _ in range(4000))

    assert rare({"rare_luck": LUCK}) > rare({})
    rules = REG.fishing
    assert sum(fishing.extra_fish(3, rules, Random(i), bonus=AMOUNT) for i in range(4000)) > 0 == sum(fishing.extra_fish(3, rules, Random(i)) for i in range(4000))


def test_foraging_drop_amount_makes_every_drop_bigger():
    plain = foraging.roll_drops(3000, Random(5), REG)
    more = foraging.roll_drops(3000, Random(5), REG, amount=AMOUNT)
    assert sum(more.values()) > sum(plain.values())
    assert sum(foraging.roll_drops(3000, Random(5), REG, amount=0.0).values()) == sum(plain.values())


def test_foraging_fox_style_reroll_finds_more_rare_drops():
    def rares(chance):
        got = foraging.roll_drops(4000, Random(3), REG, chance)
        return sum(n for i, n in got.items() if REG.item(i).rarity >= pets.RARE_FROM)

    assert rares(LUCK) > rares(0.0)


def test_farming_extras_get_rare_luck_and_bigger_amounts():
    cycles = REG.farming.drop_cycles_per_roll * 4

    def haul(**kw):
        total, rare = Counter(), 0
        for seed in range(300):
            total.update(farming.harvest_extras(Random(seed), REG, cycles, zone=1, **kw))
        rare = sum(n for i, n in total.items() if REG.item(i).rarity >= pets.RARE_FROM)
        return sum(total.values()), rare

    base_all, base_rare = haul()
    assert haul(amount=AMOUNT * 5)[0] > base_all
    assert haul(rare_luck=1.0)[0] >= base_all and haul(rare_luck=1.0)[1] >= base_rare
