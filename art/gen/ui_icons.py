"""Generate page/skill UI icons (16x16, free, auto plum outline). Light from the top-left. Writes TOML to argv[1]."""
import math
import sys

N = 16
sprites = {}


def blank():
    return [["." for _ in range(N)] for _ in range(N)]


def put(g, x, y, c):
    if 0 <= x < N and 0 <= y < N:
        g[y][x] = c


def rect(g, x0, y0, x1, y1, c):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            put(g, x, y, c)


def line(g, x0, y0, x1, y1, c):
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(n + 1):
        put(g, round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n), c)


def blob(g, mask, cx, cy, r, ramp):
    for y in range(N):
        for x in range(N):
            if mask(x, y):
                l = -((x - cx) + (y - cy)) / (math.sqrt(2) * r)
                i = 0 if l > 0.5 else 1 if l > -0.05 else 2 if l > -0.6 else 3
                if not mask(x + 1, y + 1) and i < 2:
                    i = 2
                g[y][x] = ramp[min(i, len(ramp) - 1)]


def fill(g, m, c):
    for y in range(N):
        for x in range(N):
            if m(x, y):
                put(g, x, y, c)


def add(name, g, pal):
    sprites[name] = (g, pal)


# ---- Home: a plain house, red roof, cream walls, door and window.
g = blank()
for y in range(1, 8):  # roof: peak at cols 7-8
    half = y
    for x in range(8 - half, 8 + half):
        put(g, x, y, "R" if x < 8 else "r")
rect(g, 0, 7, 15, 7, ".")
rect(g, 1, 7, 14, 7, "d")  # eave
rect(g, 10, 1, 11, 3, "C")  # chimney
put(g, 11, 1, "c"); put(g, 11, 2, "c"); put(g, 11, 3, "c")
rect(g, 3, 8, 12, 13, "W")
rect(g, 11, 8, 12, 13, "w")
rect(g, 3, 13, 12, 13, "w")
rect(g, 8, 9, 10, 13, "D"); put(g, 10, 9, "e"); rect(g, 10, 10, 10, 13, "e")  # door, shaded edge
put(g, 9, 11, "y")  # knob
rect(g, 4, 9, 6, 11, "B"); put(g, 4, 9, "b"); put(g, 6, 11, "n")  # window: highlight + shadow corner
add("ui_home", g, {"R": "#f06a50", "r": "#b83c40", "d": "#7a2a38", "C": "#b0a4a0", "c": "#786a6c",
                   "W": "#f6ead2", "w": "#cdb89c", "D": "#9a6040", "e": "#683c30", "y": "#ffd84a",
                   "B": "#7ac8f0", "b": "#d8f4ff", "n": "#3c7cb4"})

# ---- Shop: a shopping cart.
g = blank()
line(g, 1, 2, 2, 2, "k"); line(g, 3, 2, 3, 3, "k")  # handle
for y in range(4, 10):  # basket, narrowing toward the bottom
    x0 = 3 + (y - 4) // 2
    x1 = 14 - (y - 4) // 3
    for x in range(x0, x1 + 1):
        put(g, x, y, "B" if x < 9 else "b")
for x in (6, 9, 12):  # grid
    line(g, x, 5, x, 8, "n")
line(g, 4, 6, 13, 6, "n")
rect(g, 3, 4, 14, 4, "S")  # rim
rect(g, 5, 10, 13, 10, "k")  # base bar
for wx in (6, 12):  # wheels
    rect(g, wx - 1, 12, wx, 13, "k"); put(g, wx - 1, 12, "S")
line(g, 4, 9, 4, 11, "k")
add("ui_shop", g, {"k": "#4a4250", "S": "#e8eef4", "B": "#6ab4f0", "b": "#3a7cc8", "n": "#24508a"})

# ---- Inventory: a square leather satchel with a flap, buckle and top handle.
g = blank()
rect(g, 6, 2, 9, 2, "s"); put(g, 5, 3, "s"); put(g, 10, 3, "s"); put(g, 5, 4, "s"); put(g, 10, 4, "s")  # handle loop
rect(g, 3, 5, 12, 14, "m")  # body
rect(g, 3, 5, 3, 14, "L"); rect(g, 3, 5, 12, 5, "L")  # lit top/left edges
rect(g, 12, 6, 12, 14, "s"); rect(g, 4, 14, 12, 14, "s")  # shadow edges
put(g, 3, 14, "s")
rect(g, 4, 6, 11, 9, "f"); rect(g, 4, 6, 11, 6, "F")  # flap
rect(g, 4, 10, 11, 10, "d")  # flap edge shadow
rect(g, 7, 9, 8, 11, "Y"); put(g, 8, 11, "y"); put(g, 8, 10, "y")  # buckle
rect(g, 5, 12, 10, 12, "s")  # stitch line
add("ui_bag", g, {"L": "#e0a868", "m": "#b47440", "s": "#7c4a2c", "d": "#4e2c22", "F": "#d49058", "f": "#a0643a",
                  "Y": "#ffd84a", "y": "#c89020"})

# ---- Shipments: a wooden crate (top face + front with an X brace).
g = blank()
for y, (x0, x1) in zip(range(2, 5), ((4, 14), (3, 13), (2, 12))):  # top face, slanted
    rect(g, x0, y, x1, y, "T")
rect(g, 13, 3, 14, 12, "e")  # right side face
put(g, 14, 2, "e"); put(g, 14, 12, ".")
rect(g, 2, 5, 12, 13, "M")  # front
for x in range(2, 13):
    put(g, x, 5, "F"); put(g, x, 13, "F")
for y in range(5, 14):
    put(g, 2, y, "F"); put(g, 12, y, "F")
line(g, 3, 6, 11, 12, "X"); line(g, 3, 12, 11, 6, "X")
for x, y in ((3, 6), (11, 6), (3, 12), (11, 12)):
    put(g, x, y, "n")
add("ui_crate", g, {"T": "#f0c888", "M": "#b07a48", "F": "#7a4c30", "X": "#d6a46a", "e": "#5c3626", "n": "#c8c0c4"})


# ---- Pickaxe and axe parts, reused by Skills and Mining.
def pickaxe(g, hx0, hy0, hx1, hy1, cx, cy, r, a0, a1, metal="Gg", wood="Ww"):
    line(g, hx0, hy0, hx1, hy1, wood[0])
    line(g, hx0 + 1, hy0, hx1 + 1, hy1, wood[1])
    for y in range(N):
        for x in range(N):
            d = math.hypot(x - cx, y - cy)
            a = math.degrees(math.atan2(y - cy, x - cx))
            if r - 0.9 <= d <= r + 0.6 and a0 <= a <= a1:
                put(g, x, y, metal[0] if d > r - 0.2 else metal[1])


# Skills: the four skills in a 2x2 grid (pickaxe, fish, leaf, corn).
g = blank()
for (x0, y0), (base, lit) in zip(((1, 1), (8, 1), (1, 8), (8, 8)), (("1", "2"), ("3", "4"), ("5", "6"), ("7", "8"))):
    rect(g, x0, y0, x0 + 6, y0 + 6, base)  # each skill gets its own tinted tile
    rect(g, x0, y0, x0 + 6, y0, lit); rect(g, x0, y0, x0, y0 + 6, lit)  # bevel: lit top and left edges
for x, y in ((2, 3), (3, 2), (4, 2), (5, 2), (6, 3)):  # pick head
    put(g, x, y, "S")
line(g, 3, 6, 5, 3, "W")
for x, y in ((9, 4), (10, 3), (11, 3), (10, 4), (11, 4), (12, 4), (10, 5), (11, 5), (12, 3), (13, 4), (13, 3), (13, 5)):  # fish, clear of the tile edges
    put(g, x, y, "F")
put(g, 10, 3, "f"); put(g, 12, 4, "F"); put(g, 13, 4, ".")
fill(g, lambda x, y: 1 <= x <= 7 and 8 <= y <= 14 and abs((x - 4) + (y - 11)) <= 1.2 and abs((x - 4) - (y - 11)) <= 3, "L")  # leaf
line(g, 2, 13, 6, 9, "l")
fill(g, lambda x, y: 10 <= x <= 12 and 9 <= y <= 13 and abs(x - 11) <= 1.3 - abs(y - 11) * 0.2, "Y")  # corn
put(g, 9, 13, "L"); put(g, 13, 13, "l"); put(g, 9, 12, "L"); put(g, 13, 12, "l")
add("ui_skills", g, {"1": "#4a3a34", "2": "#6a5448", "3": "#1e3a6a", "4": "#2e5490", "5": "#1e4a2a", "6": "#2e6a3a", "7": "#5a4418", "8": "#7a6026", "S": "#dfe8f4", "W": "#c8905a", "F": "#6ab4f0", "f": "#e8f4ff", "L": "#8ade5a", "l": "#3c8a34",
                           "Y": "#ffd84a"})


# Ranks: a level-up badge, white arrow on green inside a gold rim.
g = blank()
fill(g, lambda x, y: math.hypot(x - 7.5, y - 7.5) <= 6.6, "G")
fill(g, lambda x, y: math.hypot(x - 7.5, y - 7.5) <= 5.4, "B")
fill(g, lambda x, y: math.hypot(x - 7.5, y - 7.5) <= 5.4 and (x - 7.5) + (y - 7.5) > 2, "b")
for y in range(4, 12):
    for x in range(N):
        if (y <= 7 and abs(x - 7.5) <= (y - 4) * 1.2 + 0.5) or (y > 7 and 7 <= x <= 8):
            put(g, x, y, "A" if x < 8 else "a")
put(g, 9, 8, "b")  # the shadow side right under the arrow head
add("ui_ranks", g, {"G": "#f0b830", "B": "#3aa04a", "b": "#267038", "A": "#ffffff", "a": "#c8d8e8"})


# ---- Mining skill: one big pickaxe.
g = blank()
pickaxe(g, 2, 14, 11, 5, 7, 9, 7.5, -105, 15, metal="Gg")
add("ui_skill_mining", g, {"W": "#c8905a", "w": "#7a4c30", "G": "#dfe8f4", "g": "#7e88a0"})

# ---- Fishing skill: a bent rod, line and red/white bobber.
g = blank()
pts = [(2, 14), (3, 13), (4, 12), (5, 11), (6, 9), (7, 8), (8, 6), (9, 5), (10, 4), (11, 3), (12, 3), (13, 3)]
for i, (x, y) in enumerate(pts):
    put(g, x, y, "W" if i < 5 else "R")
put(g, 3, 14, "w"); put(g, 4, 13, "w"); put(g, 5, 12, "w")  # grip shading
rect(g, 4, 11, 4, 11, "k")  # reel
put(g, 5, 10, "k")
line(g, 13, 4, 13, 9, "l")  # line
rect(g, 12, 10, 14, 10, "F"); rect(g, 12, 11, 14, 12, "f"); put(g, 12, 10, "H")  # bobber
put(g, 13, 13, "f")
add("ui_skill_fishing", g, {"W": "#c8905a", "w": "#7a4c30", "R": "#9a6a44", "k": "#4a4250", "l": "#d8e4f0",
                            "F": "#ff5a4a", "f": "#f4f0ec", "H": "#ffc0b0"})

# ---- Farming skill: a corn cob with green husks peeling open at the bottom.
g = blank()
for y in range(1, 12):
    w = 2.7 * math.sqrt(max(0.0, 1 - ((y - 6.5) / 5.9) ** 2))
    for x in range(N):
        if abs(x - 7.5) <= w + 0.2:
            rel = (x - 7.5) / max(w, 0.5)
            c = 0 if rel < -0.35 else 1 if rel < 0.45 else 2
            if y % 2 == 0 and x % 2 == 1:  # kernel seams
                c = min(c + 1, 3)
            put(g, x, y, "Eedc"[c])
for y in range(6, 15):
    lo, hi = 3 + abs(y - 10) * 0.7, 5.6 + (y - 6) * 0.3  # left husk
    for x in range(N):
        if lo <= x <= hi:
            put(g, x, y, "L" if x < (lo + hi) / 2 else "l")
    lo, hi = 9.4 - (y - 6) * 0.3, 12 - abs(y - 10) * 0.7  # right husk
    for x in range(N):
        if lo <= x <= hi:
            put(g, x, y, "m" if x < (lo + hi) / 2 else "s")
add("ui_skill_farming", g, {"E": "#fff2a0", "e": "#f8c838", "d": "#d08c20", "c": "#94581a",
                               "L": "#b6e86a", "l": "#6cc044", "m": "#4ea03c", "s": "#2c6a30"})

# ---- Magnet: a red horseshoe magnet with steel tips.
g = blank()
for y in range(N):
    for x in range(N):
        d = math.hypot(x - 7.5, y - 7.5)
        if (2.6 <= d <= 6.4 and y <= 7.5) or (y > 7.5 and y <= 13 and (2 <= x <= 4 or 11 <= x <= 13)):
            tip = y >= 11
            lit = x < 7.5 and (d > 5.2 or y > 7.5 and x <= 2) or (y <= 7.5 and d > 5.4 and x < 9)
            dark = x > 7.5 and (d < 3.6 or x >= 13) or (y > 7.5 and x in (4, 13))
            put(g, x, y, ("T" if lit else "t" if dark else "M") if tip else ("H" if lit else "r" if dark else "R"))
add("ui_magnet", g, {"H": "#ff9a80", "R": "#e8403c", "r": "#9c2434", "T": "#f4f8ff", "M": "#b8c2d4", "t": "#6c7890"})

# ---- Pets: three little wisps in a huddle (back-left blue, back-right pink, front orange).
FLAME = [
    "...a..",
    "..aa..",
    ".aaab.",
    ".abbb.",
    "abwbwb",
    "abbbbc",
    ".bbbc.",
    "..cc..",
]
g = blank()


def wisp(g, ox, oy, ramp, edge=False):
    for y, row in enumerate(FLAME):
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            put(g, ox + x, oy + y, {"a": ramp[0], "b": ramp[1], "c": ramp[2], "w": "w"}[ch])
    if edge:  # a plum rim so the front wisp separates from the ones behind it
        for y, row in enumerate(FLAME):
            xs = [x for x, ch in enumerate(row) if ch != "."]
            put(g, ox + xs[0] - 1, oy + y, "o"); put(g, ox + xs[-1] + 1, oy + y, "o")


wisp(g, 1, 2, "ABC")
wisp(g, 9, 2, "PQR")
wisp(g, 5, 6, "XYZ", edge=True)
for x in range(N):  # trim rim pixels that stick out past the huddle (the build outlines the rest)
    for y in range(N):
        if g[y][x] == "o" and not any(0 <= x + dx < N and g[y][x + dx] not in ".o" for dx in (-1, 1)):
            g[y][x] = "."
add("ui_pets", g, {"A": "#c8f4ff", "B": "#58b8ff", "C": "#2c68c8", "P": "#ffd4f4", "Q": "#e070d0", "R": "#9038a0",
                   "X": "#fff2a8", "Y": "#ffa030", "Z": "#d04820", "w": "#ffffff", "o": "#2e1c2c"})

# ---- Check-in: calendar, check moved 1px left, darker green.
checkin = [
    "................",
    "....k......k....",
    "..RRkRRRRRRkRR..",
    "..RRRRRRRRRRRr..",
    "..rrrrrrrrrrrr..",
    "..Wwwwwwwwwwwg..",
    "..wwwwwwwwCcwg..",
    "..wwwwwwwCcwwg..",
    "..wCcwwwCcwwwg..",
    "..wwCcwCcwwwwg..",
    "..wwwCCcwwwwwg..",
    "..wwwwcwwwwwwg..",
    "..wwwwwwwwwwwg..",
    "..gggggggggggg..",
    "................",
    "................",
]
add("ui_checkin", [list(r) for r in checkin], {"k": "#5a4a52", "R": "#f06a5a", "r": "#b03a44", "W": "#ffffff",
                                                "w": "#ece6dc", "g": "#b8aca4", "C": "#3aa040", "c": "#1e6a2e"})

# ---- Quests: an open parchment scroll, rolled at top and bottom, lines of writing and a red wax seal.
g = blank()
rect(g, 3, 4, 12, 11, "P"); rect(g, 3, 4, 3, 11, "p"); rect(g, 12, 4, 12, 11, "q")  # sheet
for y, x1 in ((5, 10), (7, 9), (9, 8)):
    line(g, 5, y, x1, y, "t")  # writing
for y0 in (2, 12):  # the two rolls: a lit top row, a shaded bottom row, darker end caps
    rect(g, 2, y0, 13, y0, "R"); rect(g, 2, y0 + 1, 13, y0 + 1, "r")
    put(g, 1, y0, "e"); put(g, 1, y0 + 1, "e"); put(g, 14, y0, "e"); put(g, 14, y0 + 1, "e")
rect(g, 10, 9, 11, 10, "S"); put(g, 11, 10, "s")  # wax seal
add("ui_quest", g, {"P": "#f6e8c8", "p": "#fff8e4", "q": "#d8c49a", "t": "#8a6a4a", "R": "#e8c890", "r": "#b08a58",
                    "e": "#7a5a3a", "S": "#e04a40", "s": "#9a2830"})

if __name__ == "__main__":
    out = ["# Page and skill UI icons (free, plum outline). Generated by a script; approved by the owner.\n"]
    for name, (g, pal) in sprites.items():
        used = {c for row in g for c in row if c != "."}
        pal = {k: v for k, v in pal.items() if k in used}
        out += [f"[{name}]", 'kind = "free"', "outline = true",
                "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items()) + " }", "rows = ["]
        out += [f'  "{"".join(r)}",' for r in g]
        out.append("]\n")
    open(sys.argv[1], "w").write("\n".join(out))
