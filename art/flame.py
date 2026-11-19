"""Flame wisps: slim flames with a darker face plate and four flickering frames. Frameless, no outline (they glow instead).

Faces: "core" (a dark plate with two white eyes), "skull" (a pale skull with dark sockets) and "eyes" (just two dark eyes), plus
"fang", "cyclops", "visor" and "sleepy" (plate faces) and the skull shapes "horned", "grin" and "slim".
An optional `accent` colour makes the flame dual-toned: the tip is the accent and it melts into the base colour.
The shape is tall and narrow (10 wide) on purpose: the round wisps in art/wisp.py looked too fat. Frames differ only in which
tongues of the flame are tall and where the embers float, so a list of them is calm and a single one still reads when it is still."""
from __future__ import annotations

import colorsys
import math

from PIL import Image

from art.palette import RGBA, WHITE, mix, outline_color, rgb
from art.wisp import ramp

FACES = ("core", "skull", "eyes", "fang", "cyclops", "visor", "sleepy", "horned", "grin", "slim")
FRAMES = 4
FRAME_MS = 140

_TOP = [8, 6, 5, 4, 3, 3, 4, 5, 6, 8]       # first row of the body per column (a teardrop)
_BOTTOM = [12, 13, 14, 14, 14, 14, 14, 14, 13, 12]
_SPIKES = [{4: -2, 7: -1, 2: -1}, {5: -3, 2: -2, 8: -1}, {3: -2, 6: -2, 8: -1}, {4: -1, 5: -2, 1: -1}]  # tongues that flicker, per frame
_EMBERS = [[(2, 1), (8, 2)], [(7, 0), (1, 3)], [(3, 1), (9, 3)], [(6, 1), (0, 2)]]
# Skulls: 8 wide, drawn from (1, top). b = bone, k = dark socket, s = shaded bone (the jaw), . = nothing.
_SKULLS = {
    "skull": (7, ["..bbbb..", ".bbbbbb.", "bkkbbkkb", "bkkbbkkb", ".bbkkbb.", ".sbbbbs."]),
    "horned": (6, ["b......b", "bbbbbbbb", "bkkbbkkb", "bkkbbkkb", ".bbkkbb.", ".sbsbbs."]),
    "grin": (7, ["..bbbb..", ".bbbbbb.", "bkkbbkkb", ".bbbbbb.", ".bkbkbk.", ".ssssss."]),
    "slim": (7, ["..bbbb..", "..bbbb..", ".bkbbkb.", ".bkbbkb.", "..bkkb..", "..sbbs.."]),
}


def flame_ramp(base_hex: str) -> dict[str, RGBA]:
    """The shared ramp, with warm colours' shadows kept warm (the default shift turns yellow shadows olive green)."""
    pal = ramp(base_hex)
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb(base_hex)[:3]))
    if 0.04 <= h <= 0.2:  # orange / yellow: shadows lean to red-brown instead
        for key, scale in (("s", 0.72), ("d", 0.5)):
            r, g, b = colorsys.hsv_to_rgb((h - 0.03 * (2 if key == "d" else 1)) % 1.0, min(1.0, s * 1.05), v * scale)
            pal[key] = (round(r * 255), round(g * 255), round(b * 255), 255)
    return pal


def _tint(pal: dict[str, RGBA], accent: dict[str, RGBA], t: float, tone: str) -> RGBA:
    """Dual-tone: near the tip (t = 0) the accent's tone, melting into the base's by t = 0.65."""
    k = max(0.0, min(1.0, t / 0.65))
    return mix(accent[tone], pal[tone], k)


def _cells(frame: int) -> set[tuple[int, int]]:
    cells = set()
    for x in range(10):
        top = max(1, _TOP[x] + _SPIKES[frame].get(x, 0))
        cells |= {(x, y) for y in range(top, _BOTTOM[x] + 1)}
    return cells


def render_flame(base: str, face: str = "core", frame: int = 0, embers: bool = True, accent: str | None = None) -> Image.Image:
    """One 16x16 frame (frame 0..3)."""
    if face not in FACES:
        raise ValueError(f"unknown flame face {face!r} (known: {', '.join(FACES)})")
    pal = flame_ramp(base)
    acc = flame_ramp(accent) if accent else None
    cells = _cells(frame % FRAMES)
    y0, y1 = min(y for _, y in cells), max(y for _, y in cells)
    layer: dict[tuple[int, int], RGBA] = {}
    for (x, y) in cells:  # pale tip -> saturated base, with a lighter rim on the sides and top
        t = (y - y0) / max(1, y1 - y0)
        tone = "h" if t < 0.22 else "l" if t < 0.45 else "m" if t < 0.72 else "s" if t < 0.9 else "d"
        rim = any((x + dx, y + dy) not in cells for dx, dy in ((1, 0), (-1, 0), (0, -1)))
        if rim and tone in ("m", "s") and y < y1 - 1:
            tone = "l" if tone == "m" else "m"
        layer[(x, y)] = _tint(pal, acc, t, tone) if acc else pal[tone]
    dark = mix(pal["d"], outline_color(), 0.55)
    if face in _SKULLS:
        bone, shade = rgb("f2ecd2"), rgb("bfb48f")
        top, rows = _SKULLS[face]
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                if ch != ".":
                    layer[(1 + x, top + y)] = dark if ch == "k" else shade if ch == "s" else bone
    elif face == "eyes":
        for ex in (3, 6):
            layer[(ex, 9)] = layer[(ex, 10)] = dark
    elif face == "visor":  # a dark band across the whole flame with two glowing slits
        for x in range(10):
            for y in (9, 10):
                if (x, y) in layer:
                    layer[(x, y)] = dark
        layer[(3, 9)] = layer[(6, 9)] = WHITE
    else:  # the plate faces: a dark oval, then the eyes
        for (x, y) in list(layer):
            if ((x - 4.5) / 3.2) ** 2 + ((y - 10.2) / 2.8) ** 2 <= 1:
                layer[(x, y)] = dark
        if face == "core":
            for ex in (3, 6):
                layer[(ex, 9)] = layer[(ex, 10)] = WHITE
        elif face == "fang":  # eyes and two small fangs
            for ex in (3, 6):
                layer[(ex, 9)] = layer[(ex, 10)] = WHITE
            layer[(3, 12)] = layer[(6, 12)] = WHITE
        elif face == "cyclops":  # one big eye with a pupil
            for p in ((4, 9), (5, 9), (4, 10), (5, 10)):
                layer[p] = WHITE
            layer[(5, 10)] = dark
        else:  # sleepy: closed eyes, two flat dashes
            for p in ((2, 10), (3, 10), (5, 10), (6, 10)):
                layer[p] = WHITE
    if embers:
        for p in _EMBERS[frame % FRAMES]:
            layer.setdefault(p, (acc or pal)["h"])
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for (x, y), c in layer.items():
        im.putpixel((3 + x, y), c)
    return im


def render_flame_frames(base: str, face: str = "core", embers: bool = True, accent: str | None = None) -> list[Image.Image]:
    return [render_flame(base, face, f, embers, accent) for f in range(FRAMES)]


AURORA_FRAMES = 8
AURORA_MS = 120


def render_aurora_frames() -> list[Image.Image]:
    """The Celestial pet: a flame whose colour flows like the northern lights (teal -> green -> blue -> violet -> pink bands drifting
    up the body), as one slow band drifting up its body. Eyes and plate stay as the normal "core" face."""
    out = []
    for f in range(AURORA_FRAMES):
        im = render_flame("#7af0d0", "core", f % FRAMES, embers=False)
        phase = f / AURORA_FRAMES
        px = im.load()
        for y in range(16):
            for x in range(16):
                r, g, b, a = px[x, y]
                if not a:
                    continue
                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                if s < 0.12 or v < 0.3:  # the white eyes and the dark face plate keep their colour
                    continue
                wave = 0.5 + 0.5 * math.sin(6.2832 * (y / 14.0 - phase))
                hue = 0.40 + 0.40 * wave  # 0.40 green-teal ... 0.80 violet, one slow band drifting up
                nr, ng, nb = colorsys.hsv_to_rgb(hue % 1.0, min(1.0, 0.45 + 0.5 * s), min(1.0, v * 1.05))
                px[x, y] = (round(nr * 255), round(ng * 255), round(nb * 255), 255)
        out.append(im)
    return out
