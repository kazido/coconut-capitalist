"""Generate species_* tree icons (16x16, free, auto plum outline) as TOML. Light from the top-left."""
import math

N = 16


def blank():
    return [["." for _ in range(N)] for _ in range(N)]


def shade_blob(g, mask, cx, cy, r, ramp, texture=True):
    """ramp = 4 letters light->dark. Light comes from the top-left."""
    for y in range(N):
        for x in range(N):
            if not mask(x, y):
                continue
            l = -((x - cx) + (y - cy)) / (math.sqrt(2) * r)
            i = 0 if l > 0.55 else 1 if l > 0.0 else 2 if l > -0.55 else 3
            # bottom-right rim always in shadow
            if not mask(x + 1, y + 1) and i < 2:
                i = 2
            # leaf clumps: a deterministic sprinkle one tone darker
            if texture and i < 3 and (x * 5 + y * 3) % 7 == 0:
                i += 1
            g[y][x] = ramp[i]


def trunk(g, x0, x1, y0, y1, light="B", dark="b"):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if g[y][x] == ".":
                g[y][x] = light if x == x0 else dark


def circle(cx, cy, r):
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def ellipse(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def union(*ms):
    return lambda x, y: any(m(x, y) for m in ms)


LEAF = {"H": "#b6e86a", "m": "#6cc044", "s": "#3c8c34", "d": "#22582a"}
BARK = {"B": "#9a6a44", "b": "#5e3c2c"}
sprites = {}

# Oak: broad round canopy of three lobes, thick trunk.
g = blank()
trunk(g, 6, 8, 10, 14)
g[14][5] = "b"; g[14][9] = "b"  # roots
shade_blob(g, union(circle(7.5, 6, 5.2), circle(4, 7.5, 3.2), circle(11, 7.5, 3.2)), 7.5, 6, 6, "Hmsd")
sprites["species_oak"] = (g, {**LEAF, **BARK})

# Birch: slim pale trunk with dark marks, small light oval canopy.
g = blank()
trunk(g, 7, 8, 8, 14, "W", "w")
for y in (9, 12):
    g[y][8] = "k"
g[11][7] = "k"
shade_blob(g, ellipse(7.5, 5, 4.2, 4), 7.5, 5, 4.2, "Hmsd")
sprites["species_birch"] = (g, {"H": "#d8f28a", "m": "#9cd64e", "s": "#5a9e3a", "d": "#346a2c",
                                 "W": "#f4eee4", "w": "#c8bcb0", "k": "#3a2e34"})

# Willow: dome with drooping strands down both sides.
g = blank()
trunk(g, 7, 8, 8, 14)
g[14][6] = "b"; g[14][9] = "b"
# Weeping curtain: a low crown, then long hanging strands that fall almost to the ground at the sides
# and stop short in the middle so the trunk shows. Ragged ends, alternating strand tones.
crown = ellipse(7.5, 3.2, 6.2, 2.4)
L = {1: 10, 2: 12, 3: 13, 4: 11, 5: 12, 6: 8, 7: 6, 8: 6, 9: 8, 10: 12, 11: 11, 12: 13, 13: 12, 14: 10}
curtain = lambda x, y: x in L and 3 <= y <= L[x]
mask = union(crown, curtain)
for y in range(N):
    for x in range(N):
        if not mask(x, y):
            continue
        l = -((x - 7.5) * 0.8 + (y - 5)) / 7
        i = 0 if l > 0.35 else 1 if l > -0.1 else 2
        if y > 4 and x % 2 == 0:
            i += 1  # strands: every other column a tone darker
        if y == L.get(x, -1) and y > 6:
            i = max(i, 2)  # strand tips in shadow
        g[y][x] = "Hmsd"[min(i, 3)]
sprites["species_willow"] = (g, {"H": "#c4e890", "m": "#86c45a", "s": "#4e8e40", "d": "#2c5a30", **BARK})

# Pine: three stacked triangles, dark cool green.
g = blank()
trunk(g, 7, 8, 12, 14)
tiers = lambda x, y: any(t0 <= y <= t1 and abs(x - 7.5) <= (y - t0) * 0.75 + 0.5 for t0, t1 in ((1, 5), (4, 8), (7, 11)))
shade_blob(g, tiers, 7.5, 6, 6, "Hmsd", texture=False)
sprites["species_pine"] = (g, {"H": "#7ec870", "m": "#3e9a52", "s": "#236a42", "d": "#14432e", **BARK})

# Chestnut: round dark canopy with spiky brown nuts.
g = blank()
trunk(g, 6, 8, 10, 14)
shade_blob(g, union(circle(7.5, 6, 5.4), circle(3.5, 8, 2.5), circle(11.5, 8, 2.5)), 7.5, 6, 6, "Hmsd")
for x, y in ((5, 5), (10, 7), (7, 9)):
    g[y][x] = "N"; g[y][x + 1] = "n"
sprites["species_chestnut"] = (g, {"H": "#9ad25a", "m": "#5aa83a", "s": "#33772e", "d": "#1d4a24",
                                    "N": "#c88a4a", "n": "#7a4a2a", **BARK})

# Cherry: pink blossom cloud, dark trunk.
g = blank()
trunk(g, 7, 8, 10, 14, "B", "b")
g[10][6] = "b"; g[9][5] = "b"  # a branch peeking out
shade_blob(g, union(circle(7.5, 5.5, 4.8), circle(4, 7.5, 3), circle(11, 7.5, 3)), 7.5, 6, 6, "Hmsd")
sprites["species_cherry"] = (g, {"H": "#ffe4ee", "m": "#ffa6c8", "s": "#e06a9c", "d": "#a03c6e",
                                  "B": "#7a4a3c", "b": "#4a2a2c"})

# Redwood: tall red-brown trunk, narrow cone canopy.
g = blank()
trunk(g, 7, 8, 9, 14, "R", "r")
g[14][6] = "r"; g[14][9] = "r"
shade_blob(g, ellipse(7.5, 5.5, 3.6, 5), 7.5, 5.5, 4.5, "Hmsd")
sprites["species_redwood"] = (g, {"H": "#86c66a", "m": "#4a9248", "s": "#2c6438", "d": "#183e28",
                                   "R": "#c0583c", "r": "#7a3026"})

# Emberwood: charred trunk, glowing ember canopy (amber -> deep red).
g = blank()
trunk(g, 7, 8, 10, 14, "B", "b")
g[11][6] = "b"; g[10][9] = "b"
shade_blob(g, union(circle(7.5, 6, 5), circle(4.5, 8, 2.6), circle(10.5, 8, 2.6)), 7.5, 6, 6, "Hmsd")
sprites["species_emberwood"] = (g, {"H": "#fff2a0", "m": "#ffb43c", "s": "#e05a26", "d": "#8c2a24",
                                     "B": "#4a3a3a", "b": "#2a2024"})

# Palm: hand-drawn (fronds are not a blob).
palm = [
    "................",
    "....HHm..HHH....",
    "..HHmmmmHmmmsd..",
    ".Hm..mmCmmm..sd.",
    ".m..mmCcCmms..d.",
    "...m..cCc..s....",
    "..m....Bb...s...",
    ".......Bb.......",
    "......Bb........",
    "......Bb........",
    "......Bb........",
    ".....Bb.........",
    ".....Bb.........",
    ".....Bb.........",
    "....BBbb........",
    "................",
]
sprites["species_palm"] = ([list(r) for r in palm], {"H": "#b6e86a", "m": "#6cc044", "s": "#3c8c34", "d": "#22582a",
                                                     "C": "#a8743c", "c": "#6a4428", **BARK})

out = ["# Tree species icons (species_<id>), free with plum outline. Generated by a script; approved by the owner.\n"]
for name, (g, pal) in sprites.items():
    used = {c for row in g for c in row if c != "."}
    pal = {k: v for k, v in pal.items() if k in used}
    out.append(f"[{name}]")
    out.append('kind = "free"')
    out.append("outline = true")
    out.append("palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items()) + " }")
    out.append("rows = [")
    out += [f'  "{"".join(r)}",' for r in g]
    out.append("]\n")


import sys
open(sys.argv[1], "w").write("\n".join(out))
