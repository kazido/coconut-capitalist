"""Mining location icons (location_mining_<id>? no: location_<id>) and mine types (mine_<id>). 16x16, free, plum outline, light top-left."""
import math
import sys

sys.path.insert(0, sys.argv[2])
from ui_icons import N, blank, put, rect, line, blob  # noqa: E402  (ui_icons only defines helpers + writes on run)

sprites = {}


def add(name, g, pal):
    sprites[name] = (g, pal)


def boulder(g, ramp, cx=7.5, cy=8.5, rx=6.2, ry=5.2):
    m = lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1 and y <= cy + ry - 0.8
    blob(g, m, cx - 1, cy - 1, max(rx, ry), ramp)
    return m


def facets(g, pts, c):
    for x, y in pts:
        put(g, x, y, c)


def star(g, x, y, c="W", arm="w"):
    put(g, x, y, c)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        put(g, x + dx, y + dy, arm)


ROCK = {"H": "#b8aab0", "m": "#857680", "s": "#5a4c58", "d": "#3a3040"}

# Slimy Burrow: an earth mound with a cave mouth, its top coated in slime that drips down in rounded drops.
g = blank()
mound = boulder(g, "HmsD", ry=6)
for y in range(7, 14):
    for x in range(5, 11):
        if ((x - 7.5) / 2.8) ** 2 + ((y - 13) / 5.5) ** 2 <= 1:
            put(g, x, y, "k")
for x in range(N):  # slime coat: the top 2 rows of the mound in every column
    ys = [y for y in range(N) if mound(x, y)]
    if ys:
        for y in ys[:2]:
            put(g, x, y, "G" if x < 8 else "g")
for x, y in ((4, 4), (5, 3), (9, 3)):
    put(g, x, y, "W")  # wet shine
for x, n in ((3, 3), (6, 4), (10, 2), (12, 3)):  # drips with a rounded drop at the end
    ys = [y for y in range(N) if mound(x, y)]
    top = ys[0] + 2
    for y in range(top, top + n):
        put(g, x, y, "g")
    put(g, x, top + n, "G")
add("location_slimy_burrow", g, {"H": "#b08a5a", "m": "#86603c", "s": "#5c3e2a", "D": "#3c281e", "k": "#1c1420",
                                 "G": "#8affb4", "g": "#2ec46a", "W": "#eafff2"})

# Gumdrop Quarry: a sugared gumdrop dome.
g = blank()
dome = lambda x, y: ((x - 7.5) / 6) ** 2 + ((y - 11) / 8.5) ** 2 <= 1 and y <= 13
blob(g, dome, 6.5, 7, 6, "HPpd")
for x, y in ((5, 6), (9, 5), (7, 9), (11, 9), (4, 11), (9, 12), (3, 8), (12, 12), (6, 12)):  # sugar crystals, a shade lighter than the candy under them
    put(g, x, y, {"H": "W", "P": "h", "p": "P", "d": "p"}[g[y][x]])
for y in range(8, 14):
    for x in range(N):
        e = ((x - 7.5) / 2.6) ** 2 + ((y - 13.5) / 5) ** 2
        if e <= 1:
            put(g, x, y, "k" if e <= 0.62 else "d")
add("location_gumdrop_quarry", g, {"k": "#2a0e2a", "W": "#fff0fa", "H": "#ffc8f0", "h": "#ffa8e0", "P": "#f070c8", "p": "#b83c9c", "d": "#702a6c"})

# Duskstone Quarry: stepped violet quarry ledges under a low dusk sun.
g = blank()
for y in range(N):
    for x in range(N):
        d = math.hypot(x - 4.5, y - 4.5)
        if d <= 3:
            put(g, x, y, "O" if d <= 1.6 else "o")
for x0, y0 in ((8, 4), (5, 7), (2, 10)):  # three ledges, each one step lower and wider
    rect(g, x0, y0, 13, y0, "H")
    rect(g, x0, y0 + 1, 13, 13, "m")
    rect(g, x0, y0 + 2, 13, 13, "s")  # riser in shadow under each ledge lip
    rect(g, 13, y0 + 1, 13, 13, "d")
rect(g, 2, 11, 12, 12, "m"); rect(g, 2, 13, 13, 13, "s")
for x, y in ((10, 5), (7, 8), (4, 11), (11, 12)):
    put(g, x, y, "d")  # chisel marks
add("location_duskstone_quarry", g, {"O": "#ffe08a", "o": "#ff8a5a", "H": "#d4c0f0", "m": "#8a72b8", "s": "#5a4688", "d": "#352858"})

# Glassfall Caverns: a cluster of cyan crystals.
g = blank()
def crystal(x0, top, h, w=2):
    for y in range(top, top + h):
        for x in range(x0, x0 + w):
            put(g, x, y, "C" if x == x0 else "c")
    put(g, x0, top - 1, "W")
crystal(7, 2, 12, 2); crystal(4, 6, 8, 2); crystal(10, 5, 9, 2); crystal(2, 10, 4, 2); crystal(12, 9, 5, 2)
rect(g, 1, 14, 14, 14, "d")
add("location_glassfall_caverns", g, {"W": "#ffffff", "C": "#a8f4ff", "c": "#3cb4e0", "d": "#2a5a80"})

# Scrapheap Tunnels: a rusty gear half-buried in scrap.
def gear(g, cx, cy, r, teeth, ramp, hole=1.4):
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - cx, y - cy)
            a = math.atan2(y - cy, x - cx)
            tooth = math.cos(a * teeth) > 0.35
            if hole < d <= r or (r < d <= r + 1.3 and tooth):
                l = -((x - cx) + (y - cy)) / (r * 1.4)
                put(g, x, y, ramp[0] if l > 0.3 else ramp[1] if l > -0.3 else ramp[2])
g = blank()
teeth = [(7, 1, 8, 1), (7, 10, 8, 10), (3, 5, 3, 6), (12, 5, 12, 6), (4, 2, 5, 2), (4, 3, 4, 3), (10, 2, 11, 2), (11, 3, 11, 3),
         (4, 9, 4, 9), (4, 10, 5, 10), (11, 9, 11, 9), (10, 10, 11, 10)]
gm = lambda x, y: math.hypot(x - 7.5, y - 5.5) <= 3.7 or any(a <= x <= c and b <= y <= d for a, b, c, d in teeth)
blob(g, gm, 7.5, 5.5, 4.5, "RRrq")
for y in range(N):
    for x in range(N):
        if math.hypot(x - 7.5, y - 5.5) <= 1.2:
            put(g, x, y, "k")
heap = lambda x, y: ((x - 7.5) / 7) ** 2 + ((y - 15) / 4.2) ** 2 <= 1 and y <= 14
for y in range(N):
    for x in range(N):
        if heap(x, y) and g[y][x] == ".":
            put(g, x, y, "rqSs"[(x * 3 + y * 5) % 4] if y > 12 else ("S" if x < 7 else "s"))
line(g, 2, 11, 6, 11, "P"); line(g, 2, 12, 6, 12, "p")  # a pipe
for x, y in ((10, 11), (12, 12)):  # bolts
    put(g, x, y, "B")
rect(g, 8, 12, 9, 13, "R")  # a rust plate
add("location_scrapheap_tunnels", g, {"R": "#e8905a", "r": "#b0582e", "q": "#6c3020", "S": "#9aa4b0", "s": "#5a5f6c",
                                      "P": "#c8d0dc", "p": "#7a8494", "B": "#fff0a8", "k": "#2a1a1c"})

# Foundry Depths: a crucible brimming with molten metal, sparks flying.
g = blank()
for y in range(6, 14):
    half = 6 - (y - 6) * 0.45
    for x in range(N):
        if abs(x - 7.5) <= half:
            put(g, x, y, "G" if x - 7.5 < -half + 1.2 else "s" if x - 7.5 > half - 1.5 else "m")
for x in (1, 14):  # handles
    put(g, x, 7, "s"); put(g, x, 8, "s")
for y in range(N):
    for x in range(N):
        e = ((x - 7.5) / 5.6) ** 2 + ((y - 6) / 1.6) ** 2
        if e <= 1:
            put(g, x, y, "M" if e <= 0.35 else "F" if e <= 0.75 else "f")
for x, y in ((4, 2), (8, 1), (11, 3), (6, 3)):
    put(g, x, y, "M" if (x + y) % 2 else "F")
add("location_foundry_depths", g, {"G": "#ff9a5a", "m": "#5c5c6c", "s": "#34343f", "M": "#fff6b0", "F": "#ffb030", "f": "#e0501e"})

# Subway Catacombs: a stone tunnel arch with a train's face coming out of the dark.
g = blank()
for y in range(N):
    for x in range(N):
        d = math.hypot(x - 7.5, y - 9)
        if y <= 13 and (d <= 6.6 or (y > 9 and 1 <= x <= 14)):
            put(g, x, y, "H" if x + y < 13 else "m" if x + y < 20 else "s")
        if y <= 13 and (d <= 4.6 or (y > 9 and 3 <= x <= 12)):
            put(g, x, y, "k")
rect(g, 5, 7, 10, 13, "T"); rect(g, 5, 7, 5, 13, "t"); rect(g, 10, 7, 10, 13, "q")  # train body
rect(g, 6, 8, 9, 9, "w")  # windshield
put(g, 6, 11, "Y"); put(g, 9, 11, "Y")  # headlights
rect(g, 5, 13, 10, 13, "q")
add("location_subway_catacombs", g, {"H": "#d0c0b0", "m": "#9a8878", "s": "#6a5a4e", "k": "#140e16", "T": "#b8c4d4", "t": "#e4ecf6",
                                     "q": "#6c7890", "w": "#2c4a7a", "Y": "#fff27a"})

# Clockwork Vaults: a brass clock face with gear teeth.
g = blank()
gear(g, 7.5, 7.5, 5, 10, "Yyb", hole=-1)
for y in range(N):
    for x in range(N):
        if math.hypot(x - 7.5, y - 7.5) <= 3.4:
            put(g, x, y, "W")
line(g, 7, 7, 7, 5, "k"); line(g, 8, 8, 9, 8, "k"); put(g, 7, 8, "k")
add("location_clockwork_vaults", g, {"Y": "#ffd870", "y": "#d09a30", "b": "#8a5a1c", "W": "#fff8e8", "k": "#3a2a30"})

# Cloudstone Crags: a slate peak with a snow cap, a bright cloud wrapped round its waist.
g = blank()
for y in range(1, 14):
    for x in range(N):
        if abs(x - 7.5) <= (y - 1) * 0.6 + 0.4:
            snow = y <= 3
            put(g, x, y, ("W" if x < 8 else "w") if snow else "H" if x < 7.5 - (y - 2) * 0.15 else "m" if x < 9 else "s")
for cx, cy, r in ((3.6, 10, 1.9), (6.8, 9.4, 2.3), (10, 10.1, 1.8)):
    for y in range(N):
        for x in range(N):
            if math.hypot(x - cx, y - cy) <= r and y <= 11:
                put(g, x, y, "W" if y < cy - 0.5 else "w")
for x in range(2, 14):  # cloud underside
    if g[11][x] in "Ww":
        put(g, x, 11, "c")
add("location_cloudstone_crags", g, {"W": "#ffffff", "w": "#c4dcf4", "c": "#7a9cc8", "H": "#8a86a8", "m": "#5e5a7a", "s": "#403c58"})

# Stormvein Rift: a dark storm cloud striking a rock with lightning; the crack glows.
g = blank()
rock = lambda x, y: ((x - 7.5) / 6.4) ** 2 + ((y - 12.5) / 3) ** 2 <= 1 and y <= 14
blob(g, rock, 6.5, 11.5, 5, "Hmsd")
for cx, cy, r in ((4, 3.6, 2.6), (8, 2.8, 3), (11.6, 3.8, 2.4)):
    for y in range(N):
        for x in range(N):
            if math.hypot(x - cx, y - cy) <= r and y <= 5:
                put(g, x, y, "C" if (y - cy) + (x - cx) * 0.3 < -1 else "c")
rect(g, 2, 5, 13, 5, "q")
for x, y in ((8, 6), (7, 7), (7, 8), (8, 8), (9, 8), (8, 9), (7, 10), (7, 11), (8, 12)):
    put(g, x, y, "Y")
put(g, 6, 7, "y"); put(g, 9, 9, "y")
for x, y in ((6, 12), (9, 13), (10, 12)):
    put(g, x, y, "y")
add("location_stormvein_rift", g, {"H": "#7a8aa8", "m": "#4e5a78", "s": "#323a54", "d": "#1e2236", "C": "#8a8aa8", "c": "#4a4a66",
                                   "q": "#2e2e44", "Y": "#fff8b0", "y": "#ffd84a"})

# Meteor Pits: a rock wrapped in flame, the fire streaming back up-right.
g = blank()
for y in range(N):
    for x in range(N):
        t_ = ((x - 6) - (y - 10)) / math.sqrt(2)  # along the tail (up-right)
        p_ = abs((x - 6) + (y - 10)) / math.sqrt(2)  # across it
        r = math.hypot(x - 6, y - 10)
        width = 5.0 if t_ < 1 else 5.0 - (t_ - 1) * 0.5
        if (r <= 5.2 or (t_ > 0 and p_ <= width)) and t_ <= 10.5:
            put(g, x, y, "M" if p_ < 1.4 and t_ > -1 else "f" if p_ < 2.8 else "F")
rock = lambda x, y: math.hypot(x - 5.4, y - 10.6) <= 2.9
blob(g, rock, 5, 10, 2.9, "Hmsd")
put(g, 4, 10, "d"); put(g, 6, 12, "d")
for x, y in ((7, 9), (6, 8), (8, 10), (7, 10)):  # glowing hot face toward the flame
    if rock(x, y):
        put(g, x, y, "f")
add("location_meteor_pits", g, {"F": "#e8401e", "f": "#ff9030", "M": "#fff3a8", "H": "#a48890", "m": "#6e5058", "s": "#48323a",
                                "d": "#2a1c24"})

# Stardust Lode: a rock studded with sparkles.
g = blank()
boulder(g, "Hmsd")
for x, y in ((5, 7), (10, 9), (7, 11)):
    star(g, x, y, "W", "y")
put(g, 12, 3, "W"); put(g, 3, 2, "y")
add("location_stardust_lode", g, {"H": "#8a82b8", "m": "#5a5290", "s": "#3a3468", "d": "#221e44", "W": "#ffffff", "y": "#ffe27a"})

# Hollow Seams: a grey-violet rock with a big hollow cave mouth; two pale eyes watch from the dark.
g = blank()
boulder(g, "Hmsd", ry=6)
for y in range(N):
    for x in range(N):
        e = ((x - 7.5) / 4) ** 2 + ((y - 13.5) / 7) ** 2
        if e <= 1 and y <= 13:
            put(g, x, y, "k")
put(g, 6, 10, "E"); put(g, 9, 10, "E")
add("location_hollow_seams", g, {"H": "#9a92aa", "m": "#6a6280", "s": "#463e58", "d": "#2a2438", "k": "#06040a", "E": "#e8f0ff"})

# Core of Nothing: a black hole: a pitch-black centre, a thin bright ring, a tilted violet disk passing in front.
g = blank()
for y in range(N):
    for x in range(N):
        r = math.hypot(x - 7.5, y - 7.5)
        disk = ((x - 7.5) / 7.2) ** 2 + ((y - 7.5 - (x - 7.5) * 0.15) / 1.2) ** 2 <= 1
        if r <= 4.2:
            put(g, x, y, "k")
        elif r <= 5.1:
            put(g, x, y, "W" if x + y < 15 else "V")
        if disk and r > 5.1:
            put(g, x, y, "P" if abs(x - 7.5) < 4.5 else "V" if abs(x - 7.5) < 6 else "v")
add("location_core_of_nothing", g, {"k": "#000000", "W": "#f4e8ff", "P": "#ff9ad8", "V": "#b070f0", "v": "#5a2a9a"})

# ---- Mine types (mine_<id>).
def ore_rock(ramp_ore, shape):
    g = blank()
    boulder(g, "Hmsd")
    for x, y in shape:
        put(g, x, y, "o")
    return g

# Copper Seam: a steep copper seam running diagonally through the rock, flecked with green patina.
g = blank()
boulder(g, "Hmsd")
for x in range(N):
    for y in range(N):
        if g[y][x] != ".":
            d = (x - 7.5) + (y - 8.5) * 0.9  # distance across the seam
            if -1.2 <= d <= 1.2 and False:
                pass
            k = (x - 7.5) - (y - 8.5) * 1.0
            if -1.0 <= k <= 1.0:
                put(g, x, y, "O" if k < -0.3 else "o" if k < 0.5 else "q")
for x, y in ((5, 5), (11, 11), (8, 9)):
    if g[y][x] in "Ooq":
        put(g, x, y, "G")
put(g, 6, 7, "W")
add("mine_copper_seam", g, {**ROCK, "O": "#ffc890", "o": "#e07a3a", "q": "#9a4220", "G": "#5ad0a0", "W": "#fff4e0"})

# Iron Vein: a branching silver vein through dark rock.
g = blank()
boulder(g, "Hmsd")
for x, y in ((3, 6), (4, 7), (5, 7), (6, 8), (7, 8), (8, 9), (9, 9), (10, 10), (11, 11), (7, 7), (8, 6), (9, 5), (8, 10), (8, 11), (7, 12), (10, 9), (11, 8)):
    put(g, x, y, "o")
for x, y in ((5, 7), (8, 6), (9, 9)):
    put(g, x, y, "O")
add("mine_iron_vein", g, {**ROCK, "O": "#ffffff", "o": "#c8d2e4"})

# Gold Vein: a gold vein ending in a fat nugget, with a glint.
g = blank()
boulder(g, "Hmsd")
for x, y in ((3, 10), (4, 10), (5, 9), (6, 9), (7, 8), (11, 11), (10, 10), (12, 11)):
    put(g, x, y, "o")
for x, y, c in ((8, 6, "O"), (9, 6, "o"), (8, 7, "o"), (9, 7, "o"), (10, 7, "q"), (8, 8, "q"), (9, 8, "q"), (7, 7, "o")):
    put(g, x, y, c)
star(g, 11, 4, "W", "O")
add("mine_gold_vein", g, {**ROCK, "O": "#fff6a0", "o": "#f0b828", "q": "#a8700c", "W": "#ffffff"})

# Standard: a mine cart loaded with rock, on a rail.
g = blank()
for y in range(6, 12):
    lo, hi = 2 + (y - 6) // 3, 13 - (y - 6) // 3
    for x in range(lo, hi + 1):
        put(g, x, y, "C" if x == lo else "c" if x == hi else "K")
rect(g, 2, 6, 13, 6, "C")
for x in (4, 11):
    put(g, x, 8, "r"); put(g, x, 10, "r")
for cx, cy, r in ((5, 4.6, 2), (8.5, 4, 2.4), (11, 5, 1.6)):  # ore lumps
    for y in range(N):
        for x in range(N):
            if math.hypot(x - cx, y - cy) <= r and y <= 5:
                put(g, x, y, "H" if (x - cx) + (y - cy) < -0.5 else "m")
for wx in (4, 10):
    rect(g, wx, 12, wx + 1, 13, "k"); put(g, wx, 12, "S")
rect(g, 1, 14, 14, 14, "S")
add("mine_standard", g, {**ROCK, "C": "#e08a5a", "K": "#a8502e", "c": "#6c2e1e", "r": "#ffd27a", "k": "#2e2830", "S": "#9aa4b0"})

# Quiet Shaft: a dark shaft mouth with a "shh" crescent moon above (stillness).
g = blank()
rect(g, 3, 6, 12, 14, "m"); rect(g, 3, 6, 12, 6, "H"); rect(g, 3, 6, 3, 14, "H"); rect(g, 12, 7, 12, 14, "s")
rect(g, 5, 8, 10, 14, "k")
line(g, 3, 6, 12, 6, "T"); put(g, 2, 6, "T"); put(g, 13, 6, "T")  # lintel beam
add("mine_quiet_shaft", g, {"H": "#9a8a80", "m": "#6c5c54", "s": "#4a3c38", "k": "#140e14", "T": "#a87048"})

# Scholar's Cavern: an open book resting on a rock.
g = blank()
boulder(g, "Hmsd", cy=11.5, ry=3)
for x in range(2, 14):
    top = 4 + abs(x - 7.5) * 0.3 if x != 7 and x != 8 else 6
    for y in range(int(top), 10):
        put(g, x, y, "P" if x < 7 else "p")
line(g, 7, 6, 7, 10, "b"); line(g, 8, 6, 8, 10, "b")
for y in (6, 8):
    line(g, 3, y, 5, y, "t"); line(g, 10, y, 12, y, "t")
rect(g, 2, 10, 13, 10, "B")
add("mine_scholars_cavern", g, {**ROCK, "P": "#fff8e8", "p": "#e0d4c0", "b": "#8a6a50", "t": "#a89a8a", "B": "#a03c3c"})

# Deep Pocket: a cut-away of rock: a narrow shaft winding down to a cavity full of glowing gems.
g = blank()
rect(g, 1, 2, 14, 14, "m"); rect(g, 1, 2, 14, 2, "H"); rect(g, 1, 2, 1, 14, "H"); rect(g, 14, 3, 14, 14, "s"); rect(g, 2, 14, 14, 14, "s")
for x, y in ((7, 2), (7, 3), (8, 4), (8, 5), (7, 6), (6, 7), (6, 8), (7, 9)):
    put(g, x, y, "k"); put(g, x + 1, y, "k")
for y in range(N):
    for x in range(N):
        e = ((x - 7.5) / 5.4) ** 2 + ((y - 11) / 3) ** 2
        if e <= 1 and y <= 13:
            put(g, x, y, "k" if e <= 0.7 else "G")  # the cavity glows at its rim
for x0, h, c in ((4, 2, "C"), (6, 3, "P"), (8, 4, "C"), (10, 2, "P")):  # gem crystals pointing up
    for y in range(13 - h, 14):
        put(g, x0, y, c); put(g, x0 + 1, y, c.lower())
    put(g, x0, 13 - h, "W")
for x, y in ((4, 5), (11, 7), (3, 4), (12, 4)):
    put(g, x, y, "s")
add("mine_deep_pocket", g, {**ROCK, "k": "#120c16", "C": "#7af0ff", "c": "#2ca0d8", "P": "#ff8ad8", "p": "#b03c9a", "W": "#ffffff", "G": "#6a5aa8"})

out = ["# Mining location icons (location_<id>) and mine types (mine_<id>). Generated by a script; approved by the owner.\n"]
for name, (g, pal) in sprites.items():
    used = {c for row in g for c in row if c != "."}
    pal = {k: v for k, v in pal.items() if k in used}
    out += [f"[{name}]", 'kind = "free"', "outline = true",
            "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items()) + " }", "rows = ["]
    out += [f'  "{"".join(r)}",' for r in g]
    out.append("]\n")
open(sys.argv[1], "w").write("\n".join(out))
