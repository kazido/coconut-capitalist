import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from cococap.registry import Registry, RegistryError, get_registry, load_registry
from cococap.registry.loader import CONFIG_DIR
from cococap.registry.models import LOCATIONS_PER_AREA
from cococap.services import areas, community
from cococap.services.areas import AreaError
from cococap.user import User

REG = get_registry()
RULES = REG.areas
SKILLS = ("mining", "fishing", "foraging", "farming")


async def level_all(user, level):
    xp = User.level_to_xp(level + 1)  # (level_to_xp(n) is just short of level n)
    for skill in SKILLS:
        await user.update_skill(skill, lambda s: setattr(s, "xp", xp))


# ---- the data ----------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("skill", SKILLS)
def test_every_skill_has_two_locations_per_area_with_unique_ids(skill):
    locs = REG.locations[skill]
    assert len(locs) == LOCATIONS_PER_AREA * len(RULES.areas)
    assert len({loc.id for loc in locs}) == len(locs)


def test_every_location_is_numbered_in_unlock_order():
    for skill in SKILLS:
        assert [loc.n for loc in REG.locations[skill]] == list(range(1, len(REG.locations[skill]) + 1))


@pytest.mark.parametrize("skill", SKILLS)
def test_each_location_sits_in_its_area_and_opens_at_its_scheduled_level(skill):
    for index, loc in enumerate(REG.locations[skill]):
        assert loc.skill == skill
        assert loc.area == RULES.areas[(loc.n - 1) // LOCATIONS_PER_AREA].id
        assert loc.min_level == RULES.location_levels[loc.n - 1]
        assert loc.n == index + 1


def test_fishing_starts_with_the_ids_saved_in_player_state():
    assert [loc.id for loc in REG.locations["fishing"][:4]] == ["pond", "river", "reef", "deep_sea"]


# ---- lookup ------------------------------------------------------------------------------------------------------------------------------
def test_location_returns_the_named_location_by_id():
    for skill in SKILLS:
        for loc in REG.locations[skill]:
            found = areas.location(skill, loc.id)
            assert (found.skill, found.id, found.n) == (skill, loc.id, loc.n)


def test_an_unknown_location_id_raises_area_error():
    with pytest.raises(AreaError, match="no such"):
        areas.location("mining", "atlantis")
    with pytest.raises(AreaError, match="no such"):
        areas.location("mining", REG.locations["fishing"][0].id)  # a fishing id is not a mining one


# ---- what the player can use -------------------------------------------------------------------------------------------------------------
async def test_a_new_player_can_use_only_the_first_location(db):
    user = await User.get(1)
    for skill in SKILLS:
        opened = await areas.open_location_list(user, skill)
        assert [loc.id for loc in opened] == [REG.locations[skill][0].id]


async def test_high_skill_xp_is_still_capped_by_the_first_area(db):
    user = await User.get(1)
    await level_all(user, 50)
    for skill in SKILLS:
        opened = await areas.open_location_list(user, skill)
        assert len(opened) == LOCATIONS_PER_AREA
        assert [loc.id for loc in opened] == [loc.id for loc in REG.locations[skill][:LOCATIONS_PER_AREA]]


async def test_the_list_is_always_as_long_as_open_locations(db):
    user = await User.get(1)
    for level in (1, 8, 50):
        await level_all(user, level)
        for skill in SKILLS:
            assert len(await areas.open_location_list(user, skill)) == await areas.open_locations(user, skill)
    await community.update(f"ship:{user.id}", {}, lambda d: d.update(
        tier=len(RULES.ship_tiers), current=len(RULES.areas) - 1, highest=len(RULES.areas) - 1))
    for skill in SKILLS:
        opened = await areas.open_location_list(user, skill)
        assert len(opened) == await areas.open_locations(user, skill) == len(REG.locations[skill])


async def test_at_the_last_area_and_max_level_every_location_is_listed(db):
    user = await User.get(1)
    await community.update(f"ship:{user.id}", {}, lambda d: d.update(
        tier=len(RULES.ship_tiers), current=len(RULES.areas) - 1, highest=len(RULES.areas) - 1))
    await level_all(user, 50)
    for skill in SKILLS:
        assert [loc.id for loc in await areas.open_location_list(user, skill)] == [loc.id for loc in REG.locations[skill]]


# ---- registry validation -----------------------------------------------------------------------------------------------------------------
@pytest.fixture
def data(tmp_path: Path) -> Path:
    for f in CONFIG_DIR.glob("*.toml"):
        shutil.copy(f, tmp_path / f.name)
    return tmp_path


def write_locations(path: Path, table: dict[str, list[tuple[str, str, str]]]):
    """Write locations.toml from (id, name, emoji) rows, in order. Tables are keyed by id, so a file cannot hold a duplicate id."""
    text = "".join(
        f"[{skill}.{loc_id}]\nname = {json.dumps(name, ensure_ascii=False)}\nemoji = {json.dumps(emoji, ensure_ascii=False)}\n\n"
        for skill, rows in table.items() for loc_id, name, emoji in rows
    )
    path.write_text(text, encoding="utf-8")


def shipped_table() -> dict[str, list[tuple[str, str, str]]]:
    return {skill: [(loc.id, loc.name, loc.emoji) for loc in REG.locations[skill]] for skill in SKILLS}


def test_a_skill_with_too_few_locations_is_rejected(data):
    table = shipped_table()
    table["farming"] = table["farming"][:-1]
    write_locations(data / "locations.toml", table)
    with pytest.raises(RegistryError, match="farming"):
        load_registry(data)


def test_a_missing_skill_is_rejected(data):
    table = shipped_table()
    del table["foraging"]
    write_locations(data / "locations.toml", table)
    with pytest.raises(RegistryError, match="foraging"):
        load_registry(data)


def test_fishing_with_different_first_ids_is_rejected(data):
    table = shipped_table()
    table["fishing"][0] = ("lake", *table["fishing"][0][1:])  # pond renamed: saved player state would break
    write_locations(data / "locations.toml", table)
    with pytest.raises(RegistryError, match="fishing"):
        load_registry(data)


def test_the_validator_reports_duplicate_ids_within_a_skill():
    # A TOML table cannot hold two ids with the same key, so the duplicate check is exercised on the built rows directly.
    locs = list(REG.locations["mining"])
    dup = locs[:-1] + [locs[0].model_copy(update={"n": len(locs)})]
    fake = SimpleNamespace(farming=REG.farming, items=REG.items, locations={**{s: REG.locations[s] for s in SKILLS if s != "mining"}, "mining": dup})
    problems = Registry._validate_locations(fake, RULES)
    assert any("mining" in p and "duplicate" in p for p in problems)
