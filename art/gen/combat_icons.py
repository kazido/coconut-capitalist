"""Combat emoji (16x16, free, auto plum outline, light top-left): weapon kinds, flee, combat zones, enemies, bosses.
Run: python art/gen/combat_icons.py <group> <out.toml>   (group = weapons_zones | enemies | bosses)"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ui_icons import N, blank, put, rect, line, blob  # noqa: E402

sprites = {}
group_of = {}
GROUP = "weapons_zones"


def add(name, g, pal, outline=True):
    sprites[name] = (g, pal, outline)
    group_of[name] = GROUP


def ell(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def pts(g, cs, c):
    for x, y in cs:
        put(g, x, y, c)


def rows(g, top, strs):
    """Stamp ASCII rows ('.' = skip) with the top-left at (0, top)."""
    for dy, s in enumerate(strs):
        for dx, ch in enumerate(s):
            if ch != ".":
                put(g, dx, top + dy, ch)


# ---------------------------------------------------------------- weapons
# Same palette and dark navy outline as the basic tools (tool_axe / tool_pickaxe): steel, wood, gold.
TOOL = {"A": "#e4ecf4", "S": "#c0cad8", "s": "#8e9aaf", "t": "#5a6678", "T": "#38404e",
        "W": "#a07444", "w": "#4c3517", "v": "#332018", "Y": "#f0c040", "y": "#c08820", "o": "#1c1c2b"}


def navy(g):
    """Draw the tools' own 1px navy outline around every filled pixel (the build adds no plum outline then)."""
    edge = [(x, y) for y in range(N) for x in range(N) if g[y][x] == "." and any(
        0 <= x + dx < N and 0 <= y + dy < N and g[y + dy][x + dx] not in ".o" for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    for x, y in edge:
        g[y][x] = "o"


# sword: 3px steel blade up-right (lit edge top-left), gold guard, wood grip, gold pommel
g = blank()
for i in range(8):
    x, y = 6 + i, 9 - i
    put(g, x, y, "S")
    put(g, x + 1, y, "s")
    put(g, x + 1, y + 1, "t")
for i in range(7):
    put(g, 6 + i, 8 - i, "A")
put(g, 14, 1, "S")
for x, y in ((3, 8), (4, 9), (5, 10), (6, 11), (7, 12)):
    put(g, x, y, "Y")
pts(g, ((4, 10), (6, 12), (8, 12)), "y")
pts(g, ((4, 11), (3, 12)), "W")
pts(g, ((5, 11), (4, 12)), "w")
pts(g, ((2, 13), (1, 14), (2, 14)), "Y")
put(g, 3, 13, "y")
navy(g)
add("ui_weapon_sword", g, TOOL, outline=False)

# bow: wooden recurve limbs, gold grip wrap, pale string, arrow with steel head
g = blank()
limb = [(9, 1), (8, 2), (7, 3), (6, 4), (6, 5), (5, 6), (5, 7), (5, 8), (5, 9), (6, 10), (6, 11), (7, 12), (8, 13), (9, 14)]
for x, y in limb:
    put(g, x, y, "W")
    put(g, x + 1, y, "w")
pts(g, ((10, 1), (10, 14)), "v")
for y in range(2, 14):
    put(g, 11, y, "A")
pts(g, ((5, 7), (5, 8)), "Y")
pts(g, ((6, 7), (6, 8)), "y")
line(g, 2, 8, 12, 8, "W")
pts(g, ((12, 7), (13, 8), (12, 9), (14, 8)), "S")
put(g, 13, 7, "A")
pts(g, ((1, 7), (1, 9), (2, 7), (2, 9)), "A")
navy(g)
add("ui_weapon_bow", g, TOOL, outline=False)

# staff: slim wooden shaft up-right, gold crescent cradle, small violet gem
g = blank()
line(g, 2, 14, 9, 7, "W")
line(g, 3, 14, 9, 8, "w")
pts(g, ((4, 11), (5, 10)), "Y")
pts(g, ((5, 11), (6, 10)), "y")
pts(g, ((10, 6), (10, 5), (11, 6)), "Y")
pts(g, ((11, 7), (9, 6)), "y")
pts(g, ((12, 1), (11, 2), (11, 3)), "L")
pts(g, ((12, 2), (12, 3), (13, 2)), "P")
pts(g, ((13, 3), (12, 4), (13, 4), (14, 3)), "p")
pts(g, ((11, 4), (11, 5), (14, 5), (13, 5), (12, 5)), "Y")
navy(g)
add("ui_weapon_staff", g, {**TOOL, "L": "#f0d8ff", "P": "#b070f0", "p": "#6a38b0"}, outline=False)

# shield: round buckler, steel rim and boss, wood planks
g = blank()
for y in range(N):
    for x in range(N):
        d = math.hypot(x - 7.5, y - 7.5)
        if d <= 6.6:
            lit = (x + y) < 14
            if d >= 5.2:
                put(g, x, y, "S" if lit else "t")
            else:
                put(g, x, y, "W" if lit else "w")
for y in range(3, 13):
    if math.hypot(4.5 - 7.5, y - 7.5) < 5.2:
        put(g, 4, y, "v")
    if math.hypot(10.5 - 7.5, y - 7.5) < 5.2:
        put(g, 11, y, "v")
for y in range(N):
    for x in range(N):
        d = math.hypot(x - 7.5, y - 7.5)
        if d <= 2.1:
            put(g, x, y, "S" if (x + y) < 15 else "s")
pts(g, ((6, 6), (7, 6)), "A")
pts(g, ((3, 3), (2, 6)), "A")
navy(g)
add("ui_weapon_shield", g, TOOL, outline=False)

# flee: winged boot running right
g = blank()
rows(g, 2, [
    "...bbbb.........",
    "...bBBb.........",
    "...bBBb.....WW..",
    "...bBBb...WWwW..",
    "...bBBb..WWwWw..",
    "...bBBbbWWwWw...",
    "...bBBBBBBwW....",
    "..bBBBBBBBBb....",
    "..bBBBBBBBBBb...",
    "..bBBBBBBBBBBb..",
    "..sSSSSSSSSSSs..",
])
rect(g, 0, 8, 1, 8, "w")
rect(g, 0, 10, 1, 10, "w")
rect(g, 0, 12, 2, 12, "w")
add("ui_flee", g, {"b": "#5e3820", "B": "#b87440", "S": "#4a2c18", "s": "#2e1c2c", "W": "#ffffff", "w": "#bcd8f4"})

# ---------------------------------------------------------------- zones
# One bold object per zone, like the approved location icons (oasis palms, moonwell, cloudstone crags). Each idea
# differs from the existing location/area icons of the same area (no second clock face, gear or snowy peak).


def shade(g, mask, r4):
    """Fill mask with a light->dark ramp (2-4 letters) lit from the top-left of its own bounding box."""
    cells = [(x, y) for y in range(N) for x in range(N) if mask(x, y)]
    xs, ys = [c[0] for c in cells], [c[1] for c in cells]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    r = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 0.5
    for x, y in cells:
        lt = -((x - cx) + (y - cy)) / (math.sqrt(2) * r)
        i = 0 if lt > 0.42 else 1 if lt > -0.12 else 2 if lt > -0.62 else 3
        if not mask(x + 1, y + 1) and i < 2:
            i = 2
        put(g, x, y, r4[min(i, len(r4) - 1)])


GRASS = {"L": "#a8e070", "G": "#68b048", "g": "#3e7a38", "q": "#285a2c"}

# graveyard: rounded headstone with an engraved cross on a dirt mound with grass
g = blank()
shade(g, ell(7.5, 13.2, 6.6, 1.8), "ddee")
shade(g, lambda x, y: (4 <= x <= 11 and 6 <= y <= 12) or (ell(7.5, 6.2, 4, 3.6)(x, y) and y <= 6), "HmsD")
rect(g, 7, 5, 7, 10, "s")
rect(g, 5, 7, 9, 7, "s")
pts(g, ((8, 5), (8, 6), (8, 8), (8, 9), (8, 10), (6, 8), (9, 8), (10, 7)), "H")
pts(g, ((3, 12), (3, 11), (4, 12), (12, 12), (12, 11), (11, 12), (5, 12)), "G")
pts(g, ((4, 10), (4, 11), (5, 11)), "g")
add("location_graveyard", g, {"H": "#e8ecf4", "m": "#a8b0c0", "s": "#6c7488", "D": "#444a5c", "d": "#7a5a44", "e": "#4c3628", **GRASS})

# slime meadow: grass mound with a glossy jelly blob oozing over it
g = blank()
shade(g, lambda x, y: y >= 9 and ell(7.5, 14, 7, 5)(x, y), "LGgq")
shade(g, lambda x, y: (ell(7.5, 8.4, 5.4, 3)(x, y) and y <= 10) or (x in (3, 4) and 10 <= y <= 12) or (x in (10, 11) and 10 <= y <= 11) or (x == 7 and y == 11), "WMmn")
pts(g, ((4, 7), (5, 6), (6, 6)), "W")
pts(g, ((1, 11), (2, 10), (13, 10), (14, 11)), "L")
pts(g, ((12, 8), (12, 9)), "g")
put(g, 12, 7, "Y")
add("location_slime_meadow", g, {**GRASS, "W": "#e8fff4", "M": "#8cf0c4", "m": "#3cc0a0", "n": "#22808a", "Y": "#ffe070"})

# dusk dunes: a big setting sun behind a violet back dune and a tan front dune
g = blank()
shade(g, lambda x, y: ell(9, 8, 4.6, 4.6)(x, y), "YOoR")
for y in range(N):
    for x in range(N):
        if y >= 8 and y >= 10 - 2.6 * math.sin((x + 1) / 4.2) and 1 <= x <= 14:
            put(g, x, y, "P" if x < 9 else "p")
for y in range(N):
    for x in range(N):
        if y >= 11 and y >= 13 - 2.2 * math.sin((x - 3) / 4) and 1 <= x <= 14:
            put(g, x, y, "S" if y < 13 else "s")
add("location_dusk_dunes", g, {"Y": "#fff0a0", "O": "#ffb050", "o": "#ff7a50", "R": "#e04870", "P": "#a07cc8", "p": "#6c509c", "S": "#f4c888", "s": "#c48c58"})

# mirage ruins: one broken sandstone column on a plinth, cyan heat shimmer either side
g = blank()
tops = {5: 3, 6: 3, 7: 4, 8: 5, 9: 6, 10: 7}
shade(g, lambda x, y: 5 <= x <= 10 and tops[x] <= y <= 12, "HHms")
for x in (6, 8):
    for y in range(tops[x] + 1, 13):
        put(g, x, y, "m")
shade(g, lambda x, y: 3 <= x <= 12 and 13 <= y <= 14, "Hms")
for y0 in (5, 9):
    for x in (1, 2, 3, 12, 13, 14):
        put(g, x, y0 + (x % 2), "C")
pts(g, ((2, 5), (13, 9)), "c")
add("location_mirage_ruins", g, {"H": "#f8e4b4", "m": "#d4a870", "s": "#9c7448", "C": "#b8f4ff", "c": "#58c8e8"})

# scrapyard: rusty oil barrel with a worn tire leaning on it
g = blank()
shade(g, lambda x, y: 2 <= x <= 9 and 3 <= y <= 13, "RrqQ")
rect(g, 2, 3, 9, 3, "R")
pts(g, ((3, 3), (4, 3)), "W")
for y in (6, 10):
    rect(g, 2, y, 9, y, "Q")
pts(g, ((5, 8), (6, 8)), "q")
ring = lambda x, y: ell(10.5, 10, 3.6, 3.6)(x, y) and not ell(10.5, 10, 1.4, 1.4)(x, y)
shade(g, ring, "TtUU")
pts(g, ((9, 7), (12, 7), (13, 9)), "t")
add("location_scrapyard", g, {"R": "#f09a60", "r": "#c0642e", "q": "#86402a", "Q": "#52281e", "W": "#ffd8b0", "T": "#7a7a8c", "t": "#4a4a5a", "U": "#2c2c38"})

# rusted foundry: saw-tooth factory roof, tall chimney with an ember, glowing windows
g = blank()
rect(g, 11, 1, 12, 7, "r")
put(g, 11, 1, "R")
pts(g, ((11, 0), (12, 0)), "F")
body = lambda x, y: 2 <= x <= 13 and 4 + (x - 2) % 4 <= y <= 14
shade(g, body, "RRrq")
for x in range(2, 14):
    t = (x - 2) % 4
    put(g, x, 4 + t, "S" if t == 0 else "s")
rect(g, 2, 13, 13, 14, "q")
for x0 in (3, 6, 9):
    rect(g, x0, 10, x0 + 1, 11, "F")
    put(g, x0, 10, "Y")
add("location_rusted_foundry", g, {"R": "#e8905a", "r": "#b0582e", "q": "#7a3a22", "S": "#c0cad8", "s": "#8e9aaf", "F": "#ff7a30", "Y": "#ffe880"})

# canal alleys: iron street lamp glowing over canal water
g = blank()
shade(g, lambda x, y: 1 <= x <= 14 and 12 <= y <= 14, "WBbb")
pts(g, ((2, 13), (3, 13), (8, 14), (9, 14), (12, 13)), "w")
rect(g, 7, 6, 8, 12, "i")
put(g, 7, 6, "I")
rect(g, 6, 11, 9, 11, "i")
rect(g, 5, 1, 10, 1, "i")
rect(g, 6, 0, 9, 0, "i")
rect(g, 5, 2, 5, 5, "i")
rect(g, 10, 2, 10, 5, "i")
rect(g, 5, 5, 10, 5, "i")
rect(g, 6, 2, 9, 4, "Y")
pts(g, ((6, 2), (7, 2)), "W")
pts(g, ((9, 4), (8, 4)), "y")
add("location_canal_alleys", g, {"W": "#ffffff", "B": "#58b8f0", "b": "#2c78c0", "w": "#a8e8ff", "i": "#3a3848", "I": "#6a6880", "Y": "#ffe070", "y": "#f0a030"})

# clockwork district: brick clock tower with a teal roof and a brass clock
g = blank()
for y in range(1, 5):
    half = y * 1.1 + 0.4
    for x in range(N):
        if abs(x - 7.5) <= half:
            put(g, x, y, "T" if x < 7.5 else "t")
shade(g, lambda x, y: 4 <= x <= 11 and 5 <= y <= 14, "BBbd")
shade(g, ell(7.5, 8, 3, 3), "YyYu")
shade(g, ell(7.5, 8, 2.1, 2.1), "WWCC")
pts(g, ((7, 6), (7, 7), (7, 8), (8, 8), (9, 8)), "k")
rect(g, 7, 12, 8, 14, "k")
pts(g, ((5, 11), (10, 13), (5, 6)), "d")
add("location_clockwork_district", g, {"T": "#4cc0b0", "t": "#2a7c80", "B": "#d07a54", "b": "#a0503a", "d": "#6a3028", "Y": "#ffe488", "y": "#e0a838", "u": "#a8701c", "W": "#fffaf0", "C": "#e8dcc0", "k": "#3a2a30"})

# cloud ridge: a floating rock island, grassy top, clouds drifting past its base
g = blank()
shade(g, lambda x, y: 5 <= y <= 13 and abs(x - 7.5) <= 6.4 - (y - 5) * 0.8, "HmsD")
shade(g, ell(7.5, 5.2, 6.4, 1.6), "LGgq")
pts(g, ((4, 3), (10, 3), (11, 3)), "G")
shade(g, lambda x, y: ell(3, 10.6, 2.6, 1.6)(x, y) or ell(12.4, 9.6, 2.4, 1.5)(x, y), "WWcc")
add("location_cloud_ridge", g, {"H": "#b4aac4", "m": "#847a9c", "s": "#5a5278", "D": "#3a3456", **GRASS, "W": "#ffffff", "c": "#c4dcf4"})

# storm garden: violet storm bloom with a crackling yellow heart, sparks around it
g = blank()
rect(g, 7, 9, 8, 14, "g")
shade(g, ell(4.6, 11.6, 2.4, 1.3), "LGg")
shade(g, ell(10.6, 12.6, 2.4, 1.3), "Gg")
petals = lambda x, y: any(ell(7.5 + 2.6 * math.cos(a * math.pi / 3), 6 + 2.6 * math.sin(a * math.pi / 3), 2, 2)(x, y) for a in range(6))
shade(g, petals, "VvPp")
shade(g, ell(7.5, 6, 1.6, 1.6), "WYYy")
pts(g, ((1, 2), (2, 3), (1, 4), (14, 1), (13, 2), (14, 3), (13, 9), (14, 10)), "Y")
add("location_storm_garden", g, {"V": "#d8b8ff", "v": "#a078f0", "P": "#7048c8", "p": "#44288c", "W": "#ffffff", "Y": "#ffe858", "y": "#f0a830", **GRASS})

# comet fields: icy comet head with a wide burning tail, two stars
g = blank()
for y in range(N):
    for x in range(N):
        u = (-(x - 11) + (y - 4)) / math.sqrt(2)  # distance along the tail (down-left)
        v = ((x - 11) + (y - 4)) / math.sqrt(2)   # sideways
        if 0 < u < 12 and abs(v) <= 2.6 * (1 - u / 13):
            put(g, x, y, "Y" if abs(v) < 0.8 and u < 7 else "O" if u < 7 else "o")
shade(g, ell(11, 4.5, 3, 3), "WCcb")
pts(g, ((3, 2), (14, 11)), "W")
pts(g, ((2, 2), (4, 2), (3, 1), (3, 3)), "w")
add("location_comet_fields", g, {"o": "#d8402c", "O": "#ff9a40", "Y": "#ffe070", "W": "#ffffff", "w": "#b8c8f0", "C": "#b8f4ff", "c": "#58c8e8", "b": "#2c78c0"})

# starfall temple: marble temple, shaded pediment, gold star above the roof
g = blank()
for y in range(3, 7):
    half = (y - 3) * 2 + 1.5
    for x in range(N):
        if abs(x - 7.5) <= half and 1 <= x <= 14:
            put(g, x, y, "H" if x < 7.5 else "m")
rect(g, 1, 6, 14, 6, "s")
for x in (2, 6, 10):
    rect(g, x, 7, x, 12, "H")
    rect(g, x + 1, 7, x + 1, 12, "m")
rect(g, 1, 13, 14, 13, "H")
rect(g, 1, 14, 14, 14, "s")
pts(g, ((7, 0), (8, 0), (6, 1), (7, 1), (8, 1), (9, 1), (7, 2), (8, 2)), "Y")
put(g, 7, 0, "W")
add("location_starfall_temple", g, {"H": "#f4f0ff", "m": "#c4b8e4", "s": "#8a78b8", "Y": "#ffd848", "W": "#ffffff"})

# hollow gate: stone arch on two pillars, a swirling violet portal inside
g = blank()
shade(g, lambda x, y: (2 <= x <= 13 and 6 <= y <= 14) or (ell(7.5, 6.5, 6, 5.5)(x, y)), "HmsD")
portal = lambda x, y: (5 <= x <= 10 and 7 <= y <= 14) or (ell(7.5, 7, 3, 3.6)(x, y))
shade(g, portal, "VvPz")
pts(g, ((7, 7), (8, 8), (7, 9), (6, 10), (8, 11)), "W")
for y in (8, 11):
    rect(g, 2, y, 4, y, "s")
    rect(g, 11, y, 13, y, "D")
add("location_hollow_gate", g, {"H": "#b8b4c8", "m": "#88849c", "s": "#5c5874", "D": "#3c3854", "V": "#e0b8ff", "v": "#a068e8", "P": "#6a38b8", "z": "#2a1458", "W": "#ffffff"})

# the unmade: a jagged tear in the world, black inside with glowing rims, broken shards drifting off
g = blank()
mid = {1: 8, 2: 8, 3: 7, 4: 7, 5: 8, 6: 9, 7: 8, 8: 7, 9: 6, 10: 7, 11: 8, 12: 8, 13: 7, 14: 7}
wid = {1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2, 7: 3, 8: 3, 9: 2, 10: 2, 11: 2, 12: 1, 13: 1, 14: 0}
for y, m in mid.items():
    w = wid[y]
    for x in range(m - w, m + w + 1):
        put(g, x, y, "k")
    put(g, m - w - 1, y, "P")
    put(g, m + w + 1, y, "p")
pts(g, ((2, 3), (3, 3), (2, 4), (12, 10), (13, 10), (13, 11), (3, 11), (12, 4)), "S")
pts(g, ((2, 3), (12, 10)), "s")
pts(g, ((8, 7), (6, 10)), "W")
add("location_the_unmade", g, {"k": "#0a0612", "P": "#ffb0ec", "p": "#c058e0", "S": "#6a5aa8", "s": "#a898e0", "W": "#ffffff"})


def main():
    group, outpath = sys.argv[1], sys.argv[2]
    out = [f"# Combat icons ({group}). Generated by art/gen/combat_icons.py; approved by the owner.\n"]
    for name, (g, pal, outline) in sprites.items():
        if group_of[name] != group:
            continue
        used = {c for row in g for c in row if c != "."}
        missing = used - set(pal)
        if missing:
            raise SystemExit(f"{name}: no colour for {sorted(missing)}")
        pal = {k: v for k, v in pal.items() if k in used}
        out += [f"[{name}]", 'kind = "free"', f"outline = {str(outline).lower()}",
                "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items()) + " }", "rows = ["]
        out += [f'  "{"".join(r)}",' for r in g]
        out.append("]\n")
    Path(outpath).write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
