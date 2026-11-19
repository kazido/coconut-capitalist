"""Fishing location icons (location_<id>). 16x16, free, plum outline, light top-left. argv: out.toml scratch_dir"""
import math
import sys

sys.path.insert(0, sys.argv[2])
_argv = sys.argv[:]
sys.argv = [sys.argv[0], sys.argv[2] + "/_ui_tmp.toml"]  # ui_icons writes its own toml on import; keep it out of the way
from ui_icons import N, blank, put, rect, line, blob  # noqa: E402
sys.argv = _argv

sprites = {}


def add(name, g, pal):
    sprites[name] = (g, pal)


def ell(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def fill(g, mask, c):
    for y in range(N):
        for x in range(N):
            if mask(x, y):
                put(g, x, y, c)


def water(g, mask, cx, cy, ramp="WBbd"):
    """Water seen from above: lit toward the viewer, a darker far bank edge, two shine streaks."""
    for y in range(N):
        for x in range(N):
            if mask(x, y):
                edge = not mask(x, y - 1)
                put(g, x, y, ramp[3] if edge else ramp[2] if y < cy - 0.5 else ramp[1])


def shine(g, pts, c="W"):
    for x, y in pts:
        if g[y][x] != ".":
            put(g, x, y, c)


def star(g, x, y, c="W", arm="w"):
    put(g, x, y, c)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        put(g, x + dx, y + dy, arm)


# Slime Pond: a murky green pond with cattails on the bank and a lily pad with a pink flower.
g = blank()
fill(g, ell(8.5, 9.5, 6.6, 4.6), "q")  # muddy bank rim
water(g, ell(8.5, 9.7, 5.8, 3.8), 8.5, 9.7, "WSsd")
for x, top in ((1, 3), (4, 2)):  # cattails: a stem with a fat 2px brown head
    line(g, x, top + 4, x, 13, "L")
    rect(g, x, top, x + 1, top + 3, "C"); put(g, x + 1, top + 1, "c"); put(g, x + 1, top + 2, "c"); put(g, x + 1, top + 3, "c")
    put(g, x, top - 1, "L")
put(g, 3, 11, "l"); put(g, 1, 12, "l"); put(g, 5, 12, "l")  # reed leaves
fill(g, lambda x, y: math.hypot((x - 10.5) / 1.4, y - 10) <= 1.6 and not (x == 12 and y == 10), "P")
put(g, 10, 9, "F"); put(g, 11, 9, "F")
shine(g, ((7, 11), (8, 11), (12, 12), (6, 8)))
add("location_pond", g, {"q": "#5a4a2c", "W": "#d8ffcc", "S": "#6ac87a", "s": "#3e9a5a", "d": "#24603e", "L": "#4e9a3c",
                         "l": "#7ac850", "C": "#8a5a34", "c": "#5a3820", "P": "#2e8a3a", "F": "#ff9ad0"})

# Slimeflow River: a round patch of meadow with a green river winding through it.
g = blank()
blob(g, ell(7.5, 7.5, 6.8, 6.8), 6.5, 6.5, 6.8, "GGgq")
river = lambda x, y: ell(7.5, 7.5, 6.8, 6.8)(x, y) and abs((x - 7.5) + 2.2 * math.sin((y - 7.5) / 2.4) - (y - 7.5) * 0.15) <= 1.9
for y in range(N):
    for x in range(N):
        if river(x, y):
            put(g, x, y, "S" if (x - y) % 4 else "W")
for y in range(N):  # the right bank of the river in shadow
    for x in range(N):
        if river(x, y) and not river(x + 1, y):
            put(g, x, y, "s")
add("location_river", g, {"G": "#9ad85a", "g": "#5aa03c", "q": "#356a2c", "W": "#e0f6ff", "S": "#3a9ae8", "s": "#1e5aa8"})

# Mirage Oasis: a sand dune ring round a turquoise pool, a little palm, heat shimmer above.
g = blank()
blob(g, ell(7.5, 10, 7, 4.4), 6.5, 9, 7, "YYyq")
water(g, ell(6.5, 10.5, 4.2, 2.2), 6.5, 10.5, "WTtd")
line(g, 11, 11, 12, 4, "B"); line(g, 12, 11, 13, 4, "b")
for x, y in ((9, 4), (10, 3), (11, 2), (12, 2), (13, 2), (14, 3), (12, 3), (13, 3), (9, 5), (14, 4), (15, 5), (10, 4), (11, 3)):
    put(g, x, y, "P" if x < 12 else "p")
put(g, 12, 4, "c"); put(g, 13, 4, "c")
add("location_reef", g, {"Y": "#ffe0a0", "y": "#e0b060", "q": "#a8783c", "W": "#e8fff8", "T": "#4ae0d0", "t": "#22a8b0",
                         "d": "#18708a", "B": "#a8743c", "b": "#6a4428", "P": "#7ed04c", "p": "#3c8c34", "c": "#7a4a2a"})

# Sandglass Cenote: an hourglass; the top bulb trickles sand, the bottom bulb holds deep blue water.
g = blank()
rect(g, 3, 1, 12, 1, "T"); rect(g, 3, 14, 12, 14, "T"); rect(g, 3, 2, 12, 2, "t"); rect(g, 3, 13, 12, 13, "t")  # wooden caps
line(g, 3, 3, 3, 12, "t"); line(g, 12, 3, 12, 12, "t")  # posts
for y in range(3, 13):
    half = 1 + abs(y - 7.5) * 0.85
    for x in range(N):
        if abs(x - 7.5) <= half:
            if y < 7.5:
                put(g, x, y, "Y" if y >= 5 else "G")  # sand settling in the top bulb
            else:
                put(g, x, y, "B" if x < 7.5 else "b" if y < 11 else "d")
for x0 in (4, 11):  # glass edges
    pass
put(g, 7, 7, "Y"); put(g, 8, 8, "y")  # trickle
put(g, 6, 10, "W"); put(g, 9, 11, "F"); put(g, 10, 11, "F")  # glint and a tiny fish
add("location_deep_sea", g, {"T": "#c8905a", "t": "#7a4c30", "G": "#e8f4ff", "Y": "#f4d890", "y": "#c8a050", "B": "#3a8ae0",
                             "b": "#2a5ab8", "d": "#1a3478", "W": "#c8ecff", "F": "#ffb040"})

# Oilslick Canal: dark canal water between brick walls, a rainbow oil sheen swirling on it.
g = blank()
for y in range(2, 14):
    for x in range(1, 15):
        wall = x <= 3 or x >= 12
        if wall:
            put(g, x, y, "H" if (y % 3 == 0) else "m" if x <= 3 else "s")
        else:
            put(g, x, y, "k" if (x + y) % 4 else "q")
for x, y, c in ((6, 5, "P"), (7, 5, "C"), (8, 6, "Y"), (8, 7, "P"), (7, 8, "C"), (6, 8, "Y"), (5, 7, "P"), (9, 9, "C"), (6, 11, "Y"), (7, 11, "P")):
    put(g, x, y, c)
add("location_oilslick_canal", g, {"H": "#a8a0a0", "m": "#7a7070", "s": "#4e4646", "k": "#1c1a24", "q": "#2c2a3a",
                                   "P": "#d070f0", "C": "#5af0e0", "Y": "#fff07a"})

# Rustwater Reservoir: a riveted rusty tank brimming with orange-brown water, a valve wheel on the side.
g = blank()
rect(g, 2, 6, 11, 13, "R"); rect(g, 2, 6, 2, 13, "H"); rect(g, 11, 6, 11, 13, "r"); rect(g, 3, 13, 11, 13, "r")
for x in (4, 7, 10):
    put(g, x, 9, "q"); put(g, x, 12, "q")
fill(g, ell(6.5, 5.6, 5, 1.6), "O")
fill(g, ell(6.5, 5.9, 3.6, 0.9), "o")
rect(g, 12, 8, 14, 8, "V"); rect(g, 12, 9, 14, 9, "v")  # outflow pipe
put(g, 14, 11, "o"); put(g, 14, 13, "O")  # drips
add("location_rustwater_reservoir", g, {"R": "#c0683a", "H": "#e8905a", "r": "#7a3a20", "q": "#ffc890", "O": "#c88a3c",
                                        "o": "#8a5424", "V": "#b8c2d0", "v": "#6a7486"})

# Cadrega Canals: a gondola on canal water beside a striped mooring pole.
g = blank()
for y in range(2, 11):
    put(g, 4, y, "R" if (y // 2) % 2 else "W"); put(g, 5, y, "r" if (y // 2) % 2 else "w")
put(g, 4, 1, "Y"); put(g, 5, 1, "Y")
rect(g, 1, 11, 14, 13, "B"); rect(g, 1, 11, 14, 11, "d")
rect(g, 3, 9, 12, 9, "Y"); rect(g, 3, 10, 12, 10, "k"); rect(g, 4, 11, 11, 11, "k")  # hull with a gold trim
put(g, 13, 9, "k"); put(g, 13, 8, "k"); put(g, 14, 7, "k"); put(g, 14, 6, "S")  # curved prow with its steel ferro
put(g, 2, 9, "k"); put(g, 2, 8, "k")  # stern
line(g, 9, 3, 9, 8, "T")  # gondolier's oar
shine(g, ((2, 12), (3, 12), (11, 13), (12, 13)))
add("location_cadrega_canals", g, {"R": "#e04040", "r": "#9a2830", "W": "#ffffff", "w": "#c8ccd8", "Y": "#ffd84a", "B": "#3a8ad0",
                                   "d": "#24508a", "k": "#1c1a24", "q": "#3a3648", "S": "#e4ecf6", "T": "#a87048"})

# Grand Harbor: a big steel anchor over waves.
g = blank()
line(g, 7, 2, 7, 11, "A"); line(g, 8, 2, 8, 11, "a")
for y in range(N):
    for x in range(N):
        if 1.2 <= math.hypot(x - 7.5, y - 2.2) <= 2.1 and y <= 2:
            put(g, x, y, "A")
rect(g, 4, 4, 11, 4, "A"); rect(g, 4, 5, 11, 5, "a")
for y in range(N):
    for x in range(N):
        d = math.hypot(x - 7.5, y - 6.5)
        if 4.4 <= d <= 5.6 and y >= 9:
            put(g, x, y, "A" if x < 8 else "a")
put(g, 2, 9, "A"); put(g, 13, 9, "a"); put(g, 1, 10, "A"); put(g, 14, 10, "a")
for x in range(1, 15):
    put(g, x, 13, "B")
    put(g, x, 12, "W" if x % 4 in (1, 2) else "B" if x % 4 == 3 else ".")
add("location_grand_harbor", g, {"A": "#e4ecf6", "a": "#8a96ac", "B": "#3a8ad0", "W": "#c8ecff"})

# Cloud Pools: a fluffy cloud holding a small pool on top.
g = blank()
for cx, cy, r in ((4, 10, 2.8), (8, 9, 3.4), (12, 10.4, 2.6)):
    fill(g, lambda x, y, cx=cx, cy=cy, r=r: math.hypot(x - cx, y - cy) <= r and y <= 13, "C")
for x in range(1, 15):
    for y in range(N):
        if g[y][x] == "C" and (y + 1 >= N or g[y + 1][x] == "."):
            put(g, x, y, "c")
water(g, ell(8, 7.2, 4.6, 1.8), 8, 7.2, "WBbd")
shine(g, ((6, 7), (7, 7)))
add("location_cloud_pools", g, {"C": "#ffffff", "c": "#b8cce8", "W": "#e8f8ff", "B": "#6ac8f8", "b": "#4aa8e8", "d": "#2a78c0"})

# Skyfall Lake: a floating sky island spilling a waterfall into a lake below.
g = blank()
rect(g, 2, 2, 9, 2, "G"); rect(g, 2, 3, 9, 3, "g")
for y, (x0, x1) in zip(range(4, 8), ((2, 9), (3, 8), (4, 7), (5, 6))):
    for x in range(x0, x1 + 1):
        put(g, x, y, "R" if x < (x0 + x1) / 2 else "r")
for y in range(2, 12):
    put(g, 10, y, "W"); put(g, 11, y, "B")
water(g, ell(8.5, 12.2, 6, 1.9), 8.5, 12.2, "WBbd")
for x, y in ((9, 10), (12, 10), (8, 11), (13, 11)):
    put(g, x, y, "W")
add("location_skyfall_lake", g, {"G": "#8ad05a", "g": "#4e9a3c", "R": "#a8805a", "r": "#6a4a34", "W": "#e8f8ff", "B": "#6ac8f8",
                                 "b": "#3a98e0", "d": "#2a68b0"})

# Moonwell: an old stone well glowing with moonlight, a beam rising to a crescent moon among stars.
g = blank()
for y in range(N):  # crescent moon, top right
    for x in range(N):
        if math.hypot(x - 11, y - 3.4) <= 2.6 and math.hypot(x - 12.4, y - 2.6) > 2.1:
            put(g, x, y, "M")
for x, y in ((3, 2), (6, 1), (2, 5)):
    put(g, x, y, "y")
for y in range(3, 9):  # beam of light rising from the water
    for x in range(5, 10):
        if abs(x - 7.5) <= 1 + (8 - y) * 0.25 and g[y][x] == ".":
            put(g, x, y, "L" if abs(x - 7.5) < 1 else "l")
rect(g, 2, 9, 13, 13, "S")  # well wall
for y in range(9, 14):
    for x in range(2, 14):
        if (x + (y % 2) * 2) % 4 == 0 or y == 13:
            put(g, x, y, "s")
rect(g, 2, 9, 2, 13, "H"); rect(g, 13, 9, 13, 13, "q")
fill(g, ell(7.5, 9, 5.2, 1.3), "G")  # glowing water surface
fill(g, ell(7.5, 9, 3, 0.7), "W")
add("location_moonwell", g, {"M": "#fff2b0", "y": "#ffe27a", "L": "#eaf6ff", "l": "#9ad0ff", "S": "#8a84a8", "s": "#5a5478",
                             "H": "#b8b2d0", "q": "#3a3456", "G": "#7ae0ff", "W": "#ffffff"})

# Starlit Stream: a night-blue stream with stars glinting on it.
g = blank()
stream = lambda x, y: 1 <= y <= 14 and abs((x - 7.5) - 2.6 * math.sin((y - 7.5) / 2.6)) <= 3.2
for y in range(N):
    for x in range(N):
        if stream(x, y):
            put(g, x, y, "B" if not stream(x - 1, y) else "d" if not stream(x + 1, y) else "b")
star(g, 6, 4, "W", "y"); star(g, 9, 10, "W", "y"); put(g, 5, 12, "y"); put(g, 10, 6, "y")
add("location_starlit_stream", g, {"B": "#4a5ab8", "b": "#2a2e78", "d": "#161a48", "W": "#ffffff", "y": "#ffe27a"})

# Black Tide: a black wave curling over (hollow open underneath), foam along its crest, a black sea below.
TIDE = [
    "................",
    "......FFFF......",
    "....FFkkkkFF....",
    "...Fkkkkkkkkf...",
    "..Fkkqkkqqqkkf..",
    "..fkkkq...qkkf..",
    ".Fkkkq.....fkf..",
    ".fkqkq......f...",
    ".fkkkkq.........",
    ".kkkqkkq........",
    ".kkkkkkkqffFf...",
    ".kkqkkkkkqkkkkk.",
    ".qkkkkqkkkkkqkq.",
    "..qqqqqqqqqqqq..",
    "................",
    "................",
]
g = [list(r) for r in TIDE]
add("location_black_tide", g, {"k": "#0e0e18", "q": "#2a2a48", "F": "#eef2fa", "f": "#8a94b0"})

# The Bottomless: a whirlpool spiralling into black, a tentacle rising out of it.
g = blank()
for y in range(N):
    for x in range(N):
        dx, dy = x - 7.5, (y - 9) * 1.5
        r = math.hypot(dx, dy)
        if r <= 7:
            a = math.atan2(dy, dx)
            band = (a + r * 0.9) % (2 * math.pi) < math.pi
            put(g, x, y, "k" if r < 1.8 else ("B" if band else "b") if r > 3.5 else ("b" if band else "d"))
for x, y in ((8, 9), (9, 9), (9, 8), (10, 8), (10, 7), (11, 7), (11, 6), (12, 6), (11, 5), (12, 5), (11, 4), (12, 4), (10, 3), (11, 3), (9, 3), (9, 4)):
    put(g, x, y, "T" if x <= 10 or y <= 3 else "t")
for x, y in ((9, 8), (10, 7), (11, 5)):
    put(g, x, y, "s")
add("location_the_bottomless", g, {"B": "#3a6ab8", "b": "#1e3a78", "d": "#101c44", "k": "#000000", "T": "#c870c0", "t": "#7a3a80",
                                   "s": "#ffc8f0"})

out = ["# Fishing location icons (location_<id>). Generated by a script; approved by the owner.\n"]
for name, (g, pal) in sprites.items():
    used = {c for row in g for c in row if c != "."}
    pal = {k: v for k, v in pal.items() if k in used}
    out += [f"[{name}]", 'kind = "free"', "outline = true",
            "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items()) + " }", "rows = ["]
    out += [f'  "{"".join(r)}",' for r in g]
    out.append("]\n")
open(sys.argv[1], "w").write("\n".join(out))
