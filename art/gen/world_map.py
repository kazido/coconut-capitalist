"""The world map for the Travel (ship) page: an old parchment map with the 7 areas marked along a dotted route.

The base map is pixel art (W x H), drawn from math and noise, inked like a classic treasure map. Each area has a small
landmark icon at a fixed spot; `SITES` (area index -> pixel) is exported with the map so the bot can draw the red X on
the current area and fog over the areas not reached yet (cococap/map_runtime.py).
Run: python art/gen/world_map.py [preview.png]   (no argument = export cococap/assets/world_map.png + world_map.json)
"""
import json
import math
import os
import sys

from PIL import Image

W, H = 168, 108
EXPORT = 3


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def _hash(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n & 0xFFFF) / 0xFFFF


def vnoise(x, y, s=0):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, s), _hash(ix + 1, iy, s)
    c, d = _hash(ix, iy + 1, s), _hash(ix + 1, iy + 1, s)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(x, y, s=0):
    return sum(vnoise(x * f, y * f, s + i) / (2 ** i) for i, f in enumerate((1, 2, 4))) / 1.75


PAPER = [hexc(c) for c in ("#f1e0b4", "#e6cf98", "#d6b97c", "#bf9d62", "#9c7a45")]
INK = hexc("#4b3120")
INK_LIGHT = hexc("#8a6440")
SEA = [hexc(c) for c in ("#cfd2a8", "#b9c19a", "#a3b08c")]
ROUTE = hexc("#9b2a1c")

# Where each area sits (area index 0..6): a winding road from the south-west shore to the edge of the world.
SITES = [(30, 80), (58, 70), (52, 44), (84, 36), (110, 22), (128, 52), (150, 82)]


def land(x, y):
    """Land height: one big island with ragged coasts (> 0 = land)."""
    cx, cy = W * 0.48, H * 0.52
    d = math.hypot((x - cx) / (W * 0.46), (y - cy) / (H * 0.44))
    return 1.0 - d + (fbm(x / 14, y / 14, 3) - 0.5) * 0.7


def base_map():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = im.load()
    for y in range(H):
        for x in range(W):
            # torn, burnt edge: distance to the border, roughened by noise
            edge = min(x, y, W - 1 - x, H - 1 - y) + (fbm(x / 6, y / 6, 9) - 0.5) * 6
            if edge < 1.5:
                continue
            if edge < 3:
                px[x, y] = hexc("#5a3a1e")  # the burnt rim
                continue
            age = (fbm(x / 9, y / 9, 1) - 0.5) * 1.6 + max(0.0, 6 - edge) * 0.35  # stains + darker toward the edge
            h = land(x, y)
            if h > 0:
                tone = 0.6 + age + (0.5 if h < 0.05 else 0)
                px[x, y] = PAPER[max(0, min(4, int(tone)))]
            else:
                tone = int(min(2, max(0, 0.5 + age - h * 3)))
                px[x, y] = SEA[tone]
                if (y % 6 == 0 and ((x + y // 6 * 3) % 9) in (0, 1, 2) and h < -0.12):  # little ink waves out at sea
                    px[x, y] = INK_LIGHT
    # coastline: ink where land meets sea, a lighter second line just offshore
    snap = im.copy().load()
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if not snap[x, y][3]:
                continue
            if land(x, y) > 0 and any(land(x + dx, y + dy) <= 0 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = INK
            elif land(x, y) <= 0 and -0.06 < land(x, y) and snap[x, y] in SEA:
                px[x, y] = INK_LIGHT if (x + y) % 2 == 0 else snap[x, y]
    _route(im)
    for i, (sx, sy) in enumerate(SITES):
        ICONS[i](im, sx, sy)
    _compass(im, 18, 18)
    return im


def _route(im):
    """A dotted red route through the sites, gently curved."""
    px = im.load()
    for (x0, y0), (x1, y1) in zip(SITES, SITES[1:]):
        mx, my = (x0 + x1) / 2 + (y1 - y0) * 0.18, (y0 + y1) / 2 - (x1 - x0) * 0.18
        n = int(math.hypot(x1 - x0, y1 - y0) * 1.5)
        for i in range(n):
            t = i / n
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1
            if 0.12 < t < 0.88 and (i // 2) % 3 == 0:
                px[int(x), int(y)] = ROUTE


def _put(im, x, y, c):
    if 0 <= x < W and 0 <= y < H:
        im.putpixel((int(x), int(y)), c)


def _sprite(im, cx, cy, rows, pal):
    """Stamp a small hand-placed sprite centred on (cx, cy)."""
    h, w = len(rows), len(rows[0])
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in pal:
                _put(im, cx - w // 2 + i, cy - h + 2 + j, pal[ch])


O = INK
ICONS = [
    # 0 Slime Hill: a green hill with a happy slime on top
    lambda im, x, y: _sprite(im, x, y, [
        "....ooo....",
        "...oGgGo...",
        "...ogwgo...",
        "..oggggo...",
        ".oHHHHHHHo.",
        "oHhHHHHhHHo",
        "ohhhhhhhhho",
        "ooooooooooo"], {"o": O, "G": hexc("#9be36a"), "g": hexc("#5fb04a"), "w": hexc("#1c3a14"),
                         "H": hexc("#8cbf5e"), "h": hexc("#5f8f3c")}),
    # 1 Twilight Desert: dunes under a dusky sun
    lambda im, x, y: _sprite(im, x, y, [
        "....ooo....",
        "...oSSSo...",
        "....ooo....",
        "...ooo.....",
        "..oDDDooo..",
        ".oDDdDDDDo.",
        "oddDDDdddDo",
        "ooooooooooo"], {"o": O, "S": hexc("#ff9f6a"), "D": hexc("#e8b878"), "d": hexc("#b98a50")}),
    # 2 Rust Belt: a rusted cog
    lambda im, x, y: _sprite(im, x, y, [
        "...o.o.o...",
        "..oRoRoRo..",
        ".oRRRRRRRo.",
        "oRRroooRRRo",
        ".oRro.oRRo.",
        "oRRroooRRRo",
        ".oRRRRRRRo.",
        "..oRoRoRo..",
        "...o.o.o..."], {"o": O, "R": hexc("#c06a34"), "r": hexc("#7e3e1c")}),
    # 3 Cadrega City: walled towers
    lambda im, x, y: _sprite(im, x, y, [
        "..o.....o..",
        ".oTo...oTo.",
        ".oTo.o.oTo.",
        ".oTooToTTo.",
        "oWTTTTTTTWo",
        "oWwTTwTTwWo",
        "oWWWWWWWWWo",
        "ooooooooooo"], {"o": O, "T": hexc("#c9b9a0"), "w": hexc("#3a2a1a"), "W": hexc("#9a8a72")}),
    # 4 Aerial Glades: a floating island with a tree and a cloud
    lambda im, x, y: _sprite(im, x, y, [
        "....ooo....",
        "...oLLLo...",
        "...oLlLo...",
        "....oto....",
        ".oGGGtGGGo.",
        "..oEEEEEo..",
        "...oEEEo...",
        "....oEo....",
        "ooo..o..ooo"], {"o": O, "L": hexc("#7fd07a"), "l": hexc("#4e9a48"), "t": hexc("#7a5030"),
                         "G": hexc("#9be36a"), "E": hexc("#a88a60")}),
    # 5 Star Kingdom: a castle with a star above
    lambda im, x, y: _sprite(im, x, y, [
        ".....o.....",
        "....oYo....",
        "...oYYYo...",
        "o.o.oYo.o.o",
        "oCoCoCoCoCo",
        "oCCCCCCCCCo",
        "oCCcoooCCCo",
        "oCCco.oCCCo",
        "ooooooooooo"], {"o": O, "Y": hexc("#ffe066"), "C": hexc("#c8c0e8"), "c": hexc("#8a80b8")}),
    # 6 The Void: a dark swirl where the map ends
    lambda im, x, y: _sprite(im, x, y, [
        "...ooooo...",
        "..oVVVVVo..",
        ".oVvoooVVo.",
        "oVvo.VVoVVo",
        "oVo.oKoVoVo",
        "oVVoVVo.vVo",
        ".oVVoooovo.",
        "..oVVVVVo..",
        "...ooooo..."], {"o": O, "V": hexc("#6a3fa0"), "v": hexc("#3a1f66"), "K": hexc("#120a20")}),
]


def _compass(im, cx, cy):
    """A small ink compass rose."""
    for r, c in ((6, O), (5, INK_LIGHT)):
        for a in range(0, 360, 8):
            _put(im, cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)), c)
    for i in range(-7, 8):
        _put(im, cx, cy + i, O)
        _put(im, cx + i, cy, O)
    for d in range(1, 4):
        for s in (-1, 1):
            _put(im, cx + s * d, cy - 7 + d, O)
    _put(im, cx, cy - 8, ROUTE)


def export():
    os.makedirs("cococap/assets", exist_ok=True)
    base_map().save("cococap/assets/world_map.png")
    with open("cococap/assets/world_map.json", "w", encoding="utf-8") as f:
        json.dump({"size": [W, H], "sites": SITES}, f)
        f.write("\n")
    print("cococap/assets/world_map.png")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        im = base_map()
        im.resize((W * EXPORT, H * EXPORT), Image.NEAREST).save(sys.argv[1])
    else:
        export()
