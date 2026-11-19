"""Area emoji (area_<id>), one per world area. 16x16, free, plum outline (added by the build), light from the top-left.
Run: python art/gen/areas.py art/sprites/areas.toml
"""
import math
import sys

sys.path.insert(0, ".")
from art.draw import Canvas  # noqa: E402

c = Canvas()


def ell(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def each(mask):
    return [(x, y) for y in range(16) for x in range(16) if mask(x, y)]


# --- Slime Hill: a plump aqua slime sitting on a grassy green hill ------------------------------------------------------
hill = lambda x, y: ell(7.5, 16.5, 8.2, 5.6)(x, y) and y <= 14  # noqa: E731
for x, y in each(hill):
    top = not hill(x, y - 1)
    c.put(x, y, "G" if top else ("g" if (x + y) % 5 else "f") if x < 9 else "H" if top else "h")  # a lit grassy rim
slime = lambda x, y: ell(7.5, 8.8, 5.0, 4.6)(x, y) and y <= 11  # noqa: E731  (a dome with a flat base)
for x, y in each(slime):
    lit = -((x - 6) + (y - 7)) / 6
    c.put(x, y, "S" if lit > 0.35 else "s" if lit > -0.35 else "T")
for x, y in ((4, 7), (5, 6), (5, 5), (6, 5)):
    c.put(x, y, "W")  # a wet shine
c.put(6, 8, "k"), c.put(6, 9, "k"), c.put(9, 8, "k"), c.put(9, 9, "k")  # tall eyes
c.put(7, 10, "m"), c.put(8, 10, "m")  # a little smile
c.put(4, 9, "p"), c.put(11, 9, "p")  # blushing cheeks
c.sprite("area_slime_hill", {"G": "#a6e070", "g": "#6cbf4c", "f": "#ffe680", "H": "#7cc254", "h": "#3f8a36",
                             "S": "#a8f4f0", "s": "#4ccfd8", "T": "#2a8aa8", "W": "#ffffff", "k": "#123040",
                             "m": "#1e4a5c", "p": "#ff9ab0"})

# --- Twilight Desert: dunes under a night sky, a crescent moon and stars --------------------------------------------------
sky = lambda x, y: 1 <= x <= 14 and 1 <= y <= 14 and not ((x in (1, 14)) and (y in (1, 14)))  # noqa: E731  (rounded corners)
for x, y in each(sky):
    c.put(x, y, "N" if y < 6 else "n" if y < 10 else "v")  # deep night fading to a violet horizon
moon = lambda x, y: ell(10.5, 4.5, 2.6, 2.6)(x, y) and not ell(11.6, 3.7, 2.1, 2.1)(x, y)  # noqa: E731
for x, y in each(moon):
    c.put(x, y, "M")
for x, y in ((3, 3), (6, 2), (4, 6), (13, 7), (8, 5)):
    c.put(x, y, "w")  # stars
back = lambda x, y: sky(x, y) and y >= 10 + 2.2 * math.cos((x - 10.5) / 2.6)  # noqa: E731
front = lambda x, y: sky(x, y) and y >= 11 + 2.0 * math.cos((x - 4) / 2.4)  # noqa: E731
for x, y in each(back):
    c.put(x, y, "D" if not back(x, y - 1) else "d")  # moonlit crest, shaded slope
for x, y in each(front):
    c.put(x, y, "E" if not front(x, y - 1) else "e")
c.sprite("area_twilight_desert", {"N": "#1a1c4a", "n": "#2e2a6a", "v": "#5a3a86", "M": "#fff2b0", "w": "#ffffff",
                                  "D": "#e8c088", "d": "#a87850", "E": "#f6dca0", "e": "#c49660"})

# --- Rust Belt: a rusted cog (teeth placed one by one) with a round dark hub ------------------------------------------
body = lambda x, y: 2.6 < math.hypot(x - 7.5, y - 7.5) <= 4.6  # noqa: E731  (a slim ring)
teeth = [(7, 1, 8, 2), (7, 13, 8, 14), (1, 7, 2, 8), (13, 7, 14, 8), (3, 3, 4, 4), (11, 3, 12, 4), (3, 11, 4, 12), (11, 11, 12, 12)]
tooth = lambda x, y: any(a <= x <= c_ and b <= y <= d for a, b, c_, d in teeth)  # noqa: E731
c.shade(lambda x, y: body(x, y) or tooth(x, y), "RRrq", 7.5, 7.5, 6.5)
for x, y in each(lambda x, y: math.hypot(x - 7.5, y - 7.5) <= 2.6):
    c.put(x, y, "k")
for x, y in ((10, 4), (4, 10)):
    c.put(x, y, "o")  # a fleck of orange rust, mirrored
c.put(5, 4, "W")
c.sprite("area_rust_belt", {"R": "#d48a4a", "r": "#a85a2a", "q": "#6a3418", "k": "#1e1414", "o": "#ff9a3a", "W": "#ffd8a8"})

# --- Cadrega City: a skyline of buildings in different colours, roofs and lit windows ---------------------------------
blocks = [  # x0, x1, top, wall, shade, roof
    (1, 3, 8, "A", "a", "flat"),
    (4, 6, 4, "B", "b", "dome"),
    (7, 9, 2, "C", "c", "spire"),
    (10, 11, 6, "D", "d", "flat"),
    (12, 14, 5, "E", "e", "point"),
]
for x0, x1, top, wall, shade, roof in blocks:
    c.rect(x0, top, x1, 14, wall)
    c.rect(x1, top, x1, 14, shade)  # the shaded east side
    for wy in range(top + 2, 14, 2):
        for wx in range(x0, x1):
            if (wx + wy) % 2 == 0:
                c.put(wx, wy, "y")  # lit windows
    if roof == "dome":
        c.put(x0 + 1, top - 1, "G"), c.put(x0, top - 1, "g"), c.put(x1, top - 1, "g"), c.put(x0 + 1, top - 2, "G")
    elif roof == "spire":
        c.put(x0 + 1, top - 1, "G"), c.put(x0 + 1, top - 2, "G")
    elif roof == "point":
        c.put(x0 + 1, top - 1, "c"), c.put(x0 + 2, top - 1, "c")
c.rect(0, 14, 15, 14, "k")  # the street
c.sprite("area_cadrega_city", {"A": "#7fc8b8", "a": "#4a8a80", "B": "#e8b48a", "b": "#b07850", "C": "#e8e0c8",
                               "c": "#a89c84", "D": "#8aa0d8", "d": "#5a6aa8", "E": "#d890b8", "e": "#a05a84",
                               "y": "#ffe27a", "G": "#ffd24a", "g": "#c99a2a", "k": "#3a2e40"})

# --- Aerial Glades: a floating island with a pond spilling off its edge as a waterfall --------------------------------
under = lambda x, y: y >= 8 and abs(x - 7) <= 6.5 - (y - 8) * 1.3 and y <= 13  # noqa: E731
for x, y in each(under):
    c.put(x, y, "E" if x < 6 else "e" if x < 9 else "p")
top_ = lambda x, y: ell(7, 7.2, 6.6, 1.9)(x, y) and y <= 8  # noqa: E731
for x, y in each(top_):
    c.put(x, y, "G" if y < 7 else "g")
for x, y in each(lambda x, y: ell(7.5, 7.0, 2.6, 0.9)(x, y)):
    c.put(x, y, "L")  # the pond
c.put(6, 7, "l")
for y in range(7, 15):
    c.put(10, y, "L" if y % 2 else "l")  # the waterfall off the east edge
c.put(10, 14, "F"), c.put(11, 14, "F"), c.put(9, 14, "F")  # foam where it lands
c.rect(3, 4, 3, 6, "t")  # a little tree: a trunk and a round crown
for x, y in each(ell(3.0, 3.0, 2.3, 2.0)):
    c.put(x, y, "T" if (x - 3) + (y - 3) < 0 else "u")
for x, y in ((12, 2), (13, 2), (14, 2), (13, 1)):
    c.put(x, y, "W")  # a wisp of cloud
c.sprite("area_aerial_glades", {"E": "#b8925e", "e": "#8a6a40", "p": "#5a4428", "G": "#a6e070", "g": "#6cbf4c",
                                "L": "#5ac8f0", "l": "#2a8ac8", "F": "#ffffff", "t": "#6a4428", "T": "#8ee07a",
                                "u": "#4e9a48", "W": "#ffffff"})

# --- Star Kingdom: a real castle (towers with blue cone roofs and flags, a keep, a gate) under a big gold star ---------
for x0, x1, top in ((1, 3, 7), (12, 14, 7)):  # the two outer towers
    c.rect(x0, top, x1, 14, "C")
    c.rect(x1, top, x1, 14, "c")
    c.put(x0 + 1, top + 2, "k")  # an arrow slit
    c.line(x0, top - 1, x1, top - 1, "B")  # cone roof
    c.put(x0 + 1, top - 2, "B"), c.put(x0 + 1, top - 3, "b")
    c.put(x0 + 1, top - 4, "f"), c.put(x0 + 2, top - 4, "f")  # a flag
c.rect(4, 9, 11, 14, "C")  # the curtain wall
c.rect(11, 9, 11, 14, "c")
for x in range(4, 12, 2):
    c.put(x, 8, "C")  # battlements
c.rect(6, 5, 9, 9, "C")  # the keep
c.rect(9, 5, 9, 9, "c")
c.line(6, 4, 9, 4, "B"), c.line(7, 3, 8, 3, "B")  # its roof
c.rect(7, 12, 8, 14, "k"), c.put(7, 11, "k"), c.put(8, 11, "k")  # the arched gate
c.put(7, 7, "y")  # a lit window
for x, y in ((7, 0), (6, 1), (7, 1), (8, 1), (7, 2)):
    pass
for x, y in ((13, 1), (12, 2), (13, 2), (14, 2), (13, 3)):
    c.put(x, y, "Y" if (x, y) == (13, 2) else "y")  # the big gold star (top right, clear of the roofs)
c.put(4, 1, "w"), c.put(10, 0, "w"), c.put(1, 3, "w")  # smaller stars
c.sprite("area_star_kingdom", {"C": "#e4def4", "c": "#a69cd0", "B": "#5a8ae8", "b": "#3a5ab0", "f": "#ffc93a",
                               "k": "#2a2244", "y": "#ffe27a", "Y": "#fff8c0", "w": "#ffffff"})

# --- The Void: a black hole, a big black circle ringed by bright bent light, a thin hot disc crossing in front -----------
for x, y in each(lambda x, y: 4.6 < math.hypot(x - 7.5, y - 7.5) <= 6.4):
    a = math.atan2(y - 7.5, x - 7.5)
    c.put(x, y, "u" if math.sin(a) < -0.3 else "v")  # a faint violet glow, brighter over the top
for x, y in each(lambda x, y: 3.6 < math.hypot(x - 7.5, y - 7.5) <= 4.6):
    c.put(x, y, "Y" if y < 7 else "o")  # the photon ring: light bent all the way round
for x, y in each(lambda x, y: math.hypot(x - 7.5, y - 7.5) <= 3.6):
    c.put(x, y, "K")  # the event horizon
for x in range(0, 16):  # the accretion disc, edge-on, crossing in front
    if abs(x - 7.5) <= 7:
        c.put(x, 8, "Y" if abs(x - 7.5) < 2.5 else "o" if abs(x - 7.5) < 5 else "O")
        if 1.5 < abs(x - 7.5) < 6:
            c.put(x, 9, "O")
c.sprite("area_the_void", {"K": "#05030a", "o": "#ffb040", "O": "#c0502a", "Y": "#fff0b0", "u": "#e0c8ff", "v": "#7a4ac8"})

open(sys.argv[1], "w", encoding="utf-8").write(c.toml("# Area emoji (area_<id>), generated by art/gen/areas.py: edit that, never this file."))
print(" ".join(c.done))
