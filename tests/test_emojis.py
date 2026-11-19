from types import SimpleNamespace

import pytest

from cococap import emojis
from cococap.registry import get_registry


@pytest.fixture(autouse=True)
def clean():
    emojis.load([])
    yield
    emojis.load([])


class Emoji:
    def __init__(self, name, id, animated=False):
        self.name, self.id, self.animated = name, id, animated

    def __str__(self):
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"


def test_without_emojis_everything_falls_back():
    assert emojis.get("cell", "⬛") == "⬛"
    assert emojis.get("cell") == ""
    assert emojis.resolve("<a:wyrmhole:1>") == "<a:wyrmhole:1>"
    assert emojis.resolve(None) is None


def test_lookup_is_by_name_so_a_wrong_id_in_the_data_still_works():
    emojis.load([Emoji("key_gemstone_rage", 999, animated=True), Emoji("material_iron_ore", 42)])
    assert emojis.get("material_iron_ore") == "<:material_iron_ore:42>"
    assert emojis.resolve("<a:key_gemstone_rage:1>") == "<a:key_gemstone_rage:999>"
    assert emojis.resolve("hi <:material_iron_ore:7> and 🍁 and <:unknown:5>") == "hi <:material_iron_ore:42> and 🍁 and <:unknown:5>"


def test_items_use_the_bots_emojis_when_loaded():
    item = get_registry().item("key_gemstone_rage")
    assert item.emoji == item.emoji_raw  # not loaded: the data file's value
    emojis.load([Emoji("key_gemstone_rage", 999, animated=True)])
    assert item.emoji == "<a:key_gemstone_rage:999>"
    assert item.display.startswith("<a:key_gemstone_rage:999>")


def test_every_custom_token_in_the_data_names_a_known_emoji():
    names = {
        emojis._TOKEN.match(i.emoji_raw).group(1)
        for i in get_registry().items.values()
        if i.emoji_raw and emojis._TOKEN.match(i.emoji_raw)
    }
    assert names <= set(emojis.KNOWN), sorted(names - set(emojis.KNOWN))


def test_for_id_falls_back_with_nothing_loaded_and_finds_the_named_emoji():
    assert emojis.for_id("item", "material_iron_ore", "X") == "X"
    assert emojis.for_id("pet", "ember") == ""
    assert emojis.for_id("pet", "ember", None) is None
    emojis.load([Emoji("material_iron_ore", 1), Emoji("pet_ember", 2), Emoji("rank_3", 3), Emoji("ui_releaf", 4)])
    assert emojis.for_id("item", "material_iron_ore", "X") == "<:material_iron_ore:1>"
    assert emojis.for_id("pet", "ember", "X") == "<:pet_ember:2>"
    assert emojis.for_id("rank", 3, "X") == "<:rank_3:3>"
    assert emojis.ui("releaf", "X") == "<:ui_releaf:4>"
    assert emojis.for_id("pet", "other", "X") == "X"
    with pytest.raises(ValueError):
        emojis.for_id("nonsense", "a")


def test_models_use_id_named_emoji_when_loaded_and_the_config_value_otherwise():
    reg = get_registry()
    pet, species = next(iter(reg.pets.values())), reg.foraging.species[0]
    enchant, mine = next(iter(reg.enchants.values())), reg.mining.mine_types[0]
    water, rank = reg.fishing.waters[0], next(iter(reg.ranks.values()))
    things = [("pet", pet), ("species", species), ("enchant", enchant), ("mine", mine), ("water", water), ("rank", rank)]
    for _, thing in things:
        assert thing.emoji == thing.emoji_raw  # nothing loaded
    emojis.load([Emoji(emojis.name_for(k, getattr(t, "rank_id", getattr(t, "id", None))), 7) for k, t in things])
    for k, t in things:
        assert t.emoji == f"<:{emojis.name_for(k, getattr(t, 'rank_id', getattr(t, 'id', None)))}:7>"


def test_every_uploaded_emoji_is_used_somewhere():
    """Your artwork shouldn't sit unused: each known name must appear in the code or the data."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parent.parent
    source = "\n".join(
        p.read_text()
        for folder in ("cococap", "configs")
        for p in (root / folder).rglob("*")
        if p.suffix in (".py", ".toml") and p.name != "emojis.py"
    )
    unused = [n for n in emojis.KNOWN if not re.search(rf"(?<![\w]){n}(?![\w])", source)]
    assert not unused, f"emojis nobody uses: {unused}"


def test_startup_warns_about_missing_emojis(caplog):
    import asyncio

    class Bot:
        async def fetch_application_emojis(self):
            return [Emoji("cell", 1), Emoji("brand_new", 2)]

    with caplog.at_level("INFO"):
        asyncio.run(emojis.refresh(Bot()))
    assert "expects but could not find" in caplog.text and "autominer" in caplog.text
    assert "beyond the original set (found by id name): 1" in caplog.text


def test_lazy_emoji_is_read_when_used_not_when_defined():
    class Page:
        emoji = emojis.Lazy("autominer", "⚙️")

    assert Page.emoji == "⚙️" and Page().emoji == "⚙️"
    emojis.load([Emoji("autominer", 9)])
    assert Page.emoji == "<:autominer:9>"


def test_the_xp_bar_uses_the_bots_emojis_and_falls_back_to_text():
    from cococap.ui.components import xp_bar

    assert xp_bar(0.5, 4) == "▰▰▱▱"  # nothing uploaded
    emojis.load([Emoji("xp_bar_left", 1), Emoji("xp_bar_full", 2), Emoji("xp_bar_empty", 3), Emoji("xp_bar_right", 4)])
    assert xp_bar(0.5, 4) == "<:xp_bar_left:1><:xp_bar_full:2><:xp_bar_full:2><:xp_bar_empty:3><:xp_bar_empty:3><:xp_bar_right:4>"
    assert xp_bar(1.0, 2).count("xp_bar_full") == 2 and xp_bar(0.0, 2).count("xp_bar_empty") == 2


def test_image_url_gives_the_big_cdn_picture_or_none():
    assert emojis.image_url("item", "material_iron_ore") is None  # nothing uploaded: no thumbnail
    emojis.load([Emoji("fish_cod", 11), Emoji("pet_ember", 22, animated=True), Emoji("material_iron_ore", 33)])
    assert emojis.image_url("item", "fish_cod").startswith("https://cdn.discordapp.com/emojis/11.png")
    assert ".gif" in emojis.image_url("pet", "ember", size=64) and "size=64" in emojis.image_url("pet", "ember", size=64)
    assert "/33.png" in emojis.image_url("item", "material_iron_ore")


def test_location_emoji_uses_location_id_name_when_loaded():
    loc = next(iter(get_registry().locations.values()))[0]
    assert loc.emoji == loc.emoji_raw
    emojis.load([Emoji(f"location_{loc.id}", 9)])
    assert loc.emoji == f"<:location_{loc.id}:9>"
