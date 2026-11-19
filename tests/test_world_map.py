"""The Travel page's world map: rendered per player, fogged past the area ahead, X where you are."""
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
RX, RY = DATA["fog"]
FOG = {(0xE6, 0xCF, 0x98, 255), (0xD6, 0xB9, 0x7C, 255)}
RED = (0xE8, 0x28, 0x1C, 255)
SCALE = 2


def _image(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGBA")


def _inside_fog(site: tuple[int, int]) -> tuple[int, int]:
    """A pixel inside the fog ellipse, clear of the ink "?" in its centre."""
    sx, sy = site
    return sx - RX // 2, sy + 6


def test_render_is_a_png_at_scaled_size():
    png = render_map(0, 0, scale=SCALE, cache_dir=None)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _image(png).size == (W * SCALE, H * SCALE)


def test_default_scale_is_the_display_scale():
    assert _image(render_map(0, 0, cache_dir=None)).size == (W * SCALE, H * SCALE)


def test_x_marks_the_current_area():
    im = _image(render_map(3, 3, scale=SCALE, cache_dir=None))
    sx, sy = SITES[3]
    near = [im.getpixel((x, y)) for x in range((sx - 12) * SCALE, (sx + 12) * SCALE)
            for y in range((sy - 16) * SCALE, (sy + 4) * SCALE)
            if 0 <= x < im.width and 0 <= y < im.height]
    assert RED in near


def test_areas_past_the_one_ahead_are_fogged():
    # highest = 1: areas 0..1 are reached, area 2 is the one ahead (revealed), area 3 is fogged.
    im = _image(render_map(1, 1, scale=SCALE, cache_dir=None))
    base = Image.open(map_runtime._ASSETS / "world_map.png").convert("RGBA")
    ahead = _inside_fog(SITES[2])
    beyond = _inside_fog(SITES[3])
    assert im.getpixel((beyond[0] * SCALE, beyond[1] * SCALE)) in FOG
    assert im.getpixel((ahead[0] * SCALE, ahead[1] * SCALE)) == base.getpixel(ahead)


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
