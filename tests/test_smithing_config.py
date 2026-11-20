"""configs/smithing.toml loads, and its numbers hold the rules the smithing code will rely on."""

import shutil
from pathlib import Path

import pytest

from cococap.registry import RegistryError, get_registry, load_registry
from cococap.registry.loader import CONFIG_DIR
from cococap.registry.models import PART_TIERS

KINDS = ("pickaxe", "rod", "axe", "can")


def test_smithing_config_loads_with_three_part_types():
    rules = get_registry().smithing
    assert rules is not None
    assert rules.part_types == ["base", "trim", "accent"]


def test_tier_power_increases_across_all_seven_tiers():
    rules = get_registry().smithing
    powers = [rules.tier_power(t) for t in range(1, 8)]
    assert all(b > a for a, b in zip(powers, powers[1:], strict=False))


def test_every_part_type_shares_one_power_table():
    rules = get_registry().smithing
    assert list(rules.tiers) == ["power"]  # one table, so base, trim and accent can never differ
    assert len({rules.tier_power(t) for t in range(1, PART_TIERS + 1)}) == PART_TIERS


def test_max_tier_for_area_respects_area_plus_cap():
    rules = get_registry().smithing
    for row in rules.area_weights:
        area = row.area
        assert rules.max_tier_for_area(area) == min(PART_TIERS, area + rules.area_cap)
        weights = rules.weights_for_area(area)
        cap = rules.max_tier_for_area(area)
        assert all(w == 0 for w in weights[cap:])  # weights above the cap are ignored


def test_every_tool_kind_has_at_least_three_traits():
    rules = get_registry().smithing
    for kind in KINDS:
        assert len(rules.traits_for(kind)) >= 3, kind


def test_trait_lookup_and_amounts_have_one_per_grade():
    rules = get_registry().smithing
    for trait in rules.trait_pool:
        assert rules.trait(trait.id) is trait
        assert len(trait.amounts) == len(rules.grades)


def test_quality_mults_increase_and_lookup_works():
    rules = get_registry().smithing
    mults = [q.mult for q in rules.grades]
    assert all(b > a for a, b in zip(mults, mults[1:], strict=False))
    assert rules.quality(rules.grades[-1].name).mult == mults[-1]


def test_max_traits_is_three():
    assert get_registry().smithing.max_traits == 3


def _broken_registry(tmp_path: Path, old: str, new: str) -> None:
    config = tmp_path / "configs"
    shutil.copytree(CONFIG_DIR, config)
    path = config / "smithing.toml"
    text = path.read_text(encoding="utf-8")
    assert text.count(old) == 1, old
    path.write_text(text.replace(old, new), encoding="utf-8")
    load_registry(config)


def test_non_increasing_tier_power_fails_to_load(tmp_path):
    power = get_registry().smithing.tiers["power"]
    broken = [*power[:4], power[3] - 1, *power[5:]]  # tier 5 weaker than tier 4
    with pytest.raises(RegistryError):
        _broken_registry(tmp_path, f"power = {power}", f"power = {broken}")


def test_unknown_trait_stat_fails_to_load(tmp_path):
    with pytest.raises(RegistryError):
        _broken_registry(tmp_path, 'stat = "power"', 'stat = "no_such_stat"')


def test_max_traits_other_than_three_fails_to_load(tmp_path):
    with pytest.raises(RegistryError):
        _broken_registry(tmp_path, "max_traits = 3", "max_traits = 4")


def test_unordered_quality_mults_fail_to_load(tmp_path):
    with pytest.raises(RegistryError):
        _broken_registry(tmp_path, "mult = 1.15", "mult = 0.9")
