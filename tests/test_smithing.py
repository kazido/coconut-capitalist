"""Smithing rules: parts, picks, smithing a tool, salvage and part swaps (services/smithing.py)."""

import random

import pytest

from cococap.errors import GameRuleError
from cococap.registry import get_registry
from cococap.registry.models import PART_TIERS
from cococap.services import smithing
from cococap.user import User

REG = get_registry()
RULES = REG.smithing
PARTS = ("base", "trim", "accent")


@pytest.fixture(autouse=True)
async def _real_db(db):
    """Every test here reads and writes the real SQLite fixture."""
    yield


async def player(level: int = 1) -> User:
    user = await User.get(1)
    if level > 1:
        await smithing.add_smithing_xp(user, User.level_to_xp(level) + 50)
    return user


async def give_part(user: User, slot: str, tier: int = 1, traits: list[str] | None = None):
    return await user.give_instance(f"part_{slot}", rolled={"tier": tier}, traits=traits or [])


def traits_fitting(kind: str) -> list[str]:
    return [t.id for t in RULES.traits_for(kind)]


def traits_not_fitting(kind: str) -> list[str]:
    return [t.id for t in RULES.trait_pool if kind not in t.kinds]


async def three_parts(user: User, tiers=(1, 1, 1), traits=(None, None, None)) -> dict[str, int]:
    ids = {}
    for slot, tier, trait in zip(PARTS, tiers, traits, strict=True):
        part = await give_part(user, slot, tier, [trait] if trait else [])
        ids[slot] = part.id
    return ids


async def smith_with(user: User, ids: dict[str, int], picks=None, kind="pickaxe", seed=0):
    return await smithing.smith(
        user, kind, ids["base"], ids["trim"], ids["accent"], picks or {}, random.Random(seed), registry=REG
    )


def test_tool_power_sums_the_three_parts_times_quality():
    parts = {"base": {"tier": 1}, "trim": {"tier": 3}, "accent": {"tier": 7}}
    for grade in RULES.grades:
        expected = (RULES.tier_power(1) + RULES.tier_power(3) + RULES.tier_power(7)) * grade.mult
        assert smithing.tool_power(parts, grade.name, RULES) == pytest.approx(expected)


async def test_smith_refuses_two_picks_from_one_part():
    user = await player(level=10)
    kind = "pickaxe"
    a, b = traits_fitting(kind)[:2]
    ids = await three_parts(user, traits=(a, None, None))
    base = await user.instance(ids["base"])
    assert base.traits == [a]  # the part really has the trait
    with pytest.raises(GameRuleError):
        await smith_with(user, ids, picks={ids["base"]: [a, b]})


async def test_smith_refuses_a_trait_that_does_not_fit_the_kind():
    user = await player(level=10)
    bad = traits_not_fitting("can")[0]
    ids = await three_parts(user, traits=(bad, None, None))
    with pytest.raises(GameRuleError):
        await smith_with(user, ids, picks={ids["base"]: bad}, kind="can")


async def test_smith_refuses_a_part_of_the_wrong_type():
    user = await player(level=10)
    ids = await three_parts(user)
    swapped = {"base": ids["trim"], "trim": ids["base"], "accent": ids["accent"]}
    with pytest.raises(GameRuleError):
        await smith_with(user, swapped)


async def test_smith_refuses_a_part_above_the_level_max_tier():
    user = await player(level=1)
    too_high = max(1, smithing.max_part_tier(1, RULES) + 1)
    if too_high > PART_TIERS:
        pytest.skip("no tier above the level-1 cap")
    ids = await three_parts(user, tiers=(too_high, 1, 1))
    with pytest.raises(GameRuleError):
        await smith_with(user, ids)


async def test_smith_consumes_parts_and_records_smith_id_parts_and_quality():
    user = await player(level=10)
    kind = "pickaxe"
    trait = traits_fitting(kind)[0]
    ids = await three_parts(user, tiers=(2, 3, 1), traits=(trait, None, None))
    tool = await smith_with(user, ids, picks={ids["base"]: trait}, kind=kind)
    # ids can be reused by SQLite after a delete, so check that no part is left, not the old ids
    assert not [i for i in await user.instances() if i.template_id.startswith("part_")]
    assert tool.smith_id == user.id
    assert tool.quality in {q.name for q in RULES.grades}
    assert tool.parts["base"] == {"tier": 2, "trait": trait}
    assert tool.parts["trim"]["tier"] == 3
    assert tool.parts["accent"]["tier"] == 1
    assert REG.item(tool.template_id).tool.kind == kind
    assert await smithing.smithing_xp(user) > 0


async def test_bonus_trait_only_when_fewer_than_max_traits_are_picked():
    kinds = traits_fitting("pickaxe")
    user = await player(level=10)
    for seed in range(40):
        full = {p: kinds[i] for i, p in enumerate(PARTS)}
        ids = await three_parts(user, traits=tuple(full[p] for p in PARTS))
        tool = await smith_with(user, ids, picks={ids[p]: full[p] for p in PARTS}, seed=seed)
        assert sum(1 for p in PARTS if tool.parts[p]["trait"]) == RULES.max_traits
        await user.delete_instance(tool.id)

    seen_bonus = False
    for seed in range(40):
        ids = await three_parts(user)
        tool = await smith_with(user, ids, picks={}, seed=seed)
        n = sum(1 for p in PARTS if tool.parts[p]["trait"])
        assert n <= 1
        seen_bonus = seen_bonus or n == 1
        await user.delete_instance(tool.id)
    assert seen_bonus  # with no picks the bonus can land on one slot


async def test_roll_part_never_exceeds_area_plus_cap():
    user = await player()
    rng = random.Random(7)
    for area in range(1, len(RULES.area_weights) + 1):
        for _ in range(25):
            part = await smithing.roll_part(user, area, rng, registry=REG)
            tier = part.rolled["tier"]
            assert 1 <= tier <= min(PART_TIERS, area + RULES.area_cap)
            assert len(part.traits) == RULES.fresh_trait_count(tier)
            assert len(set(part.traits)) == len(part.traits)
            await user.delete_instance(part.id)


async def test_salvage_keeps_only_the_picked_trait_per_part():
    user = await player()
    trait = traits_fitting("axe")[0]
    tool = await user.give_instance(
        "tool_axe_starter",
        smith_id=user.id + 1000,
        parts={"base": {"tier": 2, "trait": trait}, "trim": {"tier": 3, "trait": None}, "accent": {"tier": 1, "trait": None}},
        quality="Crude",
    )
    parts = await smithing.salvage(user, tool.id, registry=REG)
    assert [p.template_id for p in parts] == ["part_base", "part_trim", "part_accent"]
    assert [p.rolled["tier"] for p in parts] == [2, 3, 1]
    assert parts[0].traits == [trait]
    assert parts[1].traits == [] and parts[2].traits == []
    assert await user.instance(tool.id) is None


async def test_salvage_refuses_game_made_and_own_smithed_tools():
    user = await player()
    parts = {"base": {"tier": 1, "trait": None}, "trim": {"tier": 1, "trait": None}, "accent": {"tier": 1, "trait": None}}
    game = await user.give_instance("tool_axe_starter", parts=parts, quality="Crude")
    own = await user.give_instance("tool_axe_starter", smith_id=user.id, parts=parts, quality="Crude")
    with pytest.raises(GameRuleError):
        await smithing.salvage(user, game.id, registry=REG)
    with pytest.raises(GameRuleError):
        await smithing.salvage(user, own.id, registry=REG)


async def test_swap_part_is_blocked_below_the_unlock_level():
    user = await player(level=1)
    assert RULES.levels.swap_unlock_level > 1
    parts = {"base": {"tier": 1, "trait": None}, "trim": {"tier": 1, "trait": None}, "accent": {"tier": 1, "trait": None}}
    tool = await user.give_instance("tool_axe_starter", smith_id=user.id + 1000, parts=parts, quality="Crude")
    new = await give_part(user, "base", 1)
    with pytest.raises(GameRuleError):
        await smithing.swap_part(user, tool.id, "base", new.id, registry=REG)
