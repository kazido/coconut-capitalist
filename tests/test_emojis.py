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
    emojis.load([Emoji("gemstone_rage", 999, animated=True), Emoji("ore_iron", 42)])
    assert emojis.get("ore_iron") == "<:ore_iron:42>"
    assert emojis.resolve("<a:gemstone_rage:1>") == "<a:gemstone_rage:999>"
    assert emojis.resolve("hi <:ore_iron:7> and 🍁 and <:unknown:5>") == "hi <:ore_iron:42> and 🍁 and <:unknown:5>"


def test_items_use_the_bots_emojis_when_loaded():
    item = get_registry().item("rage_gemstone")
    assert item.emoji == item.emoji_raw  # not loaded: the data file's value
    emojis.load([Emoji("gemstone_rage", 999, animated=True)])
    assert item.emoji == "<a:gemstone_rage:999>"
    assert item.display.startswith("<a:gemstone_rage:999>")


def test_every_custom_emoji_in_the_data_is_one_of_the_known_names():
    names = {
        emojis._TOKEN.match(i.emoji_raw).group(1)
        for i in get_registry().items.values()
        if i.emoji_raw and emojis._TOKEN.match(i.emoji_raw)
    }
    assert names <= set(emojis.KNOWN), sorted(names - set(emojis.KNOWN))


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
    assert "does not use yet: brand_new" in caplog.text


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
