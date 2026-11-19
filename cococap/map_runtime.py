"""Runtime world map for the Travel page (pure Python + Pillow; no discord, no art/ imports).

Reads cococap/assets/world_map.png and world_map.json (one site per area, in registry order). Areas up to the
highest one reached are shown, the area ahead of it is revealed too, and everything beyond shows only a ? on the open map. A red X
marks where the player is now.
"""
import io
import json
from pathlib import Path

from PIL import Image

_ASSETS = Path(__file__).resolve().parent / "assets"
_PAPER = (0xF1, 0xE0, 0xB4, 255)
_INK = (0x4B, 0x31, 0x20, 255)
_RED = (0xE8, 0x28, 0x1C, 255)
_QUESTION = [".hhhhh.", "hoooooh", "hohhhoh", "hhh.hoh", ".hhooh.", "..hoh..", "..hhh..", "..hoh..", "..hhh.."]  # an ink ? with a paper halo
_X = [
    "oo...oo",
    "oRo.oRo",
    ".oRoRo.",
    "..oRo..",
    ".oRoRo.",
    "oRo.oRo",
    "oo...oo",
]  # the "you are here" mark, top-left at (site x + 4, site y - 14)
_BASE: Image.Image | None = None
_SITES: list[tuple[int, int]] | None = None
_UNIT = 1  # map pixels per drawing pixel: the base map is drawn at a finer grid; marks are stamped in unit-sized blocks


def _load() -> None:
    global _BASE, _SITES, _UNIT
    if _BASE is None:
        _BASE = Image.open(_ASSETS / "world_map.png").convert("RGBA")
        data = json.loads((_ASSETS / "world_map.json").read_text(encoding="utf-8"))
        _SITES = [(int(x), int(y)) for x, y in data["sites"]]
        _UNIT = int(data.get("unit", 1))


def _stamp(img: Image.Image, left: int, top: int, rows: list[str], pal: dict[str, tuple]) -> None:
    u = _UNIT
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch not in pal:
                continue
            for dy in range(u):
                for dx in range(u):
                    x, y = left + i * u + dx, top + j * u + dy
                    if 0 <= x < img.width and 0 <= y < img.height:
                        img.putpixel((x, y), pal[ch])


def _unknown(img: Image.Image, sx: int, sy: int) -> None:
    """An area the player cannot see yet: the open map with just a ? where its landmark will be."""
    u = _UNIT
    _stamp(img, sx - 3 * u, sy - 10 * u, _QUESTION, {"o": _INK, "h": _PAPER})


_OVERLAYS: list[Image.Image] = []


def _overlay(i: int) -> Image.Image:
    """Area i's landmark and name (a transparent layer the size of the map), loaded once."""
    while len(_OVERLAYS) <= i:
        _OVERLAYS.append(Image.open(_ASSETS / f"world_map_area_{len(_OVERLAYS)}.png").convert("RGBA"))
    return _OVERLAYS[i]


def _art_version() -> str:
    """A short fingerprint of the map art, so a redrawn map never serves stale cached images."""
    import zlib

    return f"{zlib.crc32(b''.join(f.read_bytes() for f in sorted(_ASSETS.glob('world_map*')))):08x}"


def render_map(
    current: int,
    highest: int,
    scale: int = 2,
    cache_dir: Path | None = Path("data/map_images"),
) -> bytes:
    """Return PNG bytes of the world map for a player at area `current`, who reached area `highest`.

    Rendered at base size then scaled with nearest-neighbour. Cached as <cache_dir>/map_<current>_<revealed>_x<scale>.png,
    where `revealed` is how many areas are shown; cache_dir=None disables caching.
    """
    _load()
    count = len(_SITES)
    current = min(max(current, 0), count - 1)
    highest = min(max(highest, 0), count - 1)
    revealed = min(highest + 2, count)  # reached areas plus the one ahead

    path = None
    if cache_dir is not None:
        path = Path(cache_dir) / f"map_{_art_version()}_{current}_{revealed}_x{scale}.png"  # new art = new files
        if path.exists():
            return path.read_bytes()

    img = _BASE.copy()
    for i in range(count):
        if i < revealed:
            img.alpha_composite(_overlay(i))
        else:
            _unknown(img, *_SITES[i])
    cx, cy = _SITES[current]
    _stamp(img, cx + 4 * _UNIT, cy - 14 * _UNIT, _X, {"o": _INK, "R": _RED})
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    png = buf.getvalue()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
    return png
