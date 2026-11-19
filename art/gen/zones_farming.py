"""Farming location icons (location_<id>). 16x16, free, plum outline, light top-left. argv: out.toml scratch_dir"""
import math
import sys

sys.path.insert(0, sys.argv[2])
_argv = sys.argv[:]
sys.argv = [sys.argv[0], sys.argv[2] + "/_ui_tmp.toml"]
from ui_icons import N, blank, put, rect, line, blob  # noqa: E402
sys.argv = _argv

sprites = {}


def add(name, g, pal):
    sprites[name] = (g, pal)


def ell(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def circ(cx, cy, r):
    return lambda x, y: math.hypot(x - cx, y - cy) <= r


def fill(g, mask, c):
    for y in range(N):
        for x in range(N):
            if mask(x, y):
                put(g, x, y, c)


def soil(g, y0, y1, x0=1, x1=14):
    """Tilled soil: furrow rows alternating light/dark."""
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(g, x, y, "E" if (y - y0) % 2 == 0 else "e")


def sprout(g, x, y):
    put(g, x, y, "L"); put(g, x - 1, y - 1, "L"); put(g, x + 1, y - 1, "l")


SOIL = {"E": "#a8744a", "e": "#6e4630", "L": "#8ade5a", "l": "#4ea03c"}

# Slimeside Garden: sprouts in a tilled bed beside a glossy slime puddle.
g = blank()
soil(g, 8, 13, 1, 10)
for x in (3, 6, 9):
    sprout(g, x, 7); sprout(g, x, 10) if x != 9 else None
fill(g, ell(12.5, 12, 2.6, 1.6), "S"); fill(g, ell(12, 11.6, 1.3, 0.7), "s"); put(g, 11, 11, "W")
add("location_slimeside_garden", g, {**SOIL, "S": "#4cd07a", "s": "#8affb4", "W": "#eafff2"})

# Meadow Farmstead: a red barn with a white-trimmed door beside a wheat field.
g = blank()
for y in range(3, 8):  # roof
    for x in range(N):
        if abs(x - 6) <= (y - 3) + 1.5 and 1 <= x <= 11:
            put(g, x, y, "R" if x < 6 else "r")
rect(g, 2, 8, 10, 13, "B"); rect(g, 9, 8, 10, 13, "b")
rect(g, 4, 10, 7, 13, "W"); rect(g, 5, 11, 6, 13, "k")  # white-framed open door
for x in range(11, 15):
    line(g, x, 9, x, 13, "Y" if x % 2 else "y")
    put(g, x, 8, "Y")
add("location_meadow_farmstead", g, {"k": "#3a1a1c", "R": "#8a3a3a", "r": "#5a2430", "B": "#d84a3a", "b": "#a0302c", "W": "#f4f0e8", "Y": "#ffe07a", "y": "#d8a83a"})

# Dusk Terraces: green terraced steps down a hillside, a dusk sun behind.
g = blank()
fill(g, circ(11, 4.5, 3), "O"); fill(g, circ(11, 4.5, 1.6), "o")
for x0, y0 in ((9, 6), (6, 8), (3, 10), (1, 12)):
    rect(g, x0, y0, 14, y0, "G")
    rect(g, x0, y0 + 1, 14, y0 + 1, "E")
rect(g, 1, 14, 14, 14, "e")
for x0, y0 in ((9, 6), (6, 8), (3, 10), (1, 12)):
    for x in range(x0, 15, 2):
        put(g, x, y0, "g")
add("location_dusk_terraces", g, {"O": "#ff8a5a", "o": "#ffe08a", "G": "#8ad05a", "g": "#5aa03c", "E": "#8a5a3a", "e": "#5a3826"})

# Oasis Orchard: a row of orange trees on desert sand, a little pool in front.
g = blank()
fill(g, ell(7.5, 15, 8, 4), "Y"); fill(g, lambda x, y: ell(7.5, 15, 8, 4)(x, y) and x > 10, "y")
for cx, cy in ((3, 7), (8, 5.5), (12.5, 7.5)):
    line(g, int(cx), int(cy) + 2, int(cx), 12, "B")
    blob(g, circ(cx, cy, 2.5), cx - 1, cy - 1, 2.5, "HmsD")
    put(g, int(cx) - 1, int(cy), "O"); put(g, int(cx) + 1, int(cy) + 1, "O"); put(g, int(cx), int(cy) - 1, "o")
fill(g, ell(5, 13.2, 2.6, 0.9), "A"); put(g, 4, 13, "a")
add("location_oasis_orchard", g, {"Y": "#ffe0a0", "y": "#d8b068", "B": "#7a4c30", "H": "#9ad25a", "m": "#5aa83a",
                                  "s": "#357a30", "D": "#1e4a24", "O": "#ffb040", "o": "#ffd890", "A": "#4ae0d0", "a": "#e8fff8"})

# Scrapyard Allotments: a veg bed edged with scrap plates, a wrench stuck in the soil.
g = blank()
soil(g, 9, 13, 2, 13)
rect(g, 1, 8, 14, 8, "M"); rect(g, 1, 8, 1, 13, "M"); rect(g, 14, 9, 14, 13, "m"); rect(g, 2, 14, 14, 14, "m")
for x in (4, 9):
    put(g, x, 8, "r")  # rivets / rust
for x in (4, 7):
    sprout(g, x, 10); put(g, x, 11, "L")
line(g, 11, 4, 11, 12, "W"); line(g, 12, 4, 12, 12, "w")  # wrench handle, upright
for y in (1, 2):
    put(g, 10, y, "W"); put(g, 13, y, "w")  # open jaw (a U)
rect(g, 10, 3, 13, 3, "W"); put(g, 13, 3, "w")
add("location_scrapyard_allotments", g, {**SOIL, "M": "#a8b0bc", "m": "#5e6472", "r": "#c0683a", "W": "#e4ecf6", "w": "#7e88a0"})

# Hydroponic Bays: a glass tank of water with a plant growing out of it, a pipe feeding it.
g = blank()
rect(g, 3, 7, 12, 13, "G"); rect(g, 3, 7, 3, 13, "H"); rect(g, 12, 7, 12, 13, "q"); rect(g, 3, 13, 12, 13, "q")
rect(g, 4, 9, 11, 12, "A"); rect(g, 4, 9, 11, 9, "a")
for x in (6, 9):
    line(g, x, 9, x, 12, "R")  # roots in the water
for x, top in ((6, 3), (9, 2)):
    line(g, x, top + 1, x, 8, "l")
    put(g, x - 1, top + 1, "L"); put(g, x + 1, top, "L"); put(g, x, top, "L"); put(g, x - 1, top + 3, "L"); put(g, x + 1, top + 2, "l")
rect(g, 13, 9, 14, 9, "P"); rect(g, 14, 10, 14, 13, "P")
add("location_hydroponic_bays", g, {"G": "#c8e8f4", "H": "#ffffff", "q": "#6a8a9a", "A": "#5ab8e8", "a": "#a8e4ff", "R": "#f0e0b0",
                                    "L": "#8ade5a", "l": "#4ea03c", "P": "#b8c2d0"})

# Market Gardens: a market stall under a striped awning, its counter piled with greens, carrots and a cabbage.
g = blank()
for x in range(1, 15):
    for y in (2, 3, 4):
        put(g, x, y, "S" if (x // 2) % 2 == 0 else "W")
    if x % 2:
        put(g, x, 5, "S" if (x // 2) % 2 == 0 else "W")  # scalloped edge
line(g, 2, 5, 2, 13, "T"); line(g, 13, 5, 13, 13, "t")  # posts
rect(g, 2, 10, 13, 13, "B"); rect(g, 2, 10, 13, 10, "T"); rect(g, 13, 11, 13, 13, "t")  # counter
for x, y in ((4, 8), (5, 8)):
    line(g, x, y, x, 9, "C"); put(g, x, y - 1, "L")  # carrots
blob(g, circ(8, 8.2, 1.7), 7.5, 7.5, 1.8, "Kkqq")  # cabbage
for x, y in ((10, 9), (11, 8), (12, 9), (11, 9), (10, 8)):
    put(g, x, y, "L" if (x + y) % 2 else "l")  # leafy greens
put(g, 3, 9, "l"); put(g, 6, 9, "L")
add("location_market_gardens", g, {"S": "#e04a40", "W": "#f4f0e8", "T": "#c8905a", "t": "#7a4c30", "B": "#a8744a", "C": "#ff9a3a",
                                   "L": "#8ade5a", "l": "#3c8a34", "K": "#c8f08a", "k": "#7ac850", "q": "#3c8a34"})

# Rooftop Farms: a city building whose flat roof is planted with green rows.
g = blank()
rect(g, 3, 6, 12, 14, "S"); rect(g, 3, 6, 3, 14, "H"); rect(g, 12, 6, 12, 14, "s")
for y in (8, 11):
    for x in (5, 7, 9):
        put(g, x, y, "Y")
rect(g, 7, 12, 8, 14, "d")
rect(g, 2, 5, 13, 5, "E")
for x in range(3, 13, 2):
    put(g, x, 4, "L"); put(g, x, 3, "l") if x % 4 == 1 else None
add("location_rooftop_farms", g, {"S": "#8a90a8", "H": "#b8bed0", "s": "#5a6078", "Y": "#ffe07a", "d": "#3a3448", "E": "#6e4630",
                                  "L": "#8ade5a", "l": "#4ea03c"})

# Cloud Terraces: stepped farm terraces high up, clouds drifting over the top of them.
g = blank()
for x0, y0 in ((8, 6), (5, 8), (2, 10), (1, 12)):
    rect(g, x0, y0, 14, y0, "G")
    rect(g, x0, y0 + 1, 14, y0 + 1, "E")
    for x in range(x0, 15, 2):
        put(g, x, y0, "g")
rect(g, 1, 14, 14, 14, "e")
for cx, cy, r in ((3.5, 6, 2.2), (6.5, 5.2, 2.6), (9.5, 6.2, 1.9)):  # front cloud over the upper terraces
    fill(g, lambda x, y, cx=cx, cy=cy, r=r: math.hypot(x - cx, y - cy) <= r and y <= 7, "C")
for cx, cy, r in ((11.5, 2.6, 1.7), (13.5, 3, 1.5)):  # a small cloud higher up
    fill(g, lambda x, y, cx=cx, cy=cy, r=r: math.hypot(x - cx, y - cy) <= r and y <= 3.6, "C")
for x in range(N):
    for y in range(N):
        if g[y][x] == "C" and (y + 1 >= N or g[y + 1][x] != "C"):
            put(g, x, y, "c")
add("location_cloud_terraces", g, {"C": "#ffffff", "c": "#b8cce8", "G": "#8ad05a", "g": "#5aa03c", "E": "#8a5a3a", "e": "#5a3826"})

# Windmill Fields: a white windmill with four sails over a field.
g = blank()
for y in range(6, 14):  # tower, tapering up
    half = 1.5 + (y - 6) * 0.3
    for x in range(N):
        if abs(x - 7.5) <= half:
            put(g, x, y, "W" if x < 7.5 else "w")
rect(g, 7, 11, 8, 13, "d")
for i in range(1, 6):  # four lattice sails: a spar plus a canvas strip
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x = round(7.5 + sx * i * 0.95 - 0.5 * (sx < 0)); y = round(5 + sy * i * 0.95 - 0.5 * (sy < 0))
        put(g, x, y, "T")
        if i >= 2:
            put(g, x + sx * -1 if sy < 0 else x, y if sy < 0 else y - sy, "C")
put(g, 7, 5, "k"); put(g, 8, 5, "k")
rect(g, 1, 14, 14, 14, "G")
add("location_windmill_fields", g, {"C": "#e8dcc4", "W": "#f4f0e8", "w": "#c8beb0", "d": "#6a4a30", "T": "#b07a48", "k": "#3a2a30", "G": "#5aa03c"})

# Stardew Fields: tall sunflowers with a little sparkle.
g = blank()
for x, top, h in ((4, 4, 10), (10, 2, 12)):
    line(g, x, top + 2, x, 14, "L")
    put(g, x - 1, top + 6, "L"); put(g, x + 1, top + 8, "l")
    fill(g, lambda px, py, x=x, top=top: math.hypot(px - x, py - top) <= 2.3, "Y")
    fill(g, lambda px, py, x=x, top=top: math.hypot(px - x, py - top) <= 1.1, "B")
    put(g, x + 1, top + 1, "y"); put(g, x + 2, top, "y")
put(g, 13, 7, "W"); put(g, 7, 2, "W"); put(g, 7, 9, "y")
add("location_stardew_fields", g, {"L": "#5cb048", "l": "#3a8a3a", "Y": "#ffd84a", "y": "#e0a020", "B": "#6a3a20", "W": "#ffffff"})

# Comet Orchards: a shiny red apple with a leaf, trailing a comet tail.
g = blank()
for y in range(N):
    for x in range(N):
        t_ = ((x - 5) - (y - 10)) / math.sqrt(2)
        p_ = abs((x - 5) + (y - 10)) / math.sqrt(2)
        if 3 <= t_ <= 11.5 and p_ <= 3.2 - t_ * 0.25:
            put(g, x, y, "M" if p_ < 0.8 else "c" if p_ < 1.7 else "C")
APPLE = [".RR.RR.", "RRRRRRR", "RRRRRRR", "RRRRRRR", "RRRRRRR", "RRRRRRR", ".RRRRR.", "..RRR.."]
apple = lambda x, y: 0 <= y - 6 < len(APPLE) and 0 <= x - 2 < 7 and APPLE[y - 6][x - 2] == "R"
blob(g, apple, 4, 8.5, 4.2, "HRrd")
put(g, 3, 8, "W"); put(g, 4, 7, "H")
put(g, 5, 5, "b"); put(g, 5, 6, "b"); put(g, 6, 4, "L"); put(g, 7, 4, "L"); put(g, 7, 5, "l")
add("location_comet_orchards", g, {"C": "#5a8ae8", "c": "#a8d0ff", "M": "#ffffff", "H": "#ff9a8a", "R": "#e03a3a", "r": "#a02030",
                                   "d": "#6a1424", "W": "#ffe8e0", "b": "#6a4428", "L": "#7ad050", "l": "#3c8a34"})

# Pale Gardens: three pale tulips, ghostly white with soft green stems.
g = blank()
for x, top in ((3, 5), (7, 3), (11, 6)):
    line(g, x, top + 3, x, 14, "L")
    rect(g, x - 1, top, x + 1, top + 2, "W")
    put(g, x - 1, top - 1, "W"); put(g, x + 1, top - 1, "w"); put(g, x + 1, top + 1, "w"); put(g, x + 1, top + 2, "w"); put(g, x, top + 2, "p")
put(g, 6, 11, "l"); put(g, 10, 12, "l")
add("location_pale_gardens", g, {"W": "#f6f4ff", "w": "#c8c4e0", "p": "#e8c8f0", "L": "#9ac8a0", "l": "#6a9a7a"})

# Dreamless Furrows: a plowed field running off to a dark horizon, a big sleepy "Z z" drifting above.
g = blank()
BAND = {8: 0, 9: 1, 10: 2, 11: 2, 12: 3, 13: 3, 14: 4}  # furrows get thicker toward us
for y, b in BAND.items():
    half = 5 + (y - 8) * 0.4
    for x in range(N):
        if abs(x - 7.5) <= half and 1 <= x <= 14:
            put(g, x, y, "E" if b % 2 == 0 else "e")
for x, y in ((4, 3), (11, 2)):  # two bright stars and a few faint ones over the dark field
    put(g, x, y, "Z")
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        put(g, x + dx, y + dy, "z")
for x, y in ((8, 5), (1, 6), (14, 6), (7, 1)):
    put(g, x, y, "y")
add("location_dreamless_furrows", g, {"E": "#8a7aa0", "e": "#2e2440", "Z": "#e8e0ff", "z": "#a898d8", "y": "#6a5a9a"})

out = ["# Farming location icons (location_<id>). Generated by a script; approved by the owner.\n"]
for name, (g, pal) in sprites.items():
    used = {c for row in g for c in row if c != "."}
    pal = {k: v for k, v in pal.items() if k in used}
    out += [f"[{name}]", 'kind = "free"', "outline = true",
            "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items()) + " }", "rows = ["]
    out += [f'  "{"".join(r)}",' for r in g]
    out.append("]\n")
open(sys.argv[1], "w").write("\n".join(out))
