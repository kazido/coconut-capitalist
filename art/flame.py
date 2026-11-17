"""Flame wisps: slim flames with a darker face plate and four flickering frames. Frameless, no outline (they glow instead).

Faces: "core" (a dark plate with two white eyes), "skull" (a pale skull with dark sockets) and "eyes" (just two dark eyes).
The shape is tall and narrow (10 wide) on purpose: the round wisps in art/wisp.py looked too fat. Frames differ only in which
tongues of the flame are tall and where the embers float, so a list of them is calm and a single one still reads when it is still."""
from __future__ import annotations

import colorsys

from PIL import Image

from art.palette import RGBA, WHITE, mix, outline_color, rgb
from art.wisp import ramp

FACES = ("core", "skull", "eyes")
FRAMES = 4
FRAME_MS = 140

_TOP = [8, 6, 5, 4, 3, 3, 4, 5, 6, 8]       # first row of the body per column (a teardrop)
_BOTTOM = [12, 13, 14, 14, 14, 14, 14, 14, 13, 12]
_SPIKES = [{4: -2, 7: -1, 2: -1}, {5: -3, 2: -2, 8: -1}, {3: -2, 6: -2, 8: -1}, {4: -1, 5: -2, 1: -1}]  # tongues that flicker, per frame
_EMBERS = [[(2, 1), (8, 2)], [(7, 0), (1, 3)], [(3, 1), (9, 3)], [(6, 1), (0, 2)]]
_SKULL = ["..####..", ".######.", "#kk##kk#", "#kk##kk#", ".##kk##.", ".#.##.#."]


def flame_ramp(base_hex: str) -> dict[str, RGBA]:
    """The shared ramp, with warm colours' shadows kept warm (the default shift turns yellow shadows olive green)."""
    pal = ramp(base_hex)
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb(base_hex)[:3]))
    if 0.04 <= h <= 0.2:  # orange / yellow: shadows lean to red-brown instead
        for key, scale in (("s", 0.72), ("d", 0.5)):
            r, g, b = colorsys.hsv_to_rgb((h - 0.03 * (2 if key == "d" else 1)) % 1.0, min(1.0, s * 1.05), v * scale)
            pal[key] = (round(r * 255), round(g * 255), round(b * 255), 255)
    return pal


def _cells(frame: int) -> set[tuple[int, int]]:
    cells = set()
    for x in range(10):
        top = max(1, _TOP[x] + _SPIKES[frame].get(x, 0))
        cells |= {(x, y) for y in range(top, _BOTTOM[x] + 1)}
    return cells


def render_flame(base: str, face: str = "core", frame: int = 0, embers: bool = True) -> Image.Image:
    """One 16x16 frame (frame 0..3)."""
    if face not in FACES:
        raise ValueError(f"unknown flame face {face!r} (known: {', '.join(FACES)})")
    pal = flame_ramp(base)
    cells = _cells(frame % FRAMES)
    y0, y1 = min(y for _, y in cells), max(y for _, y in cells)
    layer: dict[tuple[int, int], RGBA] = {}
    for (x, y) in cells:  # pale tip -> saturated base, with a lighter rim on the sides and top
        t = (y - y0) / max(1, y1 - y0)
        tone = "h" if t < 0.22 else "l" if t < 0.45 else "m" if t < 0.72 else "s" if t < 0.9 else "d"
        rim = any((x + dx, y + dy) not in cells for dx, dy in ((1, 0), (-1, 0), (0, -1)))
        if rim and tone in ("m", "s") and y < y1 - 1:
            tone = "l" if tone == "m" else "m"
        layer[(x, y)] = pal[tone]
    dark = mix(pal["d"], outline_color(), 0.55)
    if face == "core":
        for (x, y) in list(layer):
            if ((x - 4.5) / 3.2) ** 2 + ((y - 10.2) / 2.8) ** 2 <= 1:
                layer[(x, y)] = dark
        for ex in (3, 6):
            layer[(ex, 9)] = layer[(ex, 10)] = WHITE
    elif face == "skull":
        bone, shade = rgb("f2ecd2"), rgb("bfb48f")
        for y, row in enumerate(_SKULL):
            for x, ch in enumerate(row):
                if ch != ".":
                    layer[(1 + x, 7 + y)] = dark if ch == "k" else (shade if y >= 4 else bone)
    else:
        for ex in (3, 6):
            layer[(ex, 9)] = layer[(ex, 10)] = dark
    if embers:
        for p in _EMBERS[frame % FRAMES]:
            layer.setdefault(p, pal["h"])
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for (x, y), c in layer.items():
        im.putpixel((3 + x, y), c)
    return im


def render_flame_frames(base: str, face: str = "core", embers: bool = True) -> list[Image.Image]:
    return [render_flame(base, face, f, embers) for f in range(FRAMES)]
