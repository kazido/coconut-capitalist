"""Every plain unicode emoji in the code is mapped to one of our icons, and the wire swap behaves."""

import re
import tomllib
from pathlib import Path

import pytest

from cococap import emojis, glyphs

ROOT = Path(__file__).resolve().parent.parent
GLYPH_RE = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\u2B00-\u2BFF\u2190-\u21FF\u2300-\u23FF\u25A0-\u25FF\u2900-\u297F]\ufe0f?")


class E:
    def __init__(self, name, id):
        self.name, self.id = name, id

    def __str__(self):
        return f"<:{self.name}:{self.id}>"


@pytest.fixture
def loaded():
    names = {n for n in glyphs.GLYPHS.values() if not n.startswith("@")}
    emojis.load([E(f"ui_{n}", i + 100) for i, n in enumerate(sorted(names))])
    yield
    emojis.load([])


def test_every_glyph_in_the_code_has_an_icon():
    missing = {}
    for folder in ("cococap", "utils"):
        for path in (ROOT / folder).rglob("*"):
            if path.suffix in (".py", ".toml") and path.name != "glyphs.py":
                for m in GLYPH_RE.findall(path.read_text(encoding="utf8")):
                    if m.replace("\ufe0f", "") not in glyphs.GLYPHS:
                        missing.setdefault(m, path.name)
    assert not missing, f"add these to cococap/glyphs.py: {missing}"


def test_every_icon_name_has_art():
    drawn = set()
    for path in [*(ROOT / "art" / "mappings").glob("*.toml"), *(ROOT / "art" / "sprites").glob("*.toml")]:
        drawn |= set(tomllib.loads(path.read_text(encoding="utf8")))
    missing = [
        n for n in set(glyphs.GLYPHS.values())
        if not n.startswith("@") and n not in emojis.ITEM_ICONS and f"ui_{n}" not in drawn
    ]
    assert not missing, missing


def test_swap_uses_the_uploaded_icon_and_keeps_unknowns(loaded):
    assert glyphs.swap("go 🏆!") == f"go {emojis.icon('record')}!"
    assert glyphs.swap("⬅️ back") == f"{emojis.icon('prev')} back"  # the variation selector is accepted
    emojis.load([])
    assert glyphs.swap("go 🏆!") == "go 🏆!"  # not uploaded: the plain glyph stays


def test_button_label_glyph_moves_into_the_emoji_field(loaded):
    payload = {"components": [{"type": 2, "style": 2, "label": "🏆 Top", "custom_id": "x"}]}
    button = glyphs.convert(payload)["components"][0]
    assert button["label"] == "Top" and button["emoji"]["name"] == "ui_record"
    icon_only = glyphs.convert({"type": 2, "style": 2, "label": "✅", "custom_id": "y"})
    assert "label" not in icon_only and icon_only["emoji"]["name"] == "ui_check"


def test_plain_emoji_fields_and_select_text(loaded):
    out = glyphs.convert({"emoji": {"name": "🏠"}, "options": [{"label": "Mine 🏆", "value": "a", "description": "⚡ hot"}]})
    assert out["emoji"]["name"] == "ui_home"
    option = out["options"][0]
    assert option["label"] == "Mine" and option["description"] == "hot"


def test_text_and_embeds_are_swapped(loaded):
    out = glyphs.convert({"content": "👑 king", "embeds": [{"title": "🏆", "description": "x ⚡", "footer": {"text": "🔥 foot"}}]})
    assert out["content"] == f"{emojis.icon('crown')} king"
    assert emojis.icon("bolt") in out["embeds"][0]["description"]
    assert out["embeds"][0]["footer"]["text"] == "foot"


def test_a_huge_panel_keeps_plain_glyphs_instead_of_going_over_the_limit(loaded):
    text = "🏆" * 400  # 800 chars as glyphs, far more as mentions
    assert glyphs.convert({"content": text})["content"] == text


def _leftover_glyphs(payload) -> set[str]:
    """Mapped glyphs still present in the text, labels or emoji of a converted payload."""
    found: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "emoji" and isinstance(v, dict) and not v.get("id"):
                    found.add(v.get("name"))
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            found.update(m.group(0) for m in glyphs._PATTERN.finditer(o))

    walk(payload)
    return found


async def test_no_screen_shows_a_plain_emoji_once_the_icons_are_uploaded(db):
    from tests.test_hub import SCREENS, hub

    names = {n for n in glyphs.GLYPHS.values() if not n.startswith("@")}
    items = set(emojis.ITEM_ICONS.values())
    emojis.load([E(f"ui_{n}", 10**17 + i) for i, n in enumerate(sorted(names - set(emojis.ITEM_ICONS)))]
                + [E(n, 10**17 + 5000 + i) for i, n in enumerate(sorted(items))]
                + [E("xp_bar_full", 10**17 + 9000), E("xp_bar_empty", 10**17 + 9001)])
    try:
        left = {}
        for screen_id in SCREENS:
            nav, _ = await hub(screen_id)
            if found := _leftover_glyphs(glyphs.convert({"components": nav.to_components()})):
                left[screen_id] = found
    finally:
        emojis.load([])
    assert not left, left
