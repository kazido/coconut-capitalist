"""Runtime world map for the Travel page (pure Python + Pillow; no discord, no art/ imports).

Reads cococap/assets/world_map.png and world_map.json (one site per area, in registry order). Areas up to the
highest one reached are shown, the area ahead of it is revealed too, and everything beyond is fogged. A red X
marks where the player is now.
"""
import io
import json
from pathlib import Path

from PIL import Image

_ASSETS = Path(__file__).resolve().parent / "assets"
_FOG_IN = (0xE6, 0xCF, 0x98, 255)
_FOG_EDGE = (0xD6, 0xB9, 0x7C, 255)
_INK = (0x4B, 0x31, 0x20, 255)
_RED = (0xE8, 0x28, 0x1C, 255)
_QUESTION = ["ooo", "..o", ".o.", "...", ".o."]  # stamped centred on the site
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
_FOG: tuple[float, float] = (0.0, 0.0)  # fog ellipse radii (rx, ry), from world_map.json
_UNIT = 1  # map pixels per drawing pixel: the base map is drawn at a finer grid; marks are stamped in unit-sized blocks


def _load() -> None:
    global _BASE, _SITES, _FOG, _UNIT
    if _BASE is None:
        _BASE = Image.open(_ASSETS / "world_map.png").convert("RGBA")
        data = json.loads((_ASSETS / "world_map.json").read_text(encoding="utf-8"))
        _SITES = [(int(x), int(y)) for x, y in data["sites"]]
        _FOG = (float(data["fog"][0]), float(data["fog"][1]))
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


def _fog(img: Image.Image, sx: int, sy: int) -> None:
    """A soft parchment ellipse covering the landmark and its name label (6 px below the site): solid inside,
    checkerboard dither at the edge. The ink "?" sits at the centre."""
    rx, ry = _FOG
    u = _UNIT
    cx, cy = sx, sy + 6 * u
    for y in range(max(0, cy - int(ry) - 1), min(img.height, cy + int(ry) + 2)):
        for x in range(max(0, cx - int(rx) - 1), min(img.width, cx + int(rx) + 2)):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 0.6:
                img.putpixel((x, y), _FOG_IN)
            elif d <= 1.0 and (x // u + y // u) % 2 == 0:
                img.putpixel((x, y), _FOG_EDGE)
    _stamp(img, cx - 1 * u, cy - 2 * u, _QUESTION, {"o": _INK})


def _art_version() -> str:
    """A short fingerprint of the map art, so a redrawn map never serves stale cached images."""
    import zlib

    return f"{zlib.crc32(_ASSETS.joinpath('world_map.png').read_bytes() + _ASSETS.joinpath('world_map.json').read_bytes()):08x}"


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
    for i in range(revealed, count):
        _fog(img, *_SITES[i])
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
