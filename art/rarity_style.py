"""Framed item art: the sprite on a 20x20 grid inside a sprite-dark ring and a rarity ring, x6 to 120px, plus the rarity animation.

Rules (docs/plans/item-art-outline.md):
  - the sprite's own baked-in dark edge is stripped, then it sits 2px in from the 20x20 canvas so nothing clips
  - ring 1 (inner) is sprite-dark: each pixel a darkened copy of the sprite colour it touches (4-neighbour)
  - ring 2 (outer) is the rarity colour (4-neighbour); a two-tone rarity (`color2`) runs a diagonal gradient
  - animation by rarity: 3-4 breathe (the ring slowly brightens and dims); 5 wave; 6-7 wave + gleam;
    8 wave + gleam + sparkles. 1-2 stay still.
"""
from __future__ import annotations

import colorsys
import math

from PIL import Image

from art.palette import load, rgb

CANVAS = 20  # the sprite (16x16) plus a 2px margin
PAD = 2
SCALE = 6  # 20 -> 120px (Discord emoji max is 128)
FRAMES = 45  # one loop: ~3 s at MS, so the gleam comes round about every 3 s
MS = 67
GLEAM_FRAMES = 12  # the gleam sweeps over the first 12 frames, then the loop holds it off until the next pass
SPARKLE_ON = 8  # frames one sparkle's twinkle lasts per loop
N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))


def effects(rarity: int) -> tuple[bool, bool, bool, bool]:
    """(breathe, wave, gleam, sparkles) for a rarity. Owner: Rare and Super Rare only breathe; a hue wave read too flashy there."""
    return (rarity in (3, 4), rarity >= 5, rarity >= 6, rarity >= 8)


def is_animated(rarity: int) -> bool:
    return rarity >= 3


def _opaque(im: Image.Image, x: int, y: int) -> bool:
    return 0 <= x < im.width and 0 <= y < im.height and im.getpixel((x, y))[3] > 0


def strip_dark_edge(im: Image.Image, limit: int = 70) -> Image.Image:
    """Remove the sprite's own dark outline: edge pixels (touching transparency) that are near-black."""
    out = im.copy()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = im.getpixel((x, y))
            if a and (0.3 * r + 0.59 * g + 0.11 * b) < limit and any(not _opaque(im, x + dx, y + dy) for dx, dy in N4):
                out.putpixel((x, y), (0, 0, 0, 0))
    return out


def _dark(px) -> tuple[int, int, int, int]:
    """A darker, slightly richer version of the sprite colour it touches (sprite-dark ring)."""
    r, g, b = px[:3]
    return (int(r * 0.32), int(g * 0.28), int(b * 0.36), 255)


def _ring(src: Image.Image, color_of) -> Image.Image:
    """One 1px 4-neighbour ring round the opaque pixels of src; color_of(x, y, neighbour_px) gives its colour."""
    out = src.copy()
    for y in range(src.height):
        for x in range(src.width):
            if src.getpixel((x, y))[3]:
                continue
            for dx, dy in N4:
                if _opaque(src, x + dx, y + dy):
                    out.putpixel((x, y), color_of(x, y, src.getpixel((x + dx, y + dy))))
                    break
    return out


def _rarity_fill(rarity: int):
    """(x, y) -> RGBA colour for the rarity ring. Two-tone rarities run a diagonal gradient, top-left to bottom-right."""
    r = next(x for x in load()["rarity"] if x["value"] == rarity)
    a = rgb(r["color"])[:3]
    if "color2" not in r:
        return lambda x, y: (*a, 255)
    b = rgb(r["color2"])[:3]

    def fill(x: int, y: int):
        t = min(1.0, max(0.0, (x + y) / (2 * (CANVAS - 1))))
        return (*(round(a[i] + (b[i] - a[i]) * t) for i in range(3)), 255)

    return fill


def base_layers(frame: Image.Image, rarity: int) -> tuple[Image.Image, set[tuple[int, int]]]:
    """A 16x16 frame -> (20x20 image with both rings, the set of rarity-ring pixel coords)."""
    pad = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    pad.alpha_composite(strip_dark_edge(frame), (PAD, PAD))
    inner = _ring(pad, lambda x, y, px: _dark(px))
    fill = _rarity_fill(rarity)
    outer = _ring(inner, lambda x, y, px: fill(x, y))
    ring = {(x, y) for y in range(CANVAS) for x in range(CANVAS) if outer.getpixel((x, y))[3] and not inner.getpixel((x, y))[3]}
    return outer, ring


def _shift(px, dh: float = 0.0, dv: float = 0.0, toward_white: float = 0.0):
    r, g, b, a = px
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    h, l = (h + dh) % 1, max(0.0, min(1.0, l + dv))
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    r, g, b = (c + (1 - c) * toward_white for c in (r, g, b))
    return (round(r * 255), round(g * 255), round(b * 255), a)


def _frame(outer: Image.Image, ring: set, rarity: int, t: float, sparkles: list) -> Image.Image:
    """One 20x20 frame at loop position t (0..FRAMES, may be fractional). Effects follow `effects(rarity)`."""
    breathe, wave, gleam, sparkle = effects(rarity)
    breath = 0.10 * math.sin(2 * math.pi * t / FRAMES)  # one slow in-and-out per ~3 s loop
    out = outer.copy()
    band = -6 + (t / GLEAM_FRAMES) * 52 if t < GLEAM_FRAMES else None  # the gleam's diagonal (x + y), once per loop
    for y in range(CANVAS):
        for x in range(CANVAS):
            px = outer.getpixel((x, y))
            if not px[3]:
                continue
            on_ring = (x, y) in ring
            dh = dv = w = 0.0
            if breathe and on_ring:
                dv = breath
            if wave and on_ring:  # a slight hue + brightness ripple running round the ring
                k = math.sin(2 * math.atan2(y - (CANVAS - 1) / 2, x - (CANVAS - 1) / 2) + 2 * math.pi * t / FRAMES)
                dh, dv = 0.04 * k, 0.08 * k
            if gleam and band is not None:
                dist = abs((x + y) - band)
                if dist < 1.6:
                    w = (0.85 if on_ring else 0.45) * (1 - dist / 1.6)
            out.putpixel((x, y), _shift(px, dh, dv, w))
    if sparkle:
        # Each sparkle twinkles once per loop at its own random moment (so some twinkle together): a dot in the ring colour that grows into a plus with a white
        # heart for a couple of frames, then shrinks back (the look the owner picked in the first preview).
        for sx, sy, colour, start in sparkles:
            ph = (int(t) - start) % FRAMES
            if ph >= SPARKLE_ON:
                continue
            out.putpixel((sx, sy), (255, 255, 255, 255) if ph in (3, 4) else colour)
            if 2 <= ph <= 5:
                for dx, dy in N4:
                    if 0 <= sx + dx < CANVAS and 0 <= sy + dy < CANVAS and not out.getpixel((sx + dx, sy + dy))[3]:
                        out.putpixel((sx + dx, sy + dy), colour)
    return out


def _sparkles(outer: Image.Image, rarity: int) -> list:
    if not effects(rarity)[3]:
        return []
    # The owner's pick (first preview): 4 random clear spots, each starting its twinkle at a random frame, so sometimes two
    # or three twinkle at once. Seeded from the image, so a sprite always builds the same.
    import random
    import zlib

    rng = random.Random(zlib.crc32(outer.tobytes()))
    def clear(x: int, y: int) -> bool:
        return all(not _opaque(outer, x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))

    free = [(x, y) for y in range(1, CANVAS - 1) for x in range(1, CANVAS - 1) if clear(x, y)]
    fill = _rarity_fill(rarity)
    return [(x, y, fill(x, y), rng.randrange(FRAMES)) for x, y in rng.sample(free, min(4, len(free)))]


def framed(sprite) -> tuple[list[Image.Image], list[int]]:
    """A framed sprite's 20x20 frames and their ms (ms empty when still). Own frames keep their timing: each one gets the
    effect frame that is showing when it starts, so the rarity effects and an item's own animation run together."""
    rarity = sprite.rarity
    if len(sprite.frames) > 1:
        layers = [base_layers(f, rarity) for f in sprite.frames]
        if not is_animated(rarity):
            return [o for o, _ in layers], list(sprite.ms)
        spark = _sparkles(layers[0][0], rarity)
        out, t = [], 0.0
        for (o, ring), ms in zip(layers, sprite.ms, strict=True):
            out.append(_frame(o, ring, rarity, (t / MS) % FRAMES, spark))
            t += ms
        return out, list(sprite.ms)
    outer, ring = base_layers(sprite.frames[0], rarity)
    if not is_animated(rarity):
        return [outer], []
    spark = _sparkles(outer, rarity)
    return [_frame(outer, ring, rarity, t, spark) for t in range(FRAMES)], [MS] * FRAMES


def scale(im: Image.Image) -> Image.Image:
    return im.resize((CANVAS * SCALE, CANVAS * SCALE), Image.NEAREST)
