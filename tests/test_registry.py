import re
import shutil
from pathlib import Path

import pytest

from cococap.registry import RegistryError, UnknownItem, get_registry, load_registry
from cococap.registry.loader import CONFIG_DIR


def test_shipped_game_data_is_valid():
    reg = load_registry()  # raises RegistryError naming file/entry if anything is wrong
    assert len(reg.items) > 40 and len(reg.ranks) == 16


def test_works_from_any_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the old INI loader resolved ./game_data against the cwd
    assert load_registry().rank(1).display_name == "Peasant"


def test_item_ids_are_safe_inventory_keys():
    # '.' in an id would nest items inside each other in Mongo (items.<id>.quantity)
    assert all("." not in i and i == i.lower() for i in get_registry().items)


def test_seeds_and_crops_are_linked_both_ways():
    reg = get_registry()
    for item in reg.items.values():
        if item.crop:
            assert reg.item(item.crop.seed).seed.grows_into == item.id
        if item.seed:
            assert reg.item(item.seed.grows_into).crop.seed == item.id


def test_lookups():
    reg = get_registry()
    assert reg.item("tool_dreamnail").tool.requirement == 10
    assert reg.item("tool_shiningsilver").tool.ability_description.endswith("50% of their max health.")
    assert reg.item("key_gemstone_implosion").wiki  # recovered from the old database
    assert {i.id for i in reg.items_for_skill("mining")} >= {"material_copper_ore", "tool_scarab_bomb"}
    assert all(i.price > 0 for i in reg.shop_items())
    assert reg.find_item("nope") is None
    with pytest.raises(UnknownItem):
        reg.item("nope")


def test_ranks_chain_ends():
    reg = get_registry()
    assert reg.next_rank(0).rank_id == 1
    assert reg.next_rank(max(reg.ranks)) is None


@pytest.fixture
def data(tmp_path: Path) -> Path:
    for f in CONFIG_DIR.glob("*.toml"):
        shutil.copy(f, tmp_path / f.name)
    return tmp_path


def edit(path: Path, old: str, new: str):
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))


def test_typo_in_a_field_name_is_reported_with_file_and_entry(data):
    edit(data / "items.toml", "sell_price = 50  # TODO(balance): flattened (was 20)", "sel_price = 50  # TODO(balance): flattened (was 20)")
    with pytest.raises(RegistryError, match=r"items\.toml \[material_copper_ore\].*sel_price"):
        load_registry(data)


def test_out_of_range_rarity_rejected(data):
    edit(data / "items.toml", "rarity = 1\n", "rarity = 9\n")
    with pytest.raises(RegistryError, match="rarity"):
        load_registry(data)


def test_dotted_or_uppercase_ids_rejected(data):
    edit(data / "items.toml", "[fish_cod]\n", "[Cod.x]\n")
    with pytest.raises(RegistryError):
        load_registry(data)


def test_broken_seed_link_rejected(data):
    edit(data / "items.toml", 'grows_into = "crop_apple"', 'grows_into = "crop_lemon"')
    with pytest.raises(RegistryError, match="crop_apple"):
        load_registry(data)


def test_missing_file_and_bad_toml(data):
    (data / "pets.toml").unlink()
    with pytest.raises(RegistryError, match="missing data file"):
        load_registry(data)
    (data / "pets.toml").write_text("[dog\n")
    with pytest.raises(RegistryError, match="pets.toml"):
        load_registry(data)


def test_rank_gap_rejected(data):
    edit(data / "ranks.toml", "[3]\n", "[30]\n")
    with pytest.raises(RegistryError, match="ranks must be numbered"):
        load_registry(data)


def test_a_local_config_file_is_laid_over_the_shared_one(tmp_path, monkeypatch):
    from cococap.registry import loader

    (tmp_path / "x.toml").write_text('a = 1\n[t]\nb = 2\nc = 3\nl = [1, 2]\n')
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / "x.toml").write_text('a = 9\n[t]\nc = 30\nl = [7]\n')
    monkeypatch.delenv("COCOCAP_NO_LOCAL_CONFIG", raising=False)
    assert loader._read(tmp_path, "x") == {"a": 9, "t": {"b": 2, "c": 30, "l": [7]}}  # tables merge, lists are replaced
    monkeypatch.setenv("COCOCAP_NO_LOCAL_CONFIG", "1")
    assert loader._read(tmp_path, "x")["a"] == 1  # (tests and CI ignore it)


# ---- tree species ----------------------------------------------------------------------------------------------------------------------
def test_every_zone_has_two_or_three_species_and_their_drops_are_foraging_items():
    reg = get_registry()
    rules = reg.foraging
    assert all(2 <= len(rules.species_in(z)) <= 3 for z in range(1, rules.zones + 1))
    for sp in rules.species:
        assert sp.emoji
        for d in sp.drops:  # (none right now; any added later must be a foraging item)
            assert reg.item(d.item).skill == "foraging" and reg.item(d.item).drop is None and 0 < d.rate <= 1


def test_a_zone_without_a_species_is_rejected(data):
    # zone 1 is covered by birch and oak only: move both up so no species grows there
    edit(data / "foraging.toml", 'id = "oak"\nname = "Oak"\nemoji = "🌳"\nzone_min = 1', 'id = "oak"\nname = "Oak"\nemoji = "🌳"\nzone_min = 2')
    edit(data / "foraging.toml", 'id = "birch"\nname = "Birch"\nemoji = "🌿"\nzone_min = 1', 'id = "birch"\nname = "Birch"\nemoji = "🌿"\nzone_min = 2')
    with pytest.raises(RegistryError, match="zone"):
        load_registry(data)


def add_birch_drop(data, item, rate):
    drop = '{ item = "%s", rate = %s, min = 1, max = 2 }' % (item, rate)
    edit(data / "foraging.toml", 'id = "birch"' + chr(10), 'id = "birch"' + chr(10) + 'drops = [' + drop + ']' + chr(10))


def test_a_species_drop_of_an_unknown_item_or_a_bad_rate_is_rejected(data):
    add_birch_drop(data, "no_such_item", 0.3)
    with pytest.raises(RegistryError, match="no_such_item"):
        load_registry(data)


def test_a_species_drop_rate_must_be_a_chance(data):
    add_birch_drop(data, "material_hardwood", 1.5)
    with pytest.raises(RegistryError, match="rate"):
        load_registry(data)


# ---- starred materials ---------------------------------------------------------------------------------------------------------------------
def test_every_starrable_material_has_a_one_two_and_three_star_variant():
    reg = get_registry()
    rules = reg.economy.stars
    assert rules.starrable
    for base_id in rules.starrable:
        base = reg.item(base_id)
        assert base.stars == 0 and base.star_of is None  # the plain id is the no-star default
        for stars in (1, 2, 3):
            v = reg.item(f"{base_id}_s{stars}")
            assert v.star_of == base_id and v.stars == stars and v.category == "material" and v.skill == base.skill
            assert v.drop is None and not v.buyable  # stars are rolled by the star service, never part of a drop pool or sold in a shop
            assert v.sell_price == round(base.sell_price * rules.sell_multipliers[stars])  # index 0 is plain
            assert "★" * stars in v.name


def test_only_starrable_materials_have_variants():
    reg = get_registry()
    assert {i.star_of for i in reg.items.values() if i.star_of} == set(reg.economy.stars.starrable)


async def test_stars_are_their_own_stacks(db):
    from cococap.user import User

    user = await User.get(1)
    await user.add_item("material_gold_ore", 5)
    await user.add_item("material_gold_ore_s2", 2)
    assert await user.items() == {"material_gold_ore": 5, "material_gold_ore_s2": 2}


@pytest.mark.parametrize("ids,problem", [('"no_such_item"', "does not exist"), ('"material_hardwood", "tool_pickaxe_rookie"', "plain material"), ('"material_hardwood", "material_hardwood_s2"', "does not exist")])
def test_bad_starrable_lists_are_rejected(data, ids, problem):
    text = (data / "economy.toml").read_text()
    start = text.index("starrable = [")
    end = text.index("]", start) + 1
    (data / "economy.toml").write_text(text[:start] + f"starrable = [{ids}]" + text[end:])
    with pytest.raises(RegistryError, match=problem):
        load_registry(data)


def test_star_sell_multipliers_must_climb(data):
    mults = list(get_registry().economy.stars.sell_multipliers)
    mults[-2], mults[-1] = mults[-1], mults[-2]  # the 2- and 3-star prices swapped: no longer climbing
    text = (data / "economy.toml").read_text()
    line = re.search(r"sell_multipliers = \[[^\]]*\]", text).group(0)
    (data / "economy.toml").write_text(text.replace(line, f"sell_multipliers = {mults}", 1))
    with pytest.raises(RegistryError, match="climb"):
        load_registry(data)


def test_every_pet_has_a_valid_loadout_and_score_rules():
    from cococap.registry import get_registry

    reg = get_registry()
    assert reg.pet_score is not None and reg.pet_score.sidekick_cap > 0
    for pet in reg.pets.values():
        for eid, lvl in pet.loadout.enchants.items():
            assert 1 <= lvl <= reg.enchants[eid].max_level
