"""Enemy and boss emoji (enemy_<id>), 16x16, plum outline from the build, light from the top-left.

One template for every enemy so the set reads as a family: a front-facing head of the same size (HEAD, about 10x9 px,
centred low), the same 2x2 eyes at the same spot (white glint top-left, dark iris; glowing colour only where a dark face
would swallow the dark iris), 4-tone hue-shifted ramps, species told apart by silhouette (ears, horns, hoods, helms, wings).
Bosses use the same eyes but a bigger head and gold (crown, halo or trim).
Run: python art/gen/combat_enemies.py enemies|bosses <out.toml>"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import combat_icons as ci  # noqa: E402
from combat_icons import N, blank, put, rect, ell, pts  # noqa: E402

K = "#1c1420"  # iris / void black
WHITE = "#ffffff"
HEAD = ell(7.5, 8.5, 4.6, 4.4)
BIG = ell(7.5, 8.5, 5.6, 5.2)
EYE_Y = 8


def add(name, g, pal):
    ci.add(name, g, {"k": K, "W": WHITE, **pal})


def ramp(letters, hexes):
    return dict(zip(letters, hexes))


def shade(g, mask, r4):
    """Fill mask with a 4-letter light->dark ramp lit from the top-left of its own bounding box; bottom-right rim in shadow."""
    cells = [(x, y) for y in range(N) for x in range(N) if mask(x, y)]
    xs, ys = [c[0] for c in cells], [c[1] for c in cells]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    r = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 + 0.5
    for x, y in cells:
        lt = -((x - cx) + (y - cy)) / (math.sqrt(2) * r)
        i = 0 if lt > 0.42 else 1 if lt > -0.12 else 2 if lt > -0.62 else 3
        if not mask(x + 1, y + 1) and i < 2:
            i = 2
        put(g, x, y, r4[i])


def eyes(g, y=EYE_Y, iris="k", lx=5, rx=9):
    for x in (lx, rx):
        rect(g, x, y, x + 1, y + 1, iris)
        put(g, x, y, "W")


def mirror(cs):
    return list(cs) + [(15 - x, y) for x, y in cs]


ci.GROUP = "enemies"

# ---- graveyard
ZOMB = ramp("ABCD", ("#b8e08c", "#7fb860", "#4f8650", "#2f5248"))
SHIRT = ramp("RS", ("#7484b8", "#4a5482"))

g = blank()
rect(g, 3, 13, 7, 14, "R")
rect(g, 8, 13, 12, 14, "S")
pts(g, ((5, 14), (10, 14)), ".")
shade(g, HEAD, "ABCD")
pts(g, ((4, 5), (5, 4), (6, 4), (8, 4), (9, 4), (11, 5), (10, 5), (7, 5)), "D")
eyes(g)
pts(g, ((6, 11), (7, 11), (9, 11)), "k")
put(g, 8, 11, "B")
pts(g, ((11, 8), (11, 10)), "C")
add("enemy_zombie", g, {**ZOMB, **SHIRT})

STEEL = ramp("HIJL", ("#e6eef8", "#a8b6cc", "#6a7894", "#3e4864"))
g = blank()
shade(g, lambda x, y: 2 <= x <= 13 and 12 <= y <= 14 and not (y == 12 and x in (2, 13)), "HIJL")
shade(g, HEAD, "ABCD")
shade(g, lambda x, y: ell(7.5, 7.5, 5.4, 4.8)(x, y) and y <= 6, "HIJL")
rect(g, 2, 7, 13, 7, "J")
rect(g, 7, 6, 8, 10, "I")
pts(g, ((7, 6), (7, 7)), "H")
pts(g, ((4, 4), (11, 4)), "H")
eyes(g)
rect(g, 6, 12, 9, 12, "k")
add("enemy_armored_zombie", g, {**ZOMB, **STEEL})

BONE = ramp("ABCD", ("#fff8e4", "#e2d6b4", "#aa9c82", "#6e6260"))
g = blank()
shade(g, ell(7.5, 7.8, 4.8, 4.4), "ABCD")
shade(g, lambda x, y: 5 <= x <= 10 and 10 <= y <= 13, "ABCD")
rect(g, 4, 7, 6, 9, "C")
rect(g, 9, 7, 11, 9, "C")
eyes(g)
pts(g, ((7, 10), (8, 10)), "k")
for x in (5, 7, 9):
    put(g, x, 12, "k")
add("enemy_skeleton", g, BONE)

# ---- slime hill
SLIME = ramp("ABCD", ("#d4fff0", "#78ecc4", "#38b4a4", "#20707c"))
g = blank()
shade(g, lambda x, y: ell(7.5, 10.5, 6.2, 5.2)(x, y) and y <= 13, "ABCD")
pts(g, ((4, 7), (4, 8), (5, 6)), "W")
eyes(g, 9)
pts(g, ((7, 11), (8, 11)), "D")
add("enemy_jelly_slime", g, SLIME)

CANDY = ramp("ABCD", ("#ffd8f0", "#ff94cc", "#d85ca8", "#8c3478"))
g = blank()
gum = lambda x, y: 3 <= y <= 13 and abs(x - 7.5) <= 1.6 + (y - 3) * 0.62 and not (y == 13 and abs(x - 7.5) > 4.5)
shade(g, gum, "ABCD")
rect(g, 1, 9, 2, 11, "C")
rect(g, 13, 9, 14, 11, "D")
pts(g, ((7, 4), (5, 7), (10, 6), (11, 11), (4, 12), (8, 13), (3, 10)), "W")
eyes(g, 8)
pts(g, ((7, 11), (8, 11)), "D")
add("enemy_gumdrop_golem", g, CANDY)

# ---- twilight desert
SAND = ramp("ABCD", ("#fff0c0", "#f0c070", "#c08848", "#7c5434"))
PINCH = ramp("EFG", ("#e88a50", "#b85a34", "#7a3424"))
g = blank()
for x, y in ((8, 7), (9, 6), (10, 5), (10, 4), (10, 3), (9, 2), (8, 2)):
    put(g, x, y, "C")
    put(g, x - 1, y, "B") if (x - 1, y) != (7, 2) else None
pts(g, ((6, 2), (6, 3), (7, 3)), "R")
put(g, 6, 2, "W")
shade(g, ell(7.5, 10.4, 4.8, 3.4), "ABCD")
for cx in (2.2, 12.8):
    shade(g, lambda x, y, cx=cx: ell(cx, 5.6, 2, 2.4)(x, y) and not (abs(x - cx) < 0.8 and y <= 5), "EFFG")
pts(g, ((3, 9), (2, 8), (12, 9), (13, 8)), "F")
eyes(g, 9)
pts(g, mirror([(3, 13), (4, 14)]), "D")
add("enemy_sand_scorpion", g, {**SAND, **PINCH, "R": "#ff5040"})

DUST = ramp("ABCD", ("#f4e4c4", "#d0b48c", "#a08464", "#6c5448"))
g = blank()
shade(g, lambda x, y: ell(7.5, 7.5, 5, 5)(x, y) or (7 <= y <= 14 and abs(x - 7.5) <= 5 - (y - 7) * 0.35), "ABCD")
pts(g, ((3, 14), (6, 14), (7, 13), (9, 14), (12, 14), (4, 13), (11, 13)), ".")
shade(g, ell(7.5, 8.8, 3.2, 3), "zzzz")
eyes(g, iris="Q")
add("enemy_dust_wraith", g, {**DUST, "z": "#2a1c24", "Q": "#7af0ff"})

JACK = ramp("ABCD", ("#ffd890", "#e8a450", "#b06c34", "#6c4028"))
EAR = [(3, 1), (3, 2), (4, 2), (3, 3), (4, 3), (5, 3), (3, 4), (4, 4), (5, 4), (6, 4)]
g = blank()
pts(g, EAR, "B")
pts(g, [(15 - x, y) for x, y in EAR], "C")
pts(g, ((4, 3), (4, 4), (11, 3), (11, 4)), "p")
shade(g, HEAD, "ABCD")
shade(g, ell(7.5, 11.4, 2.6, 1.8), "AAEE")
pts(g, ((7, 10), (8, 10)), "k")
eyes(g)
pts(g, ((4, 9), (11, 9)), "N")
rect(g, 4, 13, 11, 14, "Y")
pts(g, ((5, 14), (7, 14), (9, 14), (11, 13), (4, 14)), "N")
add("enemy_mirage_jackal", g, {**JACK, "E": "#f0d0a0", "p": "#e88a8a", "N": "#3c78e0", "Y": "#f0c040"})

MUM = ramp("ABCD", ("#f6f0d8", "#d6cfae", "#a4a68c", "#6a7870"))
g = blank()
shade(g, lambda x, y: HEAD(x, y) or (4 <= x <= 11 and 12 <= y <= 14), "ABCD")
for x in range(3, 13):  # bandage seams: slanted rows
    for y0 in (5, 11, 13):
        y = y0 + (1 if x > 7 else 0)
        if y <= 14 and g[y][x] in "AB":
            put(g, x, y, "C")
rect(g, 4, 7, 11, 10, "z")
pts(g, ((4, 7), (11, 10)), "C")
eyes(g, iris="G")
pts(g, ((3, 4), (2, 5), (2, 6), (3, 7), (12, 12), (13, 13)), "S")
add("enemy_sunken_mummy", g, {**MUM, "z": "#2a2830", "G": "#60ff90", "S": "#4c9c44"})

# ---- rust belt
RAT = ramp("ABCD", ("#d4ccd0", "#a49aa4", "#6e6678", "#463e52"))
g = blank()
shade(g, ell(3.8, 4.8, 2.4, 2.4), "ABCD")
shade(g, ell(11.2, 4.8, 2.4, 2.4), "ABCD")
shade(g, ell(3.8, 4.8, 1.2, 1.2), "PPpp")
pts(g, ((11, 4), (12, 4), (11, 5), (12, 5)), "S")
put(g, 11, 4, "W")
shade(g, ell(7.5, 9, 4.4, 4.2), "ABCD")
shade(g, lambda x, y: (6 <= x <= 9 and y == 12) or (7 <= x <= 8 and y == 13), "AABB")
pts(g, ((7, 13), (8, 13)), "p")
eyes(g)
pts(g, ((2, 11), (3, 11), (12, 11), (13, 11), (2, 10), (13, 10)), "A")
add("enemy_scrap_rat", g, {**RAT, "P": "#ffb8c0", "p": "#e07888", "S": "#c0cad8"})

RUST = ramp("ABCD", ("#ffb880", "#e07c48", "#a84c30", "#64302c"))
g = blank()
shade(g, lambda x, y: 3 <= x <= 12 and 4 <= y <= 13 and not (x in (3, 12) and y in (4, 13)), "ABCD")
pts(g, ((7, 3), (7, 2)), "S")
put(g, 7, 1, "R")
rect(g, 4, 7, 11, 10, "z")
eyes(g, iris="R")
for x in (5, 7, 9):
    rect(g, x, 12, x + 1, 12, "D")
pts(g, ((4, 5), (11, 5)), "S")
pts(g, ((4, 12), (12, 9), (3, 7)), "D")
add("enemy_rust_bot", g, {**RUST, "S": "#c0cad8", "R": "#ff4030", "z": "#2a1a1e"})

CRUST = ramp("ABCD", ("#8c8494", "#5e5868", "#3e3a4a", "#26222e"))
g = blank()
shade(g, ell(7.5, 12.4, 6.4, 2.4), "BCDD")
shade(g, HEAD, "ABCD")
pts(g, ((5, 5), (6, 5), (7, 4), (10, 5), (11, 6), (3, 10), (12, 10)), "F")
pts(g, ((6, 5), (10, 5)), "Y")
pts(g, ((4, 12), (11, 12)), "F")
eyes(g, iris="F")
pts(g, ((5, 12), (4, 13), (10, 12), (11, 13)), "E")
add("enemy_slag_crawler", g, {**CRUST, "F": "#ff7a30", "Y": "#ffe870", "E": "#e2d6b4"})

IRON = ramp("ABCD", ("#b4bccc", "#7a8498", "#4c5468", "#2c3244"))
g = blank()
shade(g, lambda x, y: 1 <= x <= 14 and 11 <= y <= 14 and not (y == 11 and x in (1, 14)), "ABCD")
shade(g, ell(7.5, 7.6, 4.2, 4.2), "ABCD")
horn = [(3, 6), (2, 5), (2, 4), (2, 3), (3, 2)]
pts(g, horn, "H")
pts(g, [(15 - x, y) for x, y in horn], "h")
rect(g, 4, 8, 11, 9, "z")
eyes(g, iris="F")
rect(g, 6, 12, 9, 14, "F")
rect(g, 7, 12, 8, 13, "Y")
add("enemy_foundry_brute", g, {**IRON, "H": "#fff4dc", "h": "#c8b898", "z": "#161a24", "F": "#ff7030", "Y": "#ffe880"})

# ---- cadrega city
GATOR = ramp("ABCD", ("#b8e080", "#78b050", "#4a8040", "#2c5038"))
g = blank()
shade(g, lambda x, y: ell(7.5, 7.6, 5, 3.4)(x, y) or (5 <= x <= 10 and 8 <= y <= 14 and not (y == 14 and x in (5, 10))), "ABCD")
shade(g, ell(5.4, 5.2, 2, 1.8), "ABCD")
shade(g, ell(9.6, 5.2, 2, 1.8), "ABCD")
eyes(g, 5)
pts(g, ((6, 13), (9, 13)), "D")
pts(g, ((4, 9), (4, 11), (11, 10), (11, 12), (4, 13), (11, 14)), "W")
pts(g, ((7, 9), (8, 10), (7, 11)), "C")
add("enemy_canal_gator", g, GATOR)

HOOD = ramp("ABCD", ("#a88ad8", "#7a5cb0", "#54408a", "#342860"))
g = blank()
shade(g, lambda x, y: ell(7.5, 7.2, 5.2, 5.4)(x, y) or (3 <= x <= 12 and 10 <= y <= 14), "ABCD")
shade(g, ell(7.5, 9, 3.4, 3), "SSTT")
rect(g, 4, 6, 11, 6, "D")
eyes(g)
shade(g, lambda x, y: 4 <= x <= 11 and 11 <= y <= 12, "RRrr")
pts(g, ((13, 9), (13, 8), (14, 7), (14, 6)), "H")
put(g, 13, 10, "b")
add("enemy_alley_cutpurse", g, {**HOOD, "S": "#f4c8a0", "T": "#d09878", "R": "#ff5060", "r": "#b03048", "H": "#e6eef8", "b": "#7a4c28"})

BRASS = ramp("ABCD", ("#fff0a0", "#f0c040", "#c08820", "#7a4c18"))
g = blank()
pts(g, ((5, 3), (7, 2), (8, 2), (10, 3), (4, 4), (11, 4)), "C")
shade(g, HEAD, "ABCD")
shade(g, ell(7.5, 9, 3.6, 2.6), "DDDD")
eyes(g, iris="G")
pts(g, ((3, 8), (12, 8), (7, 5), (8, 5)), "D")
rect(g, 6, 12, 9, 12, "D")
put(g, 5, 6, "A")
add("enemy_brass_automaton", g, {**BRASS, "G": "#7af0ff"})

g = blank()
shade(g, ell(2.6, 6, 2.2, 3.2), "XXZZ")
shade(g, ell(12.4, 6, 2.2, 3.2), "XZZZ")
shade(g, ell(7.5, 9, 3.8, 3.8), "HIJL")
pts(g, ((7, 4), (8, 4), (3, 8), (3, 9), (12, 8), (12, 9), (7, 13), (8, 13), (4, 5), (11, 5), (4, 12), (11, 12)), "J")
eyes(g, 9)
pts(g, ((7, 6), (8, 6)), "Y")
add("enemy_gear_sprite", g, {**STEEL, "X": "#e0fbff", "Z": "#90dcf0", "Y": "#ffe070"})

# ---- aerial glades
HARP = ramp("ABCD", ("#ffffff", "#d8e8ff", "#9cb8e8", "#6478b8"))
g = blank()
shade(g, ell(2.6, 8.5, 2.4, 4.6), "CDEE")
shade(g, ell(12.4, 8.5, 2.4, 4.6), "DDEE")
pts(g, ((1, 12), (2, 13), (14, 12), (13, 13)), "E")
shade(g, HEAD, "ABCD")
pts(g, ((6, 3), (7, 2), (8, 3), (9, 2), (10, 3)), "C")
eyes(g)
pts(g, ((7, 10), (8, 10), (7, 11)), "Y")
pts(g, ((8, 11), (8, 12)), "y")
add("enemy_cloud_harpy", g, {**HARP, "E": "#3c4c8c", "Y": "#f0c040", "y": "#c08820"})

MIST = ramp("ABCD", ("#ffffff", "#d0f6f0", "#8cd4d4", "#5096b0"))
g = blank()
shade(g, lambda x, y: ell(5, 7.4, 3.4, 3.2)(x, y) or ell(10, 7, 3.6, 3.4)(x, y) or ell(7.5, 9.6, 5.8, 3)(x, y), "ABCD")
pts(g, ((6, 13), (7, 13), (8, 13), (9, 14), (10, 14)), "C")
pts(g, ((5, 12), (4, 13)), "B")
eyes(g)
add("enemy_mist_elemental", g, MIST)

STORM = ramp("ABCD", ("#fffff0", "#ffe858", "#f0b030", "#b8702c"))
g = blank()
arcs = [(7, 2), (8, 3), (13, 8), (14, 7), (2, 9), (1, 8), (7, 14), (8, 13), (3, 4), (4, 5), (12, 4), (11, 5), (3, 13), (4, 12), (12, 13), (11, 12)]
pts(g, arcs, "B")
shade(g, ell(7.5, 8.5, 4.4, 4.4), "ABCD")
pts(g, ((5, 6), (6, 5)), "A")
eyes(g)
add("enemy_storm_wisp", g, STORM)

# ---- star kingdom
ROSE = ramp("ABCD", ("#ffb0c0", "#f05070", "#b02c50", "#6a1840"))
g = blank()
shade(g, ell(3.6, 12.6, 2.6, 1.6), "LLGG")
shade(g, ell(11.4, 12.6, 2.6, 1.6), "LGGG")
pts(g, ((1, 12), (14, 12), (7, 14), (8, 14)), "G")
pts(g, ((0, 12), (15, 12)), "E")
shade(g, lambda x, y: ell(7.5, 7.5, 5.4, 4.8)(x, y) and not (y == 3 and x in (5, 10)), "BCCD")
shade(g, ell(7.5, 8.3, 3.8, 3.4), "ABBC")
pts(g, ((4, 5), (7, 4), (10, 5), (3, 8), (12, 8)), "D")
eyes(g)
add("enemy_thorn_bloom", g, {**ROSE, "L": "#90d860", "G": "#4c9c44", "E": "#fff4dc"})

IMP = ramp("ABCD", ("#ff9c7c", "#e85848", "#a8304c", "#641c3c"))
g = blank()
horn = [(2, 2), (3, 3), (3, 4), (4, 5)]
pts(g, horn, "H")
pts(g, [(15 - x, y) for x, y in horn], "h")
pts(g, ((7, 1), (7, 2), (8, 2), (6, 3), (7, 3), (8, 3), (9, 3)), "O")
pts(g, ((7, 2), (8, 3)), "Y")
pts(g, ((2, 8), (1, 7), (2, 9)), "B")
pts(g, ((13, 8), (14, 7), (13, 9)), "C")
shade(g, HEAD, "ABCD")
eyes(g)
rect(g, 6, 11, 9, 11, "D")
pts(g, ((6, 11), (9, 11)), "H")
add("enemy_comet_imp", g, {**IMP, "H": "#fff4dc", "h": "#c8b898", "O": "#ff9a40", "Y": "#ffe070"})

ROCK = ramp("ABCD", ("#b0a4ac", "#7c7080", "#504658", "#2e2838"))
g = blank()
ear = [(3, 3), (3, 4), (4, 4), (4, 5), (5, 4)]
pts(g, ear, "B")
pts(g, [(15 - x, y) for x, y in ear], "C")
pts(g, ((6, 3), (7, 2), (8, 2), (9, 3), (7, 1)), "F")
pts(g, ((7, 2), (8, 3)), "Y")
shade(g, HEAD, "ABCD")
shade(g, ell(7.5, 11.4, 2.6, 1.8), "AABB")
pts(g, ((7, 10), (8, 10)), "k")
pts(g, ((4, 6), (5, 5), (11, 6), (12, 10), (3, 10)), "F")
eyes(g)
add("enemy_meteor_hound", g, {**ROCK, "F": "#ff7a30", "Y": "#ffe870"})

STONE = ramp("ABCD", ("#f4f0ff", "#c8c0e8", "#8c84bc", "#5a5488"))
g = blank()
shade(g, lambda x, y: 3 <= x <= 12 and 3 <= y <= 13 and not (x in (3, 12) and y in (3, 13)), "ABCD")
pts(g, ((7, 3), (8, 3), (6, 4), (7, 4), (8, 4), (9, 4), (7, 5), (8, 5)), "Y")
put(g, 7, 3, "W")
eyes(g)
rect(g, 6, 11, 9, 11, "D")
pts(g, ((4, 11), (11, 6), (10, 12)), "C")
add("enemy_star_sentinel", g, {**STONE, "Y": "#ffd848"})

MOTH = ramp("ABCD", ("#f8f0ff", "#d8c8f8", "#a898e0", "#6c60a8"))
g = blank()
shade(g, ell(3.4, 6.4, 3, 3.8), "ABCD")
shade(g, ell(11.6, 6.4, 3, 3.8), "ABCD")
shade(g, ell(4, 11.6, 2.6, 2.4), "BCCD")
shade(g, ell(11, 11.6, 2.6, 2.4), "BCDD")
pts(g, ((2, 5), (2, 6), (3, 7)), "M")
pts(g, ((13, 5), (13, 6), (12, 7)), "M")
shade(g, ell(7.5, 9, 3, 3.8), "EFGG")
pts(g, ((6, 5), (5, 4), (5, 3), (4, 2), (9, 5), (10, 4), (10, 3), (11, 2)), "E")
eyes(g)
add("enemy_moon_moth", g, {**MOTH, "M": "#ffe888", "E": "#fff4d8", "F": "#e0c898", "G": "#a88c68"})

SHADE = ramp("ABCD", ("#6a5aa8", "#4a3c80", "#2e2458", "#1e163e"))
g = blank()
shade(g, lambda x, y: ell(7.5, 7.2, 5, 5)(x, y) or (7 <= y <= 14 and abs(x - 7.5) <= 5), "ABCD")
pts(g, ((3, 14), (5, 13), (7, 14), (10, 13), (12, 14)), ".")
shade(g, ell(7.5, 8.8, 3.4, 3.2), "zzzz")
eyes(g, iris="L")
add("enemy_hollow_shade", g, {**SHADE, "z": "#0c0818", "L": "#c8b8ff"})

VOID = ramp("ABCD", ("#8c6cd8", "#5c40a8", "#3a2878", "#1c1440"))
g = blank()
pts(g, EAR, "B")
pts(g, [(15 - x, y) for x, y in EAR], "C")
shade(g, HEAD, "ABCD")
shade(g, ell(7.5, 11.4, 2.6, 1.8), "AABB")
pts(g, ((7, 10), (8, 10)), "k")
pts(g, ((7, 4), (8, 5), (7, 6)), "P")
pts(g, ((4, 11), (11, 6), (5, 5)), "W")
eyes(g, iris="P")
add("enemy_void_hound", g, {**VOID, "P": "#ff6ad8"})

g = blank()
shade(g, ell(7.5, 8, 5.8, 5.2), "ABCD")
pts(g, ((3, 12), (2, 13), (2, 14), (6, 13), (6, 14), (9, 13), (9, 14), (12, 12), (13, 13), (13, 14)), "C")
shade(g, ell(7.5, 8.5, 2.8, 2.2), "WWEE")
rect(g, 7, 8, 8, 9, "P")
pts(g, ((7, 8), (8, 9)), "k")
pts(g, ((4, 5), (11, 5), (4, 11), (11, 11)), "P")
pts(g, ((3, 8), (12, 8)), "W")
add("enemy_unmade_horror", g, {**VOID, "P": "#ff6ad8", "E": "#d8c8f0"})

NULL = ramp("ABCD", ("#8890a8", "#5c6480", "#383e58", "#1c2034"))
g = blank()
shade(g, lambda x, y: 3 <= x <= 12 and 3 <= y <= 14 and not (x in (3, 12) and y in (3, 14)), "ABCD")
rect(g, 7, 1, 8, 2, "W")
rect(g, 4, 8, 11, 8, "W")
rect(g, 4, 9, 11, 9, "z")
rect(g, 7, 10, 8, 12, "z")
rect(g, 3, 13, 12, 13, "B")
add("enemy_null_knight", g, {**NULL, "z": "#0c0e18"})

# ---------------------------------------------------------------- bosses: bigger head, gold crown/halo/trim
ci.GROUP = "bosses"
GOLD = {"Y": "#fff0a0", "y": "#f0c040", "u": "#c08820", "v": "#7a4c18", "r": "#ff4060"}


def crown(g, x0, x1, y, jewel=True):
    """A gold crown spanning x0..x1, its band on rows y-1..y, three points above."""
    rect(g, x0, y - 1, x1, y - 1, "y")
    rect(g, x0, y, x1, y, "u")
    for x in (x0, (x0 + x1) // 2, x1):
        put(g, x, y - 2, "y")
    pts(g, ((x0, y - 2), (x0, y - 1)), "Y")
    if jewel:
        put(g, (x0 + x1) // 2, y - 1, "r")


g = blank()
shade(g, lambda x, y: 1 <= x <= 14 and 11 <= y <= 14 and not (y == 11 and x in (1, 14)), "ABCD")
pts(g, ((0, 10), (15, 10), (1, 10), (14, 10)), "B")
shade(g, BIG, "ABCD")
shade(g, ell(7.5, 9.2, 3.6, 2.8), "zzzz")
eyes(g, 8, iris="G")
crown(g, 3, 12, 4)
add("enemy_gravewarden", g, {**ramp("ABCD", ("#a8b4cc", "#6a7894", "#444e6c", "#262c44")), **GOLD, "z": "#0c0e18", "G": "#60ff90"})

g = blank()
shade(g, lambda x, y: ell(7.5, 10.4, 7, 5.4)(x, y) and y <= 14, "ABCD")
pts(g, ((3, 8), (3, 9), (4, 7)), "W")
eyes(g, 9)
pts(g, ((7, 12), (8, 12)), "D")
crown(g, 4, 11, 5)
add("enemy_king_slime", g, {**ramp("ABCD", ("#c8eeff", "#68b8f4", "#3474d0", "#1c4294")), **GOLD})

g = blank()
nemes = lambda x, y: 2 <= y <= 14 and abs(x - 7.5) <= 4.2 + max(0, y - 6) * 0.45 and not (y == 2 and abs(x - 7.5) > 3)
for y in range(N):
    for x in range(N):
        if nemes(x, y):
            put(g, x, y, ("y" if x < 8 else "u") if y % 2 == 0 else ("N" if x < 8 else "n"))
shade(g, ell(7.5, 8.8, 3.2, 3.8), "SSTT")
eyes(g)
pts(g, ((4, 8), (11, 8)), "k")
pts(g, ((7, 2), (8, 2), (7, 3), (8, 3)), "G")
put(g, 7, 2, "Y")
pts(g, ((7, 12), (8, 12), (7, 13), (8, 13)), "u")
put(g, 7, 13, "N")
add("enemy_dune_pharaoh", g, {**GOLD, "N": "#4a88f0", "n": "#2a56b0", "S": "#e8b880", "T": "#b88050", "G": "#60e070"})

g = blank()
shade(g, lambda x, y: 1 <= x <= 14 and 3 <= y <= 14 and not (x in (1, 14) and y in (3, 14)), "ABCD")
for x0 in (2, 11):
    rect(g, x0, 0, x0 + 2, 2, "S")
    rect(g, x0 + 2, 0, x0 + 2, 2, "s")
rect(g, 3, 6, 12, 10, "z")
rect(g, 9, 7, 11, 9, "R")
put(g, 9, 7, "W")
rect(g, 4, 7, 5, 8, "R")
put(g, 4, 7, "W")
for x in range(4, 12, 2):
    rect(g, x, 12, x, 13, "S")
pts(g, ((2, 4), (13, 4), (2, 13), (13, 13), (7, 4), (8, 4)), "y")
add("enemy_scrap_titan", g, {**RUST, **GOLD, "S": "#c0cad8", "s": "#5a6678", "R": "#ff3030", "z": "#1a1216"})

g = blank()
shade(g, lambda x, y: 2 <= x <= 13 and 13 <= y <= 14, "Yyuv")
shade(g, BIG, "ABCD")
eyes(g)
for x, y in ((8, 7), (11, 7), (8, 10), (11, 10), (8, 8), (8, 9), (11, 8), (11, 9), (9, 6), (10, 6), (9, 11), (10, 11)):
    put(g, x, y, "u")
pts(g, ((6, 11), (7, 11), (8, 11), (5, 12)), "C")
crown(g, 3, 12, 4)
pts(g, ((5, 2), (10, 2)), "y")
add("enemy_clockwork_regent", g, {**ramp("ABCD", ("#ffffff", "#f0e8d8", "#c8bca4", "#8c8070")), **GOLD})

g = blank()
shade(g, lambda x, y: x <= 6 and 4 <= y <= 13 and y >= 4 + (6 - x) * 0.6, "BCDD")
shade(g, lambda x, y: x >= 9 and 4 <= y <= 13 and y >= 4 + (x - 9) * 0.6, "CCDD")
pts(g, ((0, 11), (1, 12), (15, 11), (14, 12), (0, 9), (15, 9)), "y")
shade(g, BIG, "ABCD")
pts(g, ((6, 2), (7, 1), (8, 2), (9, 1), (7, 3), (8, 3)), "y")
eyes(g)
pts(g, ((7, 10), (8, 10), (7, 11), (8, 11)), "y")
put(g, 8, 12, "u")
add("enemy_storm_roc", g, {**ramp("ABCD", ("#f0f4ff", "#a8c0f0", "#5874c8", "#2c3c8c")), **GOLD})

g = blank()
for a in range(16):
    t = a * math.pi / 8
    put(g, round(7.5 + 7 * math.cos(t)), round(8 + 6.6 * math.sin(t)), "Y" if a % 2 == 0 else "y")
shade(g, lambda x, y: 3 <= x <= 12 and 3 <= y <= 14 and not (x in (3, 12) and y in (3, 14)), "Yyuv")
rect(g, 4, 7, 11, 10, "z")
eyes(g, iris="C")
pts(g, ((7, 2), (8, 2), (7, 3), (8, 3), (7, 4), (8, 4)), "W")
rect(g, 7, 11, 8, 13, "u")
add("enemy_star_warden", g, {**GOLD, "z": "#1a1430", "C": "#7af0ff"})

g = blank()
shade(g, ell(7.5, 9, 5.2, 4.8), "ABCD")
shade(g, lambda x, y: 5 <= x <= 10 and 11 <= y <= 14, "ABCD")
for x in (3, 5, 7, 9, 11, 12):
    rect(g, x, 2, x, 4, "V")
rect(g, 3, 4, 12, 5, "v")
pts(g, ((3, 1), (7, 1), (12, 1), (5, 2), (9, 2)), "P")
rect(g, 4, 7, 6, 10, "D")
rect(g, 9, 7, 11, 10, "D")
eyes(g, 8, iris="P")
pts(g, ((7, 11), (8, 11)), "k")
for x in (5, 7, 9):
    put(g, x, 13, "k")
add("enemy_the_hollow_king", g, {**BONE, "V": "#7a5ab8", "v": "#3a2468", "P": "#ff6ad8"})

ci.main()
