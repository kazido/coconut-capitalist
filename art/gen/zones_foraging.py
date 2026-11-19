"""Foraging location icons (location_<id>). 16x16, free, plum outline, light top-left. argv: out.toml scratch_dir"""
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


def union(*ms):
    return lambda x, y: any(m(x, y) for m in ms)


def fill(g, mask, c):
    for y in range(N):
        for x in range(N):
            if mask(x, y):
                put(g, x, y, c)


def trunk(g, x0, x1, y0, y1, light="B", dark="b"):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(g, x, y, light if x == x0 else dark)


def canopy(g, mask, ramp="Hmsd", cx=7.5, cy=6, r=6, texture=True):
    for y in range(N):
        for x in range(N):
            if not mask(x, y):
                continue
            l = -((x - cx) + (y - cy)) / (math.sqrt(2) * r)
            i = 0 if l > 0.5 else 1 if l > -0.05 else 2 if l > -0.6 else 3
            if not mask(x + 1, y + 1) and i < 2:
                i = 2
            if texture and i < 3 and (x * 5 + y * 3) % 7 == 0:
                i += 1
            put(g, x, y, ramp[i])


BARK = {"B": "#9a6a44", "b": "#5e3c2c"}

# Slimewood Thicket: a clump of slime-capped mushrooms.
g = blank()
for cx, cy, r, sx in ((5, 7, 3.4, 4), (11, 9, 2.6, 10), (8, 11.5, 2, 7)):
    trunk(g, sx, sx + 1, int(cy), 13, "W", "w")
    canopy(g, lambda x, y, cx=cx, cy=cy, r=r: math.hypot((x - cx) / 1.2, y - cy) <= r and y <= cy + 0.3, "GgSs", cx, cy - 1, r, False)
for x, y in ((4, 5), (6, 6), (10, 8), (7, 10)):
    put(g, x, y, "D")  # slime spots
put(g, 3, 9, "S"); put(g, 3, 10, "S")  # a drip
add("location_slimewood_thicket", g, {"G": "#b4ff8a", "g": "#6ad85a", "S": "#3ca04a", "s": "#226a34", "D": "#e8ffd8",
                                      "W": "#f0e8d8", "w": "#c0b098"})

# Jellybough Grove: a tree hung with wobbly purple jelly fruit.
g = blank()
trunk(g, 7, 8, 10, 14)
canopy(g, union(circ(7.5, 6, 5), circ(4, 8, 2.8), circ(11, 8, 2.8)), "Hmsd")
for x, y in ((3, 7), (6, 3), (9, 3), (12, 7), (5, 9), (10, 9), (7, 6), (2, 10), (13, 10)):
    put(g, x, y, "J"); put(g, x, y + 1, "j"); put(g, x - 1, y, "K")
add("location_jellybough_grove", g, {"H": "#a8e070", "m": "#6cb048", "s": "#407a34", "d": "#244a26", "J": "#e8a0ff", "j": "#9a48d0",
                                     "K": "#fbe0ff", **BARK})

# Duskthorn Scrub: a big dusk sun sinking behind a tangle of thorny branches.
g = blank()
fill(g, lambda x, y: math.hypot(x - 7.5, y - 10) <= 6.2 and y <= 12, "O")
fill(g, lambda x, y: math.hypot(x - 7.5, y - 10) <= 4.2 and y <= 12, "o")
fill(g, lambda x, y: math.hypot(x - 7.5, y - 10) <= 2.2 and y <= 12, "W")
branches = ((3, 13, 4, 6), (7, 13, 6, 4), (11, 13, 12, 5))
for x0, y0, x1, y1 in branches:
    line(g, x0, y0, x1, y1, "T")
for x0, y0, x1, y1 in branches:  # thorns: short spurs off each branch, alternating sides
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(3, n, 3):
        x = round(x0 + (x1 - x0) * i / n); y = round(y0 + (y1 - y0) * i / n)
        put(g, x + (1 if i % 4 else -1), y, "T")
for x, y in ((4, 6), (6, 4), (12, 5)):
    put(g, x, y, "t")
rect(g, 1, 13, 14, 13, "T")
add("location_duskthorn_scrub", g, {"O": "#ff8a5a", "o": "#ffb870", "W": "#ffe8a0", "T": "#3a2440", "t": "#c05aa0"})

# Oasis Palms: two palm trees on a sandy rise.
g = blank()
fill(g, ell(7.5, 14.5, 7, 2.6), "Y")
fill(g, lambda x, y: ell(7.5, 14.5, 7, 2.6)(x, y) and x > 9, "y")


def palm(g, bx, by, tx, ty):
    line(g, bx, by, tx, ty + 1, "B"); line(g, bx + 1, by, tx + 1, ty + 1, "b")
    for dx, dy in ((-3, 1), (-2, 0), (-1, -1), (0, -1), (1, -1), (2, 0), (3, 1), (-3, 2), (3, 2), (1, 0), (-1, 0)):
        put(g, tx + dx, ty + dy, "P" if dx <= 0 else "p")
    put(g, tx, ty + 1, "c"); put(g, tx + 1, ty + 1, "c")


palm(g, 4, 12, 4, 4)
palm(g, 10, 12, 11, 2)
add("location_oasis_palms", g, {"Y": "#ffe0a0", "y": "#d8b068", "P": "#7ed04c", "p": "#3c8c34", "c": "#7a4a2a", "B": "#b07a48", "b": "#6a4428"})

# Rustleaf Woods: a tree in rust-orange autumn leaves, one leaf falling.
g = blank()
trunk(g, 6, 8, 10, 14)
canopy(g, union(circ(7.5, 6, 5.2), circ(4, 7.5, 3.2), circ(11, 7.5, 3.2)), "HmsD", 7.5, 6, 6)
put(g, 13, 12, "m"); put(g, 12, 13, "s")
add("location_rustleaf_woods", g, {"H": "#ffc060", "m": "#e07a30", "s": "#a84a24", "D": "#6a2a1c", **BARK})

# Cogbark Copse: a tree with a brass gear set into its trunk.
g = blank()
trunk(g, 6, 9, 8, 14, "B", "b")
canopy(g, union(circ(7.5, 5, 4.6), circ(4, 6.5, 2.6), circ(11, 6.5, 2.6)), "Hmsd", 7.5, 5, 5.5)
teeth = [(7, 8, 8, 8), (7, 13, 8, 13), (5, 10, 5, 11), (10, 10, 10, 11)]
fill(g, lambda x, y: math.hypot(x - 7.5, y - 10.5) <= 1.9 or any(a <= x <= c and b <= y <= d for a, b, c, d in teeth), "Y")
for y in range(N):
    for x in range(N):
        if g[y][x] == "Y" and (x - 7.5) + (y - 10.5) > 0.5:
            put(g, x, y, "y")
fill(g, lambda x, y: math.hypot(x - 7.5, y - 10.5) <= 0.8, "k")
add("location_cogbark_copse", g, {"H": "#a8d870", "m": "#62a848", "s": "#3a7436", "d": "#224a26", "Y": "#e0a858", "y": "#9a6428", "k": "#2a1a14", "B": "#8a8a98", "b": "#55556a"})

# Canal Park Arboretum: a clipped round tree in a stone planter by the water.
g = blank()
trunk(g, 7, 8, 8, 10)
canopy(g, circ(7.5, 5, 4), "Hmsd", 7.5, 5, 4.5, False)
rect(g, 3, 10, 12, 12, "S"); rect(g, 3, 10, 12, 10, "W"); rect(g, 12, 11, 12, 12, "s")
rect(g, 1, 13, 14, 14, "A"); put(g, 3, 13, "a"); put(g, 4, 13, "a"); put(g, 11, 14, "a")
add("location_canal_park_arboretum", g, {"H": "#a8e070", "m": "#5cb048", "s": "#367a36", "d": "#1e4a26", "S": "#c0b8b0", "W": "#ece6dc",
                                         "A": "#3a8ad0", "a": "#c8ecff", **BARK})

# Rooftop Gardens: a red roof ridge with potted flowers on top.
g = blank()
for y in range(8, 15):
    for x in range(N):
        if abs(x - 7.5) <= 7 - max(0, 10 - y) * 0.0 and y >= 9:
            put(g, x, y, "R" if (x + y) % 3 else "r")
rect(g, 0, 8, 15, 8, ".")
rect(g, 1, 8, 14, 8, "q")
for px in (2, 7, 12):
    rect(g, px, 6, px + 1, 7, "T"); put(g, px + 1, 7, "t")
    put(g, px, 5, "L"); put(g, px + 1, 4, "L")
for (x, y, c) in ((2, 3, "F"), (3, 3, "F"), (2, 4, "f"), (7, 2, "Y"), (8, 2, "Y"), (8, 3, "y"), (12, 3, "F"), (13, 3, "F"), (13, 4, "f")):
    put(g, x, y, c)
put(g, 7, 5, "L"); put(g, 8, 4, "L"); put(g, 12, 5, "L"); put(g, 13, 5, "L")
add("location_rooftop_gardens", g, {"R": "#d86a50", "r": "#a84038", "q": "#6a2a30", "T": "#c87a48", "t": "#8a4a2c", "L": "#5cb048",
                                    "F": "#ff7ab0", "f": "#c0407a", "Y": "#ffe05a", "y": "#d0a020"})

# Cloudroot Canopy: a tree whose crown is a cloud, its roots dangling into open sky.
g = blank()
for cx, cy, r in ((4, 5.5, 2.8), (8, 4.2, 3.4), (12, 5.8, 2.6)):
    fill(g, circ(cx, cy, r), "C")
for x in range(N):
    for y in range(N):
        if g[y][x] == "C" and (y + 1 >= N or g[y + 1][x] == "."):
            put(g, x, y, "c")
for x, y in ((3, 3), (4, 3), (7, 2), (8, 2), (11, 4)):
    put(g, x, y, "W")
trunk(g, 7, 8, 8, 10)
for x0, x1, y1 in ((7, 4, 14), (8, 11, 14), (7, 7, 13)):
    line(g, x0, 11, x1, y1, "b")
add("location_cloudroot_canopy", g, {"C": "#eef4ff", "c": "#a8c0e4", "W": "#ffffff", **BARK})

# Windbloom Meadow: three flowers leaning with the wind, curling gusts sweeping across.
g = blank()
for bx, tx, ty, c in ((3, 5, 7, "F"), (7, 9, 5, "Y"), (11, 13, 8, "P")):
    line(g, bx, 14, tx, ty + 2, "L")
    for dx, dy in ((0, 0), (1, 0), (0, -1), (-1, 0), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1)):
        if abs(dx) + abs(dy) < 2:
            put(g, tx + dx, ty + dy, c)
    put(g, tx, ty, "o")
for pts in (((1, 3), (2, 3), (3, 3), (4, 3), (5, 2), (5, 1), (4, 1)), ((8, 10), (9, 10), (10, 10), (11, 10), (12, 9), (12, 8), (11, 8)),
            ((9, 2), (10, 2), (11, 2), (12, 2), (13, 3))):
    for x, y in pts:
        put(g, x, y, "w")
rect(g, 1, 14, 14, 14, "G")
add("location_windbloom_meadow", g, {"L": "#5cb048", "G": "#3a8a3a", "F": "#ff8ab0", "Y": "#ffe05a", "P": "#b88aff", "o": "#fff6e0",
                                     "w": "#e0f0ff"})

# Starlit Orchard: a row of round orchard trees on a night hill, stars above.
g = blank()
fill(g, ell(7.5, 15.5, 8.5, 3.4), "G")
fill(g, lambda x, y: ell(7.5, 15.5, 8.5, 3.4)(x, y) and x > 9, "g")
for cx, cy in ((3, 9), (8, 8), (12.5, 9.5)):
    trunk(g, int(cx), int(cx), int(cy) + 2, 13, "B", "b")
    canopy(g, circ(cx, cy - 0.3, 2.6), "Hmsd", cx, cy, 2.8, False)
for x, y in ((2, 2), (12, 3)):
    put(g, x, y, "W")
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        put(g, x + dx, y + dy, "y")
for x, y in ((7, 1), (9, 4), (5, 4), (14, 1)):
    put(g, x, y, "y")
add("location_starlit_orchard", g, {"G": "#2e4a6a", "g": "#1e3048", "H": "#6aa86a", "m": "#3e7a52", "s": "#285640", "d": "#18382c",
                                    "Y": "#fff6a0", "W": "#ffffff", "y": "#ffe27a", "B": "#6a5a7a", "b": "#3e3450"})

# Moonbark Forest: a tall silver-barked tree with a teal crown under a crescent moon.
g = blank()
for y in range(N):
    for x in range(N):
        if math.hypot(x - 3.2, y - 3.2) <= 2.4 and math.hypot(x - 4.3, y - 2.4) > 1.9:
            put(g, x, y, "M")
put(g, 6, 1, "y"); put(g, 1, 7, "y")
trunk(g, 8, 9, 8, 14, "W", "w")
put(g, 8, 10, "k"); put(g, 9, 12, "k"); put(g, 7, 14, "w"); put(g, 10, 14, "w")
canopy(g, union(circ(9.5, 5, 3.8), circ(12, 7.5, 2.4), circ(7, 7, 2.2)), "Hmsd", 9.5, 5, 4.5)
add("location_moonbark_forest", g, {"M": "#fff2b0", "y": "#ffe27a", "W": "#f4f4ff", "w": "#a8a8c8", "k": "#5a5a78",
                                    "H": "#a8e0d8", "m": "#5aa8a8", "s": "#357480", "d": "#1e4450"})

# Hollow Wood: a fallen hollow log, the hollow end facing us.
g = blank()
rect(g, 1, 7, 10, 13, "B")
rect(g, 1, 7, 10, 7, "H"); rect(g, 1, 12, 10, 13, "b")
for x in (3, 6, 9):
    put(g, x, 9, "b"); put(g, x - 1, 10, "b")
fill(g, ell(11.5, 10, 3, 3.6), "R")
fill(g, ell(11.5, 10, 2, 2.6), "k")
put(g, 4, 6, "L"); put(g, 5, 5, "L"); put(g, 6, 6, "l")  # a sprout on top
add("location_hollow_wood", g, {"B": "#8a5a3a", "H": "#b8845a", "b": "#5a3826", "R": "#d8a870", "k": "#1c120e", "L": "#7ad050", "l": "#3c8a34"})

# The Withered Rift: a dead grey tree over a glowing violet crack in the ground.
g = blank()
line(g, 7, 13, 7, 5, "W"); line(g, 8, 13, 8, 6, "w")
for x0, y0, x1, y1 in ((7, 7, 4, 4), (4, 4, 3, 2), (8, 8, 11, 5), (11, 5, 12, 3), (7, 5, 6, 2), (11, 5, 13, 5)):
    line(g, x0, y0, x1, y1, "W" if x1 < x0 else "w")
rect(g, 1, 13, 14, 14, "G")
for x, y in ((1, 13), (2, 13), (3, 14), (4, 14), (5, 13), (6, 14), (9, 14), (10, 13), (11, 13), (12, 14), (13, 14), (14, 13)):
    put(g, x, y, "V")  # a jagged crack across the ground
for x, y in ((2, 12), (5, 12), (10, 12), (13, 12), (11, 11)):
    put(g, x, y, "v")  # violet glow rising
add("location_the_withered_rift", g, {"W": "#b8b0b8", "w": "#7a707a", "G": "#4a4048", "V": "#e8b0ff", "v": "#9a5ad8"})

out = ["# Foraging location icons (location_<id>). Generated by a script; approved by the owner.\n"]
for name, (g, pal) in sprites.items():
    used = {c for row in g for c in row if c != "."}
    pal = {k: v for k, v in pal.items() if k in used}
    out += [f"[{name}]", 'kind = "free"', "outline = true",
            "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items()) + " }", "rows = ["]
    out += [f'  "{"".join(r)}",' for r in g]
    out.append("]\n")
open(sys.argv[1], "w").write("\n".join(out))
