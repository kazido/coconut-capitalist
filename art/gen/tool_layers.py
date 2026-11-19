"""Smithed tools: one base drawing per kind, split into 3 recolourable layers (docs/plans/tools-smithing.md, Art).

A tool is 3 parts, one per layer, each coloured by its own tier from the one shared TIERS table
(palette letters, light -> dark):
  base    P p q Q   the working end: pick head, axe blade, rod reel, can body
  trim    H h k K   what you hold: handle, pole, can handle
  accent  A a       a small wrap, line or spout

`layers()` returns {kind: 16x16 letter grid}; `palette(b, t, a)` colours it for base/trim/accent tiers b/t/a.
The list emoji (tool_<kind>_t<n>) are all three parts at tier n; the bot's runtime renderer recolours the
same grids per tool. Run: python art/gen/tool_layers.py <out.toml> [preview]

`generic` writes the one list emoji per kind (tool_<kind>): a framed Common item in GENERIC tiers. Every smithed
tool shows that pixel emoji; its own colours and cosmetics only appear in the big runtime picture (art_runtime).
Run: python art/gen/tool_layers.py art/sprites/tools_generic.toml generic
"""
import math
import sys

sys.path.insert(0, ".")
from art.draw import Canvas, circ, ell, union  # noqa: E402

# One colour per tier, shared by every part, so a tier reads the same on a head, a handle or a wrap.
# Ramps are light -> dark; the accent (2 letters) uses the middle two shades.
TIERS = {
    1: ("#c89a64", "#a07444", "#76522e", "#4c341c"),  # wood
    2: ("#a49c8e", "#7c7468", "#575148", "#38342e"),  # stone (warm, dull)
    3: ("#c0cad8", "#8a96a8", "#5a6678", "#38404e"),  # iron (cool steel)
    4: ("#fff0a0", "#f0c040", "#c08820", "#7c5410"),  # gold
    5: ("#ffffff", "#e4f4f8", "#aed0dc", "#6e94a4"),  # platinum (bright, icy)
    6: ("#b8ffe0", "#48d8a0", "#20a070", "#106048"),  # emerald / crystal
    7: ("#d8b8ff", "#9860e0", "#6030a8", "#341864"),  # void
}


def poly(pts):
    def m(x, y):
        px, py, inside = x + 0.5, y + 0.5, False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
        return inside
    return m


def diag(c, x0, y0, x1, ramp="hhkK"):
    """A 1px handle from bottom-left (x0, y0) up-right to x1, lighter toward the top."""
    n = x1 - x0
    for i in range(n + 1):
        c.put(x0 + i, y0 - i, ramp[min(3, (n - i) * 4 // (n + 1))])


def rot(tx, ty):
    """Coordinates along the handle (u: toward its top-right tip) and across it (w: toward the bottom-right) from point (tx, ty)."""
    r = math.sqrt(0.5)
    return lambda x, y: ((x - tx - (y - ty)) * r, (x - tx + (y - ty)) * r)


def grab(c):
    g = [row[:] for row in c.g]
    c.g = [["." for _ in range(16)] for _ in range(16)]
    return g


def layers():
    c = Canvas()
    out = {}

    # Pickaxe: 1px diagonal handle, a curved two-pronged head across its top, a grip wrap at the bottom.
    diag(c, 2, 13, 10)
    # A crescent head over the handle top, like a classic game pickaxe: in handle coordinates (u along the handle,
    # w across it) its centre line is the arc u = BOW - CURVE * w^2, so the prongs sweep back toward the grip
    # without hooking in. Thick in the middle, tapering to sharp tips; symmetric in w so both prongs match.
    BOW, CURVE, SPAN = 0.6, 0.075, 6.6
    hu = rot(10, 5)

    def head(x, y):
        u, w = hu(x, y)
        if abs(w) > SPAN:
            return False
        half = 0.35 + 0.85 * (1 - (w / SPAN) ** 2)  # half-thickness: ~1.2 in the middle, ~0.35 at the tips
        return abs(u - (BOW - CURVE * w * w)) <= half
    c.shade(head, "PpqQ", 10, 5, 6)
    c.put(3, 12, "A")
    c.put(4, 11, "a")
    out["pickaxe"] = grab(c)

    # Axe: the same handle, a flared blade on the bow side and a small poll behind it.
    diag(c, 2, 13, 10)
    uw = rot(10, 5)

    def blade(x, y):  # flares out on the bottom-right side of the handle top
        u, w = uw(x, y)
        return 0.4 <= w <= 4.6 and -0.9 - 0.45 * w <= u <= 0.9 + 0.3 * w

    def poll(x, y):  # the blunt back of the head
        u, w = uw(x, y)
        return -2.2 <= w <= 0.4 and -0.8 <= u <= 0.8
    c.shade(blade, "PpqQ", 11, 3, 5)
    c.shade(poll, "pqQ", 8, 3, 3)
    c.put(3, 12, "A")
    c.put(4, 11, "a")
    out["axe"] = grab(c)

    # Rod: a long pole, the reel (primary) low on the pole, the line (accent) hanging from the tip to a bobber.
    diag(c, 2, 13, 12)
    c.shade(circ(5.5, 11.0, 1.45), "PpqQ", 5, 10, 2)
    c.put(5, 11, "Q")  # reel hub
    for y in range(3, 10):
        c.put(13, y, "a")
    c.put(13, 10, "A")
    c.put(13, 11, "A")
    out["rod"] = grab(c)

    # Watering can: a round-bellied body with a small rim (primary), a curved handle on the back (shaft), a long slender spout
    # rising from the belly to a rose (accent).
    c.shade(union(ell(6.8, 10.6, 4.2, 3.4), poly([(5, 6), (8.6, 6), (9, 8), (4.6, 8)])), "PpqQ", 5, 8, 6)
    for x in range(5, 9):
        c.put(x, 6, "q")  # rim
    for x, y in ((4, 5), (3, 5), (2, 6), (1, 7), (1, 8), (1, 9), (2, 10)):
        c.put(x, y, "h" if y < 8 else "k")
    for x, y in ((11, 11), (12, 10), (12, 9), (13, 8), (13, 7)):
        c.put(x, y, "a")
    for x, y in ((13, 6), (14, 6), (14, 5)):
        c.put(x, y, "A")
    out["can"] = grab(c)
    return out


def palette(b, t, a):
    pal = dict(zip("PpqQ", TIERS[b]))
    pal.update(zip("HhkK", TIERS[t]))
    pal.update(zip("Aa", TIERS[a][1:3]))
    return pal


GENERIC = (3, 1, 4)  # iron working end, wood handle, gold wrap: reads as "a tool", not as any one tier


def toml(sprites, rarity=None):
    lines = ["# Smithed tool emoji, generated by art/gen/tool_layers.py: edit that, never this file.", ""]
    for name, (g, pal) in sprites.items():
        used = {ch for row in g for ch in row if ch != "."}
        head = [f"rarity = {rarity}"] if rarity else ['kind = "free"', "outline = true"]
        lines += [f"[{name}]", *head,
                  "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items() if k in used) + " }",
                  "rows = ["] + [f'  "{"".join(r)}",' for r in g] + ["]", ""]
    return "\n".join(lines)


def export(path):
    """Write the runtime data (tier ramps + 16x16 letter grids) as JSON for cococap/art_runtime.py."""
    import json
    import os

    grids = layers()
    data = {
        "tiers": {str(n): list(ramp) for n, ramp in TIERS.items()},
        "kinds": {k: ["".join(row) for row in g] for k, g in grids.items()},
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print(path)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--export":
        export("cococap/assets/tool_layers.json")
        sys.exit(0)
    grids = layers()
    if len(sys.argv) > 2 and sys.argv[2] == "generic":
        sprites = {f"tool_{k}": (grids[k], palette(*GENERIC)) for k in grids}
        open(sys.argv[1], "w", encoding="utf-8").write(toml(sprites, rarity=1))
        print(" ".join(sprites))
        sys.exit(0)
    if len(sys.argv) > 2 and sys.argv[2] == "preview":
        combos = [(1, 1, 1), (3, 3, 1), (2, 5, 3), (5, 2, 4), (6, 4, 6), (7, 7, 7)]
        sprites = {f"preview_{k}_{b}{t}{a}": (grids[k], palette(b, t, a)) for k in grids for b, t, a in combos}
    else:
        sprites = {f"tool_{k}_t{n}": (grids[k], palette(n, n, n)) for k in grids for n in range(1, 8)}
    open(sys.argv[1], "w", encoding="utf-8").write(toml(sprites))
    print(" ".join(sprites))
