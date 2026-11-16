"""Wisp generator: a silhouette + one base colour -> shaded, outlined 16x16 sprite (no hand drawing).

To add a silhouette: add an entry to SHAPES below ('#' = body, '.' = empty, every row the same width, at most 12 x 12 so the
outline still fits inside the cell). Then use it by name in art/wisps.toml.
"""
from __future__ import annotations

import colorsys

from PIL import Image

from art.palette import RGBA, WHITE, mix, outline_color, rgb

SHAPES: dict[str, list[str]] = {
    "round": ["....####....", "..########..", ".##########.", "############", "############", "############", "############",
              "############", ".##########.", "..########..", "....####...."],
    "drop": [".....##.....", "....####....", "....####....", "...######...", "..########..", ".##########.", ".##########.",
             "############", "############", ".##########.", "...######..."],
    "ghost": ["...######...", ".##########.", ".##########.", "############", "############", "############", "############",
              "############", "############", "###.####.###", "##...##...##"],
    "cloud": ["..##....##..", ".####..####.", "############", "############", "############", "############", "############",
              ".##########.", "..########..", "....####...."],
    "gem": [".....##.....", "....####....", "...######...", "..########..", ".##########.", "############", ".##########.",
            "..########..", "...######...", "....####....", ".....##....."],
    "eared": ["##........##", "###......###", "############", "############", "############", "############", "############",
              "############", ".##########.", "...######..."],
    "flame": [".......##...", "......###...", ".....####...", "....#####...", "...######...", "..########..", ".##########.",
              ".##########.", "############", "############", ".##########.", "...######..."],
    "jelly": ["...######...", ".##########.", "############", "############", "############", "############", ".##########.",
              ".#.#.##.#.#.", ".#.#.##.#.#.", "..#..##..#.."],
    "crescent": ["....#####...", "..#######...", ".#######....", ".######.....", "#######.....", "#######.....", ".######.....",
                 ".#######....", "..#######...", "....#####..."],
    "bulb": [".....##.....", "....####....", "..########..", ".##########.", ".##########.", ".##########.", ".##########.",
             ".##########.", ".##########.", "..########..", "...######..."],
    "spiky": ["#....##....#", ".#..####..#.", "..########..", ".##########.", "############", "############", "############",
              ".##########.", "..########..", ".#..####..#.", "#....##....#"],
    "mushroom": ["...######...", ".##########.", "############", "############", "############", ".##########.", "....####....",
                 "....####....", "....####....", "...######..."],
}


def check_shape(name: str, rows: list[str]) -> None:
    if not rows or len({len(r) for r in rows}) != 1:
        raise ValueError(f"shape {name}: rows must all have the same width")
    if len(rows) > 12 or len(rows[0]) > 12:
        raise ValueError(f"shape {name}: at most 12 x 12 (the outline needs room)")
    if any(ch not in "#." for r in rows for ch in r):
        raise ValueError(f"shape {name}: only '#' and '.' allowed")


for _n, _r in SHAPES.items():
    check_shape(_n, _r)


def _col(h: float, s: float, v: float) -> RGBA:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return (round(r * 255), round(g * 255), round(b * 255), 255)


def ramp(base_hex: str) -> dict[str, RGBA]:
    """Saturated, hue-shifted ramp: shadows lean to blue/violet, lights to warm. d s m l h, plus w (white)."""
    h, s, v = colorsys.rgb_to_hsv(*(int(base_hex.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)))
    s = min(1.0, max(s, 0.45) * 1.05)
    return {
        "d": _col(h + 0.07, s, v * 0.50), "s": _col(h + 0.04, s * 1.05, v * 0.72), "m": _col(h, s, v),
        "l": _col(h - 0.02, s * 0.75, min(1, v * 1.18)), "h": _col(h - 0.05, s * 0.4, 1.0), "w": WHITE,
    }


def _edge_depth(p: tuple[int, int], pix: set, cap: int = 4) -> int:
    x, y = p
    for d in range(1, cap + 1):
        if (x - d, y) not in pix or (x + d, y) not in pix or (x, y - d) not in pix or (x, y + d) not in pix:
            return d
    return cap


def _shade(rows: list[str], inverted: bool) -> tuple[dict[tuple[int, int], str], int, int]:
    pix = {(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "#"}
    height = len(rows)
    tones: dict[tuple[int, int], str] = {}
    for (x, y) in pix:
        d = _edge_depth((x, y), pix)
        lit = (x - 1, y) not in pix or (x, y - 1) not in pix
        shadow = (x + 1, y) not in pix or (x, y + 1) not in pix
        if inverted:  # dark core, bright rim
            t = ("h" if lit else "l") if d == 1 else ("m" if d == 2 else "s" if d == 3 else "d")
        elif d == 1:
            t = "l" if lit and not shadow else ("d" if shadow and not lit else ("m" if lit and shadow else "s"))
        elif d == 2:
            t = "m" if y < height * 0.62 else "s"
        else:
            t = "l" if d == 3 else "h"
        tones[(x, y)] = t
    # one or two white specular pixels, up and left
    for p in sorted((p for p in pix if _edge_depth(p, pix) == 2), key=lambda q: q[0] + q[1] * 1.3)[:1 if inverted else 2]:
        tones[p] = "w"
    # eyes: 1 wide x 2 tall, two columns apart, on the body's middle at the eye row
    ey = max(2, int(height * 0.45))
    xs = sorted(x for (x, y) in pix if y == ey)
    mid = (xs[0] + xs[-1]) / 2
    for ex in (int(mid - 1.5), int(mid + 1.5)):
        for dy in range(2):
            if (ex, ey + dy) in pix:
                tones[(ex, ey + dy)] = "E"
    return tones, max(x for x, _ in pix) + 1, height


def render_wisp(shape: str, base: str, inverted: bool = False, framed: bool = False) -> Image.Image:
    """16x16 RGBA wisp with its own plum outline. framed=True centres it inside the cell's 14 inner rows."""
    if shape not in SHAPES:
        raise ValueError(f"unknown wisp shape {shape!r} (known: {', '.join(sorted(SHAPES))})")
    plum = outline_color()
    pal = ramp(base)
    if inverted:
        pal["d"], pal["s"] = mix(pal["d"], plum, 0.55), mix(pal["s"], plum, 0.35)
    pal["E"] = WHITE if inverted else plum
    tones, bw, bh = _shade(SHAPES[shape], inverted)
    lo, hi = (1, 15) if framed else (0, 16)
    xb, yb = (16 - bw) // 2, lo + ((hi - lo) - bh) // 2
    layer = {(xb + x, yb + y): pal[t] for (x, y), t in tones.items()}
    out = dict(layer)
    for (x, y) in layer:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (x + dx, y + dy)
            if q not in layer and 0 <= q[0] < 16 and 0 <= q[1] < 16:
                out[q] = plum
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for (x, y), c in out.items():
        im.putpixel((x, y), c)
    return im


__all__ = ["SHAPES", "check_shape", "ramp", "render_wisp", "rgb"]
