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


# ---- a smithed tool's stats come from its parts (equipment.effective_stats) -------------------------------------------

from cococap.services import enchanting  # noqa: E402
from cococap.services.equipment import effective_stats  # noqa: E402

GRADE_NAMES = [q.name for q in RULES.grades]


async def smithed_pickaxe(user: User, grade: str, traits=(None, None, None), tiers=(1, 1, 1)):
    parts = {
        slot: {"tier": tier, "trait": trait}
        for slot, tier, trait in zip(PARTS, tiers, traits, strict=True)
    }
    return await user.give_instance(
        "tool_pickaxe_rookie", parts=parts, quality=grade, smith_id=user.id
    )


async def test_smithed_tool_power_is_tool_power_and_scales_with_quality():
    user = await player()
    powers = []
    for grade in GRADE_NAMES:
        tool = await smithed_pickaxe(user, grade, tiers=(2, 4, 6))
        expected = smithing.tool_power(tool.parts, grade, RULES)
        assert effective_stats(tool, REG).power == round(expected)
        powers.append(expected)
    assert powers == sorted(powers) and len(set(powers)) == len(powers)


async def test_a_picked_trait_adds_its_amount_times_the_grade_mult_to_its_stat():
    user = await player()
    trait = RULES.traits_for("pickaxe")[0]
    for grade in GRADE_NAMES:
        idx = GRADE_NAMES.index(grade)
        tool = await smithed_pickaxe(user, grade, traits=(trait.id, None, None))
        base = await smithed_pickaxe(user, grade)
        mult = RULES.quality(grade).mult
        gained = effective_stats(tool, REG).stats.get(trait.stat, 0.0) - effective_stats(base, REG).stats.get(trait.stat, 0.0)
        assert gained == pytest.approx(trait.amounts[idx] * mult)


async def test_the_same_trait_picked_from_two_parts_stacks():
    # two parts can carry the same trait; picking it from both doubles the bonus
    trait = next(t for t in RULES.traits_for("pickaxe") if t.stat != "power")
    user = await player()
    grade = GRADE_NAMES[-1]
    both = await smithed_pickaxe(user, grade, traits=(trait.id, trait.id, None))
    one = await smithed_pickaxe(user, grade, traits=(trait.id, None, None))
    mult = RULES.quality(grade).mult
    gained = effective_stats(both, REG).stats[trait.stat] - effective_stats(one, REG).stats[trait.stat]
    assert gained == pytest.approx(trait.amounts[GRADE_NAMES.index(grade)] * mult)


async def test_an_old_tool_without_parts_keeps_its_template_stats():
    user = await player()
    tool = await user.give_instance("tool_pickaxe_rookie")
    template = REG.item("tool_pickaxe_rookie").tool
    stats = effective_stats(tool, REG)
    assert stats.power == template.power
    for stat, value in template.stats.items():
        assert stats.stats[stat] == pytest.approx(value)


async def test_enchanting_a_smithed_tool_twice_keeps_only_the_newer_enchant():
    user = await player()
    tool = await smithed_pickaxe(user, GRADE_NAMES[0])
    await user.add_item("scroll_keen", 1)
    await user.add_item("scroll_iron_frame", 1)
    await enchanting.apply_scroll(user, "scroll_keen", tool.id, REG)
    done = await enchanting.apply_scroll(user, "scroll_iron_frame", tool.id, REG)
    assert done.enchants == {"iron_frame": 1}


async def test_an_old_tool_still_keeps_both_enchants():
    user = await player()
    tool = await user.give_instance("tool_pickaxe_rookie")
    await user.add_item("scroll_keen", 1)
    await user.add_item("scroll_iron_frame", 1)
    await enchanting.apply_scroll(user, "scroll_keen", tool.id, REG)
    done = await enchanting.apply_scroll(user, "scroll_iron_frame", tool.id, REG)
    assert set(done.enchants) == {"keen", "iron_frame"}
