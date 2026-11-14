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
    assert reg.item("dreamnail").tool.requirement == 10
    assert reg.item("shiningsilver").tool.ability_description.endswith("50% of their max health.")
    assert reg.item("implosion_gemstone").wiki  # recovered from the old database
    assert {i.id for i in reg.items_for_skill("mining")} >= {"copper_ore", "scarab_bomb"}
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
    edit(data / "items.toml", "sell_price = 10\n", "sel_price = 10\n")
    with pytest.raises(RegistryError, match=r"items\.toml \[copper_ore\].*sel_price"):
        load_registry(data)


def test_out_of_range_rarity_rejected(data):
    edit(data / "items.toml", "rarity = 1\n", "rarity = 9\n")
    with pytest.raises(RegistryError, match="rarity"):
        load_registry(data)


def test_dotted_or_uppercase_ids_rejected(data):
    edit(data / "items.toml", "[cod]\n", "[Cod.x]\n")
    with pytest.raises(RegistryError):
        load_registry(data)


def test_broken_seed_link_rejected(data):
    edit(data / "items.toml", 'grows_into = "apple"', 'grows_into = "lemon"')
    with pytest.raises(RegistryError, match="apple"):
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
