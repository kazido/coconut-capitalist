"""Runtime renderer for smithed tool images (pure Python + Pillow; no discord, no art/ imports).

Reads cococap/assets/tool_layers.json, written by `python art/gen/tool_layers.py --export`.
Each tool is 3 recolourable parts (base, trim, accent), each with its own tier 1..7.
"""
import io
import json
from pathlib import Path

from PIL import Image

_DATA_PATH = Path(__file__).resolve().parent / "assets" / "tool_layers.json"
_OUTLINE = (0x2A, 0x1E, 0x2A, 255)
_DATA: dict | None = None


def _data() -> dict:
    global _DATA
    if _DATA is None:
        _DATA = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return _DATA


def _palette(base: int, trim: int, accent: int) -> dict[str, tuple[int, int, int, int]]:
    """Letter -> RGBA; same mapping as art/gen/tool_layers.py palette()."""
    tiers = _data()["tiers"]

    def rgba(hex_code: str) -> tuple[int, int, int, int]:
        h = hex_code.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)

    pal = {}
    pal.update(zip("PpqQ", (rgba(c) for c in tiers[str(base)]), strict=True))
    pal.update(zip("HhkK", (rgba(c) for c in tiers[str(trim)]), strict=True))
    pal.update(zip("Aa", (rgba(c) for c in tiers[str(accent)][1:3]), strict=True))
    return pal


def _check_tier(name: str, tier: int) -> None:
    if not isinstance(tier, int) or not 1 <= tier <= 7:
        raise ValueError(f"{name} tier must be 1..7, got {tier!r}")


def _draw(kind: str, base: int, trim: int, accent: int, scale: int) -> bytes:
    rows = _data()["kinds"][kind]
    pal = _palette(base, trim, accent)
    h, w = len(rows), len(rows[0])
    opaque = [[ch in pal for ch in row] for row in rows]

    def touches(y: int, x: int) -> bool:
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and opaque[ny][nx]:
                return True
        return False

    # 16x16 grid with a 1px outline, placed on an 18x18 canvas (1px transparent border).
    img = Image.new("RGBA", (w + 2, h + 2), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in pal:
                img.putpixel((x + 1, y + 1), pal[ch])
            elif touches(y, x):
                img.putpixel((x + 1, y + 1), _OUTLINE)
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def render_tool(
    kind: str,
    base: int,
    trim: int,
    accent: int,
    scale: int = 8,
    cache_dir: Path | None = Path("data/tool_images"),
) -> bytes:
    """Return PNG bytes for a tool of `kind` with the given base/trim/accent tiers.

    Results are cached as <cache_dir>/<kind>_<base><trim><accent>_x<scale>.png; cache_dir=None disables caching.
    """
    if kind not in _data()["kinds"]:
        raise ValueError(f"unknown tool kind {kind!r}")
    _check_tier("base", base)
    _check_tier("trim", trim)
    _check_tier("accent", accent)

    path = None
    if cache_dir is not None:
        path = Path(cache_dir) / f"{kind}_{base}{trim}{accent}_x{scale}.png"
        if path.exists():
            return path.read_bytes()
    png = _draw(kind, base, trim, accent, scale)
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)
    return png
