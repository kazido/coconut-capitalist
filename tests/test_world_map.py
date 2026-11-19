"""The Travel page's world map: rendered per player; areas past the one ahead show only a ?; X where you are."""
import io
import json

import pytest
from PIL import Image

from cococap import map_runtime
from cococap.map_runtime import render_map
from tests.test_hub import hub

DATA = json.loads((map_runtime._ASSETS / "world_map.json").read_text(encoding="utf-8"))
W, H = DATA["size"]
SITES = [tuple(s) for s in DATA["sites"]]
UNIT = DATA.get("unit", 1)  # map pixels per drawing pixel
INK = (0x4B, 0x31, 0x20, 255)
RED = (0xE8, 0x28, 0x1C, 255)
SCALE = 2


def _image(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGBA")


def test_render_is_a_png_at_scaled_size():
    png = render_map(0, 0, scale=SCALE, cache_dir=None)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _image(png).size == (W * SCALE, H * SCALE)


def test_default_scale_is_the_display_scale():
    assert _image(render_map(0, 0, cache_dir=None)).size == (W * SCALE, H * SCALE)


def test_x_marks_the_current_area():
    im = _image(render_map(3, 3, scale=SCALE, cache_dir=None))
    sx, sy = SITES[3]
    near = [im.getpixel((x, y)) for x in range((sx - 12 * UNIT) * SCALE, (sx + 12 * UNIT) * SCALE)
            for y in range((sy - 16 * UNIT) * SCALE, (sy + 4 * UNIT) * SCALE)
            if 0 <= x < im.width and 0 <= y < im.height]
    assert RED in near


BASE = Image.open(map_runtime._ASSETS / "world_map.png").convert("RGBA")


def _shown(im, layer, scale):
    """(pixels of a landmark layer that show in the render, pixels it would change on the bare map)."""
    changes = [(x, y) for y in range(layer.height) for x in range(layer.width)
               if layer.getpixel((x, y))[3] and BASE.getpixel((x, y)) != layer.getpixel((x, y))]
    return sum(1 for x, y in changes if im.getpixel((x * scale, y * scale)) == layer.getpixel((x, y))), len(changes)


def test_areas_past_the_one_ahead_show_only_a_question_mark():
    # highest = 1: areas 0..1 are reached, area 2 is the one ahead (its landmark shows), area 3 is unknown (just a ?).
    im = _image(render_map(1, 1, scale=SCALE, cache_dir=None))
    ahead = map_runtime._overlay(2)
    beyond = map_runtime._overlay(3)
    shown, total = _shown(im, ahead, SCALE)
    assert shown > 0.9 * total
    shown, total = _shown(im, beyond, SCALE)
    assert shown < 0.1 * total
    sx, sy = SITES[3]
    near = {im.getpixel((x * SCALE, y * SCALE)) for x in range(sx - 4 * UNIT, sx + 4 * UNIT) for y in range(sy - 11 * UNIT, sy)}
    assert INK in near  # the ? is there


def test_cache_returns_identical_bytes(tmp_path):
    first = render_map(2, 4, scale=SCALE, cache_dir=tmp_path)
    assert list(tmp_path.glob(f"map_*_2_*_x{SCALE}.png"))
    assert render_map(2, 4, scale=SCALE, cache_dir=tmp_path) == first


@pytest.mark.asyncio
async def test_travel_page_attaches_the_map(db):
    nav, _ = await hub("ship")
    assert [name for name, _ in nav._files] == ["map.png"]
    assert nav._attachments()[0].filename == "map.png"


@pytest.mark.asyncio
async def test_pages_without_pictures_attach_nothing(db):
    nav, _ = await hub("home")
    assert nav._files == []
    assert nav._attachments() == []
