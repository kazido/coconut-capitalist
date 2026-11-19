"""The world map for the Travel (ship) page: an old parchment map with the 7 areas marked along a dotted route.

The base map is pixel art (W x H), drawn from math and noise, inked like a classic treasure map. Each area has a small
landmark icon at a fixed spot; `SITES` (area index -> pixel) is exported with the map so the bot can draw the red X on
the current area and fog over the areas not reached yet (cococap/map_runtime.py).
Run: python art/gen/world_map.py [preview.png]   (no argument = export cococap/assets/world_map.png + world_map.json)
"""
import json
import math
import os
import sys

sys.path.insert(0, ".")  # (run from the repo root: art/ is importable for the area emoji)
from PIL import Image

W, H = 240, 150
EXPORT = 2
FINE = 2  # details are drawn on a canvas twice the terrain's size


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


def _hash(x, y, s=0):
    n = (x * 374761393 + y * 668265263 + s * 2246822519) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n & 0xFFFF) / 0xFFFF


def vnoise(x, y, s=0):
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, s), _hash(ix + 1, iy, s)
    c, d = _hash(ix, iy + 1, s), _hash(ix + 1, iy + 1, s)
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(x, y, s=0):
    return sum(vnoise(x * f, y * f, s + i) / (2 ** i) for i, f in enumerate((1, 2, 4))) / 1.75


PAPER = [hexc(c) for c in ("#f1e0b4", "#e6cf98", "#d6b97c", "#bf9d62", "#9c7a45")]
INK = hexc("#4b3120")
INK_LIGHT = hexc("#8a6440")
SEA = [hexc(c) for c in ("#dcc08a", "#cba872", "#b8925a")]  # stained paper past the coast
ROUTE = hexc("#9b2a1c")

# Where each area sits (area index 0..6): a winding road from the south-west shore to the edge of the world.
SITES = [(40, 112), (84, 100), (70, 66), (118, 54), (160, 34), (186, 80), (214, 118)]
NAMES = ["SLIME HILL", "TWILIGHT DESERT", "RUST BELT", "CADREGA CITY", "AERIAL GLADES", "STAR KINGDOM", "THE VOID"]
FOG = (34, 13)  # fog ellipse radii over an unrevealed area: covers its landmark and its label


def land(x, y):
    """Land height: one big island with ragged coasts (> 0 = land)."""
    cx, cy = W * 0.5, H * 0.52
    d = math.hypot((x - cx) / (W * 0.46), (y - cy) / (H * 0.45))
    h = 1.0 - d + (fbm(x / 18, y / 18, 3) - 0.5) * 0.7
    vx, vy = SITES[6]
    pull = max(0.0, 1 - math.hypot(x - vx, y - (vy + 2)) / 30)  # the land round the Void is smooth and whole
    return h + 0.35 * pull * pull


def base_map():
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    px = im.load()
    for y in range(H):
        for x in range(W):
            # torn, burnt edge: distance to the border, roughened by noise
            edge = min(x, y, W - 1 - x, H - 1 - y) + (fbm(x / 7, y / 7, 9) - 0.5) * 6
            if edge < 1.5:
                continue
            if edge < 3:
                px[x, y] = hexc("#5a3a1e")  # the burnt rim
                continue
            age = (fbm(x / 12, y / 12, 1) - 0.5) * 1.6 + max(0.0, 6 - edge) * 0.35  # stains + darker toward the edge
            h = land(x, y)
            if h > 0:
                tone = 0.6 + age + (0.5 if h < 0.05 else 0)
                px[x, y] = PAPER[max(0, min(4, int(tone)))]
            else:
                tone = int(min(2, max(0, 0.5 + age - h * 3)))
                px[x, y] = SEA[tone]
    # coastline: ink where land meets sea, a lighter second line just offshore
    snap = im.copy().load()
    for y in range(1, H - 1):
        for x in range(1, W - 1):
            if not snap[x, y][3]:
                continue
            if land(x, y) > 0 and any(land(x + dx, y + dy) <= 0 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = INK
    up = im.resize((W * FINE, H * FINE), Image.NEAREST)  # the fine canvas: details below are drawn at twice the detail
    F = FINE
    _coast_echoes(up)
    _void_warp(up)
    _river_fine(up)
    _forests_fine(up)
    _mountains_fine(up)
    _route_fine(up)
    _projected_text(up, "THE OLD PEAKS", [(124 * F, 71 * F), (146 * F, 72 * F), (168 * F, 71 * F)])
    _projected_text(up, "SILT RIVER", [(p[0] * F, p[1] * F - 7) for p in RIVER_PATH[4:9]])
    _projected_text(up, "MIREWOOD", [(x * F, y * F) for x, y in MIREWOOD_PATH], step=11)  # down a clear lane through the wood
    _compass(up, 222 * F, 22 * F, F)
    return up


def area_overlay(i):
    """Area i's landmark and name, BAKED: drawn as ink on a copy of the base map, then kept only where the ink changed
    the paper. The bot adds this layer once the area is revealed, so it looks drawn on the map, not pasted."""
    base = base_map()
    drawn = base.copy()
    sx, sy = SITES[i]
    _landmark(drawn, i, sx * FINE, sy * FINE)
    _label(drawn, NAMES[i], sx * FINE, sy * FINE + 8)
    ov = Image.new("RGBA", drawn.size, (0, 0, 0, 0))
    bp, dp, op = base.load(), drawn.load(), ov.load()
    for y in range(drawn.height):
        for x in range(drawn.width):
            if dp[x, y] != bp[x, y]:
                op[x, y] = dp[x, y]
    return ov


def _landmark(im, i, x, y):
    """The seven landmarks as small ink drawings (about 24 x 20 fine px) in the map's own hand: lines, hatching, dots."""
    px = im.load()
    S = im.size

    def ink(a, b, k=0.9):
        _ink(px, a, b, k, S)

    def line(x0, y0, x1, y1, k=0.9):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 2) + 1
        for j in range(n + 1):
            ink(x0 + (x1 - x0) * j / n, y0 + (y1 - y0) * j / n, k)

    def arc(cx, cy, rx, ry, a0, a1, k=0.9):
        for a in range(int(a0), int(a1) + 1, 3):
            ink(cx + rx * math.cos(math.radians(a)), cy - ry * math.sin(math.radians(a)), k)

    def hatch(test, x0, y0, x1, y1, k=0.35, every=3):
        for yy in range(int(y0), int(y1) + 1):
            for xx in range(int(x0), int(x1) + 1):
                if (xx + yy) % every == 0 and test(xx, yy):
                    ink(xx, yy, k)

    if i == 0:  # Slime Hill: a round hill, its east side hatched, a little slime with two eyes on top
        arc(x, y, 14, 9, 0, 180)
        hatch(lambda a, b: ((a - x) / 14) ** 2 + ((b - y) / 9) ** 2 <= 0.85 and a > x + 4 and b < y, x, y - 9, x + 14, y)
        for gx in (-9, -5, 6):
            line(x + gx, y - 3, x + gx + 1, y - 5, 0.6)
        arc(x, y - 9, 5, 5, 0, 180)
        line(x - 5, y - 9, x + 5, y - 9)
        ink(x - 2, y - 12, 1), ink(x + 2, y - 12, 1)
        line(x - 1, y - 10.5, x + 1, y - 10.5, 0.7)
    elif i == 1:  # Twilight Desert: two dunes and a crescent moon with a star
        for j in range(25):
            ink(x - 12 + j, y - 3 * math.sin(math.pi * j / 24) - 1, 0.9)
        for j in range(17):
            ink(x - 2 + j, y - 4 * math.sin(math.pi * j / 16) - 3, 0.9)
        hatch(lambda a, b: b > y - 4 * math.sin(math.pi * max(0, min(16, a - (x - 2))) / 16) - 3 and a > x + 6 and b < y - 1,
              x + 6, y - 7, x + 14, y - 1)
        arc(x - 4, y - 14, 4, 4, 60, 300)
        arc(x - 2.5, y - 15, 3.2, 3.2, 70, 290, 0.0)
        line(x + 6, y - 16, x + 6, y - 12), line(x + 4, y - 14, x + 8, y - 14)
    elif i == 2:  # Rust Belt: a cog, eight teeth, a hub
        cx, cy = x, y - 8
        arc(cx, cy, 6, 6, 0, 360)
        arc(cx, cy, 2, 2, 0, 360)
        for a in range(0, 360, 45):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            for w in (-1.3, 1.3):
                line(cx + 6 * ca - w * sa, cy - 6 * sa - w * ca, cx + 8.5 * ca - w * sa, cy - 8.5 * sa - w * ca)
            line(cx + 8.5 * ca - 1.3 * sa, cy - 8.5 * sa - 1.3 * ca, cx + 8.5 * ca + 1.3 * sa, cy - 8.5 * sa + 1.3 * ca)
        hatch(lambda a, b: 2.5 < math.hypot(a - cx, b - cy) < 5.5 and a + b > cx + cy, cx - 6, cy - 6, cx + 6, cy + 6)
    elif i == 3:  # Cadrega City: a walled city with domes, pointed roofs and a tall spire, drawn in light ink
        k = 0.6
        line(x - 14, y, x + 14, y, k)  # the ground
        line(x - 14, y - 4, x + 14, y - 4, k)  # the city wall
        for cx in range(-14, 15, 3):
            line(x + cx, y - 4, x + cx, y - 5.5, k)  # its battlements
        for x0, w, top, roof in ((-12, 5, 10, "point"), (-6, 5, 13, "dome"), (0, 4, 19, "spire"), (5, 5, 12, "dome"), (10, 4, 9, "point")):
            line(x + x0, y - 4, x + x0, y - top, k), line(x + x0 + w, y - 4, x + x0 + w, y - top, k)
            if roof == "dome":
                arc(x + x0 + w / 2, y - top, w / 2, w / 2.2, 0, 180, k)
            elif roof == "point":
                line(x + x0, y - top, x + x0 + w / 2, y - top - 3.5, k), line(x + x0 + w / 2, y - top - 3.5, x + x0 + w, y - top, k)
            else:
                line(x + x0, y - top, x + x0 + w / 2, y - top - 7, k), line(x + x0 + w / 2, y - top - 7, x + x0 + w, y - top, k)
            for wy in range(7, top - 1, 3):
                ink(x + x0 + w / 2, y - wy, 0.45)  # lit windows: just a soft dot
        hatch(lambda a, b: True, x + 6, y - 11, x + 9, y - 5, 0.25)
    elif i == 5:  # Star Kingdom: a castle with conical-roofed towers, flags, a keep and a gate, under three stars
        k = 0.6
        line(x - 14, y, x + 14, y, k)
        for tx in (-12, 9):  # the two outer towers with pointed roofs and flags
            line(x + tx, y, x + tx, y - 11, k), line(x + tx + 3, y, x + tx + 3, y - 11, k)
            line(x + tx - 1, y - 11, x + tx + 1.5, y - 16, k), line(x + tx + 1.5, y - 16, x + tx + 4, y - 11, k)
            line(x + tx + 1.5, y - 16, x + tx + 1.5, y - 19, k), line(x + tx + 1.5, y - 19, x + tx + 4, y - 18, k)
        line(x - 9, y - 6, x + 9, y - 6, k)  # the curtain wall
        for cx in range(-9, 10, 2):
            line(x + cx, y - 6, x + cx, y - 7.5, k)
        line(x - 4, y - 6, x - 4, y - 13, k), line(x + 4, y - 6, x + 4, y - 13, k)  # the keep
        line(x - 5, y - 13, x, y - 18, k), line(x, y - 18, x + 5, y - 13, k)
        arc(x, y - 2.5, 2.2, 3, 0, 180, k), line(x - 2.2, y, x - 2.2, y - 2.5, k), line(x + 2.2, y, x + 2.2, y - 2.5, k)
        ink(x, y - 10, 0.45), ink(x - 8, y - 8, 0.45), ink(x + 8, y - 8, 0.45)
        hatch(lambda a, b: True, x + 10, y - 10, x + 12, y - 1, 0.25)
        for sx_, sy_, r_ in ((0, -24, 3), (-9, -23, 2), (9, -23, 2)):
            line(x + sx_ - r_, y + sy_, x + sx_ + r_, y + sy_), line(x + sx_, y + sy_ - r_, x + sx_, y + sy_ + r_)
            line(x + sx_ - r_ * 0.6, y + sy_ - r_ * 0.6, x + sx_ + r_ * 0.6, y + sy_ + r_ * 0.6, 0.6)
            line(x + sx_ - r_ * 0.6, y + sy_ + r_ * 0.6, x + sx_ + r_ * 0.6, y + sy_ - r_ * 0.6, 0.6)
    elif i == 4:  # Aerial Glades: a floating island, its underside hatched, a pond spilling off as a waterfall, a tree
        arc(x, y - 8, 12, 3, 0, 360)
        line(x - 12, y - 8, x, y + 2), line(x + 12, y - 8, x, y + 2)
        hatch(lambda a, b: b > y - 7 and abs(a - x) < 12 - (b - (y - 8)) * 1.2, x - 12, y - 7, x + 12, y + 2)
        arc(x - 3, y - 9, 4, 1.2, 0, 360, 0.6)
        line(x + 10, y - 7, x + 10, y + 4, 0.6), line(x + 12, y - 7, x + 12, y + 6, 0.6)
        line(x + 4, y - 9, x + 4, y - 12)
        arc(x + 2.5, y - 14, 2.2, 2.2, 60, 300), arc(x + 5.5, y - 14, 2.2, 2.2, -120, 120), arc(x + 4, y - 16, 2.4, 2.0, 0, 180)
    elif i == 6:  # The Void: a black hole, a solid ink core inside a tilted, hatched ring
        cx, cy = x, y - 8
        for yy in range(int(cy - 4), int(cy + 5)):
            for xx in range(int(cx - 4), int(cx + 5)):
                if math.hypot(xx - cx, yy - cy) <= 4:
                    ink(xx, yy, 1.0)
        arc(cx, cy, 12, 3.5, 0, 360)
        arc(cx, cy, 7, 2, 180, 360, 0.6)
        hatch(lambda a, b: ((a - cx) / 12) ** 2 + ((b - cy) / 3.5) ** 2 <= 1 and math.hypot(a - cx, b - cy) > 4.5,
              cx - 12, cy - 4, cx + 12, cy + 4, 0.4, 2)


def _route(im):
    """A dotted red route through the sites, gently curved."""
    px = im.load()
    for (x0, y0), (x1, y1) in zip(SITES, SITES[1:]):
        mx, my = (x0 + x1) / 2 + (y1 - y0) * 0.18, (y0 + y1) / 2 - (x1 - x0) * 0.18
        n = int(math.hypot(x1 - x0, y1 - y0) * 1.5)
        for i in range(n):
            t = i / n
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1
            if 0.12 < t < 0.88 and (i // 2) % 3 == 0:
                px[int(x), int(y)] = ROUTE


def _route_fine(up):
    """The route as even red dashes: 3 x 2 fine-pixel dashes every 9 px of arc length along gentle curves, leaving a gap
    round each landmark."""
    F = FINE
    for (x0, y0), (x1, y1) in zip(SITES, SITES[1:]):
        x0, y0, x1, y1 = x0 * F, y0 * F, x1 * F, y1 * F
        mx, my = (x0 + x1) / 2 + (y1 - y0) * 0.18, (y0 + y1) / 2 - (x1 - x0) * 0.18
        samples = []
        for i in range(401):
            t = i / 400
            samples.append(((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1))
        dist, nxt = 0.0, 0.0
        for (ax, ay), (bx, by) in zip(samples, samples[1:]):
            dist += math.hypot(bx - ax, by - ay)
            if dist >= nxt:
                nxt += 10
                if math.hypot(bx - x0, by - y0) > 20 and math.hypot(bx - x1, by - y1) > 20:
                    cx, cy = int(round(bx)), int(round(by))
                    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):  # the same small round dot every time
                        _put(up, cx + dx, cy + dy, ROUTE)

# ---- terrain features on the fine canvas ---------------------------------------------------------------------------
MTN_LIT, MTN_SHADE, MTN_LINE, MTN_SNOW = hexc("#e2c993"), hexc("#ccae78"), hexc("#a5845a"), hexc("#f3e6c4")
TREE = [hexc(c) for c in ("#a8b27a", "#8a9862", "#6e7c4c", "#55613a")]  # canopy light -> dark, muted to sit in the paper


def _layer_outline(layer, colour):
    """A 1px outline round everything opaque on a layer (4-neighbour), in place."""
    src = layer.copy()
    w, h = layer.size
    sp = src.load()
    lp = layer.load()
    for y in range(h):
        for x in range(w):
            if not sp[x, y][3] and any(0 <= x + dx < w and 0 <= y + dy < h and sp[x + dx, y + dy][3]
                                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                lp[x, y] = colour


def _void_warp(up):
    """Where the map ends: the paper round the Void is pulled into a black hole: spiral arms of ink winding inward,
    darker toward the middle, fading out into the plain paper."""
    F = FINE
    vx, vy = SITES[6][0] * F, (SITES[6][1] - 4) * F
    px = up.load()
    R = 40.0
    for y in range(int(vy - R), int(vy + R) + 1):
        for x in range(int(vx - R), int(vx + R) + 1):
            if not (0 <= x < up.width and 0 <= y < up.height) or not px[x, y][3]:
                continue
            r = math.hypot(x - vx, (y - vy) * 1.35)  # a little squashed, like a disc seen at an angle
            if r > R:
                continue
            a = math.atan2((y - vy) * 1.35, x - vx)
            arm = math.sin(2 * a + r * 0.38)  # two arms spiralling in
            fade = (1 - r / R) ** 0.9
            k = 0.0
            if arm > 0.6:
                k = 0.7 * fade  # the inked edge of each arm
            elif arm > 0.1:
                k = 0.22 * fade  # its shaded body
            k += 0.5 * max(0.0, 1 - r / 7) ** 2  # the dark heart
            if k > 0.02:
                _ink(px, x, y, min(0.95, k), up.size)


def _coast_echoes(up):
    """Two wavering ink lines echoing the coast out at sea, the way a hand-inked map draws its shoreline."""
    F = FINE
    px = up.load()
    for y in range(up.height):
        for x in range(up.width):
            if px[x, y][3] == 0 or px[x, y] not in SEA:
                continue
            h = land(x / F, y / F) + 0.006 * math.sin(x * 0.4 + y * 0.3)  # a slight waver
            if -0.045 < h < -0.036 or -0.10 < h < -0.091:
                px[x, y] = INK_LIGHT


def _ink(px, x, y, strength, size):
    """Darken the paper at (x, y) like ink soaking in: strength 1 = full line, 0.3 = faint hatch."""
    w, h = size
    x, y = int(round(x)), int(round(y))
    if 0 <= x < w and 0 <= y < h and px[x, y][3]:
        r, g, b, a = px[x, y]
        k = 1 - 0.62 * strength  # ink never goes fully black: it is brown ink on old paper
        px[x, y] = (int(r * k * 0.97), int(g * k * 0.93), int(b * k * 0.88), a)


def _peak_line(up, clean, x, y, h, lean):
    """One inked mountain baked into the paper: the paper behind it is restored from `clean` (so a nearer peak hides the
    lines of a farther one without a flat fill), then its two slopes and a hatched east face are inked."""
    px, cp = up.load(), clean.load()
    tip = x + lean
    half = h * 0.8
    rows = []
    for yy in range(int(y - h), int(y) + 1):
        k = (yy - (y - h)) / h
        left, right = tip - (tip - (x - half)) * k, tip + ((x + half) - tip) * k
        rows.append((yy, left, right))
        for xx in range(int(left) + 1, int(right)):
            if 0 <= xx < up.width and 0 <= yy < up.height:
                px[xx, yy] = cp[xx, yy]
    for yy, left, right in rows:
        _ink(px, left, yy, 0.85, up.size)
        _ink(px, right, yy, 0.85, up.size)
        for xx in range(int(tip) + 1, int(right)):
            if (xx + yy) % 3 == 0 and (xx - tip) > (right - tip) * 0.2:
                _ink(px, xx, yy, 0.35, up.size)  # hatching on the shaded east face


def _mountains_fine(up):
    """Two ranges of inked peaks in loose rows, stacked back to front, baked into the paper."""
    F = FINE
    clean = up.copy()
    peaks = []
    for x0, x1, base, rows in ((14, 72, 46, 3), (128, 180, 66, 3)):
        for r in range(rows):
            n = 5 - r
            for i in range(n):
                x = (x0 + (x1 - x0) * (i + 0.5 + (0.5 if r % 2 else 0)) / (n + 0.5) + (_hash(i, r, x0) - 0.5) * 3) * F
                y = (base - r * 6 + (_hash(r, i, x0) - 0.5) * 2) * F
                h = (8 + _hash(i, r, 9) * 3 - r * 0.8) * F
                hw = h * 0.8 / F
                if min(land(x / F - hw, y / F), land(x / F + hw, y / F), land(x / F, y / F - h / F)) > 0.06 and _clear_of_sites(x / F, y / F - 4, 11):
                    peaks.append((y, x, h, (_hash(i, r, 7) - 0.5) * 4))
    for y, x, h, lean in sorted(peaks):
        _peak_line(up, clean, x, y, h, lean)


def _forests_fine(up):
    """Each wood is ONE drawing: a single scalloped canopy outline round the whole wood, rows of crown arcs inside it
    (each row tucked under the one behind), a slightly darker canopy tone, and a few trunks along the bottom edge."""
    F = FINE
    px = up.load()
    woods = [(124, 103, 21, 12), (26, 88, 9, 6), (156, 120, 8, 5), (200, 52, 9, 6)]
    r = 2.8
    for wx, wy, rx, ry in woods:
        crowns = []
        for gy in range(-ry * F, ry * F + 1, 4):
            for gx in range(-rx * F, rx * F + 1, 4):
                x = wx * F + gx + (2 if (gy // 4) % 2 else 0) + (_hash(gx, gy, wx) - 0.5) * 1.5
                y = wy * F + gy + (_hash(gy, gx, wy) - 0.5) * 1.5
                edge = ((x / F - wx) / rx) ** 2 + ((y / F - wy) / ry) ** 2 + (_hash(int(x), int(y), 2) - 0.5) * 0.3
                if edge > 1 or land(x / F, y / F) < 0.06 or not _clear_of_sites(x / F, y / F, 11):
                    continue
                if _near_path(x / F, y / F, MIREWOOD_PATH, 6.5):
                    continue
                crowns.append((x, y))
        if not crowns:
            continue
        inside = set()
        for cx, cy in crowns:
            for yy in range(int(cy - r) - 1, int(cy + r) + 2):
                for xx in range(int(cx - r) - 1, int(cx + r) + 2):
                    if math.hypot(xx - cx, yy - cy) <= r:
                        inside.add((xx, yy))
        for xx, yy in inside:
            _ink(px, xx, yy, 0.1, up.size)  # the canopy's tone
            if (xx * 3 + yy) % 7 == 0 and (xx, yy - 2) in inside:
                _ink(px, xx, yy, 0.4, up.size)  # little foliage ticks
                _ink(px, xx, yy + 1, 0.3, up.size)
        for xx, yy in inside:  # one outline round the whole wood
            if any((xx + dx, yy + dy) not in inside for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                _ink(px, xx, yy, 0.75, up.size)
        bottom = {}
        for xx, yy in inside:
            bottom[xx] = max(bottom.get(xx, -1), yy)
        for xx in sorted(bottom)[1:-1:3]:  # a row of short trunks under the canopy
            for k in (1, 2):
                _ink(px, xx, bottom[xx] + k, 0.6, up.size)


def _river_fine(up):
    """The Silt River baked into the paper: softly inked banks and a faint cool wash between them, widening toward the
    sea, so the stains and grain of the paper run through it."""
    F = FINE
    pts = [(x * F, y * F) for x, y in RIVER_PATH]
    total = sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(pts, pts[1:]))
    run = 0.0
    px = up.load()
    water, bank = set(), {}
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        n = int(L * 2)
        for i in range(n):
            t = i / n
            x = x0 + (x1 - x0) * t + math.sin((y0 + (y1 - y0) * t) * 0.17) * 3
            y = y0 + (y1 - y0) * t
            h_land = land(x / F, y / F)
            if h_land <= -0.03:
                break  # out at sea: the mouth has already faded away
            along = (run + L * t) / total
            half = (0.5 + 7.5 * min(1.0, along / 0.12) * (0.4 + 0.6 * along)) / 2  # a spring that swells into a river
            if h_land < 0.05:
                half += (0.05 - h_land) * 60  # the mouth opens out toward the sea
            nx, ny = -(y1 - y0) / L, (x1 - x0) / L
            for k in range(-int(half * 2), int(half * 2) + 1):
                o = k / 2
                q = (int(round(x + nx * o)), int(round(y + ny * o)))
                if _clear_of_sites(q[0] / F, q[1] / F, 9):
                    fade = max(0.0, min(1.0, h_land / 0.05)) if h_land < 0.05 else 1.0
                    if abs(o) >= half - 0.5:
                        bank[q] = max(bank.get(q, 0.0), 0.7 * fade)
                    else:
                        water.add(q)
        run += L
    for x, y in water - set(bank):
        if 0 <= x < up.width and 0 <= y < up.height and px[x, y][3]:
            r_, g, b, a = px[x, y]
            px[x, y] = (int(r_ * 0.86), int(g * 0.93), int(b * 1.0), a)  # a faint cool wash, the paper still showing
    for (x, y), k in bank.items():
        if k > 0.05:
            _ink(px, x, y, k, up.size)


def _put(im, x, y, c):
    if 0 <= x < im.width and 0 <= y < im.height:
        im.putpixel((int(x), int(y)), c)


def _sprite(im, cx, cy, rows, pal):
    """Stamp a small hand-placed sprite centred on (cx, cy)."""
    h, w = len(rows), len(rows[0])
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch in pal:
                _put(im, cx - w // 2 + i, cy - h + 2 + j, pal[ch])


O = INK
ICONS = [
    # 0 Slime Hill: a green hill with a happy slime on top
    lambda im, x, y: _sprite(im, x, y, [
        "....ooo....",
        "...oGgGo...",
        "...ogwgo...",
        "..oggggo...",
        ".oHHHHHHHo.",
        "oHhHHHHhHHo",
        "ohhhhhhhhho",
        "ooooooooooo"], {"o": O, "G": hexc("#9be36a"), "g": hexc("#5fb04a"), "w": hexc("#1c3a14"),
                         "H": hexc("#8cbf5e"), "h": hexc("#5f8f3c")}),
    # 1 Twilight Desert: dunes under a dusky sun
    lambda im, x, y: _sprite(im, x, y, [
        "....ooo....",
        "...oSSSo...",
        "....ooo....",
        "...ooo.....",
        "..oDDDooo..",
        ".oDDdDDDDo.",
        "oddDDDdddDo",
        "ooooooooooo"], {"o": O, "S": hexc("#ff9f6a"), "D": hexc("#e8b878"), "d": hexc("#b98a50")}),
    # 2 Rust Belt: a rusted cog
    lambda im, x, y: _sprite(im, x, y, [
        "...o.o.o...",
        "..oRoRoRo..",
        ".oRRRRRRRo.",
        "oRRroooRRRo",
        ".oRro.oRRo.",
        "oRRroooRRRo",
        ".oRRRRRRRo.",
        "..oRoRoRo..",
        "...o.o.o..."], {"o": O, "R": hexc("#c06a34"), "r": hexc("#7e3e1c")}),
    # 3 Cadrega City: walled towers
    lambda im, x, y: _sprite(im, x, y, [
        "..o.....o..",
        ".oTo...oTo.",
        ".oTo.o.oTo.",
        ".oTooToTTo.",
        "oWTTTTTTTWo",
        "oWwTTwTTwWo",
        "oWWWWWWWWWo",
        "ooooooooooo"], {"o": O, "T": hexc("#c9b9a0"), "w": hexc("#3a2a1a"), "W": hexc("#9a8a72")}),
    # 4 Aerial Glades: a floating island with a tree and a cloud
    lambda im, x, y: _sprite(im, x, y, [
        "....ooo....",
        "...oLLLo...",
        "...oLlLo...",
        "....oto....",
        ".oGGGtGGGo.",
        "..oEEEEEo..",
        "...oEEEo...",
        "....oEo....",
        "ooo..o..ooo"], {"o": O, "L": hexc("#7fd07a"), "l": hexc("#4e9a48"), "t": hexc("#7a5030"),
                         "G": hexc("#9be36a"), "E": hexc("#a88a60")}),
    # 5 Star Kingdom: a castle with a star above
    lambda im, x, y: _sprite(im, x, y, [
        ".....o.....",
        "....oYo....",
        "...oYYYo...",
        "o.o.oYo.o.o",
        "oCoCoCoCoCo",
        "oCCCCCCCCCo",
        "oCCcoooCCCo",
        "oCCco.oCCCo",
        "ooooooooooo"], {"o": O, "Y": hexc("#ffe066"), "C": hexc("#c8c0e8"), "c": hexc("#8a80b8")}),
    # 6 The Void: a dark swirl where the map ends
    lambda im, x, y: _sprite(im, x, y, [
        "...ooooo...",
        "..oVVVVVo..",
        ".oVvoooVVo.",
        "oVvo.VVoVVo",
        "oVo.oKoVoVo",
        "oVVoVVo.vVo",
        ".oVVoooovo.",
        "..oVVVVVo..",
        "...ooooo..."], {"o": O, "V": hexc("#6a3fa0"), "v": hexc("#3a1f66"), "K": hexc("#120a20")}),
]


def _fill_poly(im, pts, c):
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    for y in range(int(min(ys)), int(max(ys)) + 2):
        for x in range(int(min(xs)), int(max(xs)) + 2):
            inside, j = False, len(pts) - 1
            for i in range(len(pts)):
                (xi, yi), (xj, yj) = pts[i], pts[j]
                if (yi > y + 0.5) != (yj > y + 0.5) and x + 0.5 < (xj - xi) * (y + 0.5 - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                _put(im, x, y, c)


def _compass(im, cx, cy, k=1):
    """A compass rose: a thin ring, four long and four short points, each point split into a lit and a shaded half
    (so it reads as a 3D star), the north tip in red, an ink outline round it all. Symmetric about both axes."""
    for a in range(0, 360, 2):  # the ring
        _put(im, cx + 8.5 * k * math.cos(math.radians(a)), cy + 8.5 * k * math.sin(math.radians(a)), INK_LIGHT)
    rose = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for ang, length, half in ((-90, 11, 2.6), (0, 11, 2.6), (90, 11, 2.6), (180, 11, 2.6),
                              (-45, 6.5, 1.8), (45, 6.5, 1.8), (135, 6.5, 1.8), (225, 6.5, 1.8)):
        a = math.radians(ang)
        length, half = length * k, half * k
        tip = (cx + 0.5 + length * math.cos(a), cy + 0.5 + length * math.sin(a))
        left = (cx + 0.5 + half * math.cos(a - math.pi / 2), cy + 0.5 + half * math.sin(a - math.pi / 2))
        right = (cx + 0.5 + half * math.cos(a + math.pi / 2), cy + 0.5 + half * math.sin(a + math.pi / 2))
        centre = (cx + 0.5, cy + 0.5)
        dark, light = (INK_LIGHT, PAPER[0])
        north = ang == -90
        _fill_poly(rose, [centre, left, tip], ROUTE if north else light)
        _fill_poly(rose, [centre, tip, right], hexc("#6e1a10") if north else dark)
    src = rose.copy()
    RW, RH = rose.size
    for y in range(max(0, int(cy - 14 * k)), min(RH, int(cy + 14 * k))):  # ink outline round the star
        for x in range(max(0, int(cx - 14 * k)), min(RW, int(cx + 14 * k))):
            if not src.getpixel((x, y))[3] and any(0 <= x + dx < RW and 0 <= y + dy < RH and src.getpixel((x + dx, y + dy))[3]
                                                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                rose.putpixel((x, y), INK)
    im.alpha_composite(rose)
    _put(im, cx, cy, INK)


# ---- extras: forests, mountains, a river, labels ---------------------------------------------------------------------
FOREST = [hexc(c) for c in ("#7f9a52", "#5c7a3a", "#3c5428")]
RIVER = [hexc(c) for c in ("#6f9fb8", "#4a7a96")]


MIREWOOD_PATH = [(100, 95), (122, 101), (146, 110)]  # the wood's name runs down through it (coarse map pixels)


def _near_path(x, y, path, r):
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        vx, vy = x1 - x0, y1 - y0
        k = max(0.0, min(1.0, ((x - x0) * vx + (y - y0) * vy) / (vx * vx + vy * vy)))
        if math.hypot(x - (x0 + vx * k), y - (y0 + vy * k)) < r:
            return True
    return False


def _clear_of_sites(x, y, r=13):
    return all(math.hypot(x - sx, y - (sy + 3)) > r for sx, sy in SITES)


def _tree(im, x, y):
    """A tiny inked tree: a round crown on a trunk."""
    _sprite(im, x, y, [".ooo.", "oFFfo", "oFfff", ".ofo.", "..o.."], {"o": INK, "F": FOREST[0], "f": FOREST[1]})


def _forests(im):
    """Clusters of trees in a few woods (fixed by a seeded hash, so the map never changes)."""
    for wx, wy, n in ((124, 102, 26), (24, 86, 9), (150, 118, 8), (200, 52, 8)):
        for i in range(n):
            a, r = _hash(i, wx, 7) * 6.283, 3 + _hash(i, wy, 8) * 11
            x, y = int(wx + math.cos(a) * r * 1.4), int(wy + math.sin(a) * r * 0.7)
            if land(x, y) > 0.08 and _clear_of_sites(x, y) and not _near_path(x, y + 2, MIREWOOD_PATH, 5):
                _tree(im, x, y)


def _peak(im, x, y, h):
    """An inked mountain: lit left slope, hatched right slope, a little snow on top."""
    for j in range(h):
        half = j * 0.9 + 0.5
        for i in range(int(-half), int(half) + 1):
            c = PAPER[1] if i < 0 else (INK_LIGHT if (i + j) % 2 == 0 else PAPER[3])  # lit west slope, hatched east slope
            if j < 2:
                c = hexc("#ffffff") if i <= 0 else PAPER[1]
            _put(im, x + i, y - h + j, c)
        _put(im, x - int(half) - 1, y - h + j, INK)
        _put(im, x + int(half) + 1, y - h + j, INK)
    _put(im, x, y - h - 1, INK)


def _mountains(im):
    """Two ranges: the Old Peaks in the north-west, and a ridge between Cadrega City and the Star Kingdom."""
    ranges = [(16, 66, 46, 6), (130, 176, 66, 5)]
    for x0, x1, base, count in ranges:
        for i in range(count):
            x = int(x0 + (x1 - x0) * (i + 0.5) / count + (_hash(i, x0, 3) - 0.5) * 4)
            y = int(base + (_hash(i, x0, 4) - 0.5) * 8)
            h = 7 + int(_hash(i, x0, 5) * 5)
            if land(x, y) > 0.08 and _clear_of_sites(x, y - 4, 11):
                _peak(im, x, y, h)


RIVER_PATH = [(34, 48), (48, 70), (46, 84), (56, 96), (62, 110), (80, 122), (104, 125), (126, 129), (142, 138), (150, 150)]


def _river(im):
    """The Silt River: from the Old Peaks, winding south-east past the woods to the southern sea, widening as it goes."""
    pts = RIVER_PATH
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = int(math.hypot(x1 - x0, y1 - y0) * 3)
        for i in range(n):
            t = i / n
            x = x0 + (x1 - x0) * t + math.sin((y0 + (y1 - y0) * t) * 0.35) * 1.5
            y = y0 + (y1 - y0) * t
            if land(x, y) <= 0:
                return
            wide = 1 if y > 95 else 0
            for dx in range(-wide, wide + 1):
                if _clear_of_sites(x + dx, y, 9):
                    _put(im, x + dx, y, RIVER[0] if dx <= 0 else RIVER[1])


# A 3x5 pixel font for the labels (uppercase only).
FONT = {
    "A": ["010", "101", "111", "101", "101"], "B": ["110", "101", "110", "101", "110"], "C": ["011", "100", "100", "100", "011"],
    "D": ["110", "101", "101", "101", "110"], "E": ["111", "100", "110", "100", "111"], "G": ["011", "100", "101", "101", "011"],
    "H": ["101", "101", "111", "101", "101"], "I": ["111", "010", "010", "010", "111"], "K": ["101", "101", "110", "101", "101"],
    "L": ["100", "100", "100", "100", "111"], "M": ["101", "111", "111", "101", "101"], "N": ["110", "101", "101", "101", "101"],
    "O": ["010", "101", "101", "101", "010"], "P": ["110", "101", "110", "100", "100"], "R": ["110", "101", "110", "101", "101"],
    "S": ["011", "100", "010", "001", "110"], "T": ["111", "010", "010", "010", "010"], "U": ["101", "101", "101", "101", "111"],
    "V": ["101", "101", "101", "101", "010"], "W": ["101", "101", "111", "111", "101"], "Y": ["101", "101", "010", "010", "010"],
    " ": ["000", "000", "000", "000", "000"],
}


def _label(im, text, cx, top):
    """Small inked capitals centred on cx, with a 1px parchment halo so they read over terrain."""
    width = len(text) * 4 - 1
    x0 = int(cx - width / 2)
    ink = []
    for k, ch in enumerate(text):
        for j, row in enumerate(FONT.get(ch, FONT[" "])):
            for i, bit in enumerate(row):
                if bit == "1":
                    ink.append((x0 + k * 4 + i, top + j))
    inked = set(ink)
    for x, y in ink:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (x + dx, y + dy) not in inked:
                    _put(im, x + dx, y + dy, PAPER[0])
    for x, y in ink:
        _put(im, x, y, INK)


_AREA_SPRITES = None


def _area_icon(im, i, x, y):
    """Stamp area i's emoji (art/sprites/areas.toml, outlined like the built emoji) with its base just below the site."""
    global _AREA_SPRITES
    if _AREA_SPRITES is None:
        from pathlib import Path as _P

        from art.build import add_outline
        from art.sprite import load_hand
        sprites = {sp.name: sp for sp in load_hand(_P("art/sprites/areas.toml"))}
        order = ["area_slime_hill", "area_twilight_desert", "area_rust_belt", "area_cadrega_city", "area_aerial_glades",
                 "area_star_kingdom", "area_the_void"]
        _AREA_SPRITES = [add_outline(sprites[n].frames[0]) for n in order]
    icon = _AREA_SPRITES[i]
    im.alpha_composite(icon, (int(x - 8), int(y - 13)))


def _faded_text(im, text, path):
    """A feature name printed faintly INTO the map (the paper under each letter darkened a little, no halo), with its
    letters laid along `path` so the name follows a river or arches over peaks."""
    pts, total = [], 0.0
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        pts.append(((x0, y0), (x1, y1), math.hypot(x1 - x0, y1 - y0)))
        total += pts[-1][2]
    step = total / max(1, len(text))
    px = im.load()
    for k, ch in enumerate(text):
        d = (k + 0.5) * step  # the letter's centre, measured along the path
        for (x0, y0), (x1, y1), L in pts:
            if d <= L:
                cx, cy = x0 + (x1 - x0) * d / L, y0 + (y1 - y0) * d / L
                break
            d -= L
        for j, row in enumerate(FONT.get(ch, FONT[" "])):
            for i, bit in enumerate(row):
                x, y = int(round(cx - 1 + i)), int(round(cy - 2 + j))
                if bit == "1" and 0 <= x < W and 0 <= y < H and px[x, y][3]:
                    r, g, b, a = px[x, y]
                    px[x, y] = (int(r * 0.82), int(g * 0.80), int(b * 0.78), a)


# Map landmarks: small (about 13 x 12 fine px) ink-and-wash drawings in muted map colours, outlined in ink.
WASH = {"h": "#a9b67c", "H": "#7f8f58", "s": "#a3d0bf", "S": "#6fa494", "e": "#2c2a20", "y": "#e4c890", "Y": "#c49b5e",
        "m": "#f6efd2", "r": "#bb7c48", "R": "#8c5734", "k": "#3e2c1e", "a": "#cfae80", "c": "#aab4b4", "d": "#c38c78",
        "w": "#f0d27a", "g": "#a9b67c", "G": "#7f8f58", "E": "#a9875e", "D": "#7c6040", "l": "#8db8c8", "q": "#e2dae4",
        "Q": "#aaa2bc", "t": "#f0cc58", "v": "#221826", "V": "#9a7aaa", "u": "#d4c0dc"}


def _icon_canvas():
    return [["." for _ in range(13)] for _ in range(12)]


def _paint(g, test, ch):
    for y in range(12):
        for x in range(13):
            if test(x + 0.5, y + 0.5):
                g[y][x] = ch


def _icons():
    icons = []
    e = lambda cx, cy, rx, ry: (lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1)  # noqa: E731
    # 0 Slime Hill: a round hill with a slime sitting on top (symmetric)
    g = _icon_canvas()
    _paint(g, lambda x, y: e(6.5, 12.5, 6.2, 5.0)(x, y) and y <= 11.5, "h")
    _paint(g, lambda x, y: e(6.5, 12.5, 6.2, 5.0)(x, y) and y <= 11.5 and x > 8.5, "H")
    _paint(g, lambda x, y: e(6.5, 6.6, 3.2, 2.8)(x, y) and y <= 8, "s")
    _paint(g, lambda x, y: e(6.5, 6.6, 3.2, 2.8)(x, y) and y <= 8 and (x - 6.5) + (y - 6.6) > 1.6, "S")
    g[6][5] = g[6][7] = "e"
    icons.append(g)
    # 1 Twilight Desert: two dunes under a crescent moon and a star
    g = _icon_canvas()
    _paint(g, lambda x, y: 4 <= x <= 13 and y >= 7.5 + 2.2 * math.cos((x - 9) / 2.4) and y <= 11.5, "Y")
    _paint(g, lambda x, y: x <= 9 and y >= 8.6 + 1.8 * math.cos((x - 3.5) / 2.0) and y <= 11.5, "y")
    _paint(g, lambda x, y: e(9.5, 3.0, 2.3, 2.3)(x, y) and not e(10.6, 2.2, 1.9, 1.9)(x, y), "m")
    g[1][3] = g[2][2] = g[2][4] = g[3][3] = "m"
    icons.append(g)
    # 2 Rust Belt: a cog, eight teeth placed by hand, a dark hub (symmetric)
    g = _icon_canvas()
    ring = lambda x, y: 1.4 < math.hypot(x - 6.5, y - 6.0) <= 3.6  # noqa: E731
    teeth = [(6, 1, 6, 1), (6, 10, 6, 10), (1, 5, 1, 6), (11, 5, 11, 6), (3, 2, 3, 2), (9, 2, 9, 2), (3, 9, 3, 9), (9, 9, 9, 9)]
    tooth = lambda x, y: any(a <= int(x) <= c_ and b <= int(y) <= d for a, b, c_, d in teeth)  # noqa: E731
    _paint(g, lambda x, y: ring(x, y) or tooth(x, y), "r")
    _paint(g, lambda x, y: (ring(x, y) or tooth(x, y)) and (x - 6.5) + (y - 6.0) > 1.5, "R")
    _paint(g, lambda x, y: math.hypot(x - 6.5, y - 6.0) <= 1.4, "k")
    icons.append(g)
    # 3 Cadrega City: a skyline of buildings in different colours, lit windows
    g = _icon_canvas()
    for x0, x1, top, col in ((0, 2, 7, "a"), (3, 4, 4, "c"), (5, 7, 1, "d"), (8, 9, 5, "a"), (10, 12, 3, "c")):
        _paint(g, lambda x, y, x0=x0, x1=x1, top=top: x0 <= int(x) <= x1 and top <= int(y) <= 11, col)
    for x, y in ((1, 9), (4, 6), (6, 3), (6, 6), (9, 7), (11, 5), (11, 8)):
        g[y][x] = "w"
    icons.append(g)
    # 4 Aerial Glades: a floating island with a pond spilling over the edge as a waterfall
    g = _icon_canvas()
    _paint(g, lambda x, y: e(6.5, 4.5, 5.6, 1.9)(x, y) and y <= 5.2, "g")
    _paint(g, lambda x, y: y > 5 and abs(x - 6.5) <= 5.4 - (y - 5) * 1.25 and y <= 9.5, "E")
    _paint(g, lambda x, y: y > 5 and abs(x - 6.5) <= 5.4 - (y - 5) * 1.25 and y <= 9.5 and x > 7.5, "D")
    _paint(g, lambda x, y: e(5.5, 4.0, 2.2, 0.9)(x, y), "l")  # the pond
    for y in range(4, 12):
        g[y][11] = "l"  # the waterfall off the east edge
    icons.append(g)
    # 5 Star Kingdom: a symmetric castle (two towers and a keep, battlements, a gate) under three stars
    g = _icon_canvas()
    for x0, x1, top in ((1, 3, 5), (9, 11, 5), (4, 8, 4)):
        _paint(g, lambda x, y, x0=x0, x1=x1, top=top: x0 <= int(x) <= x1 and top <= int(y) <= 11, "q")
    for x in (1, 3, 9, 11, 4, 6, 8):
        g[4 if x in (1, 3, 9, 11) else 3][x] = "q"
    _paint(g, lambda x, y: 5 <= int(x) <= 7 and 9 <= int(y) <= 11, "e")
    _paint(g, lambda x, y: x > 9.0 and 5 <= int(y) <= 11, "Q")
    g[0][6] = g[1][5] = g[1][7] = g[1][6] = "t"
    g[1][2] = g[1][10] = "t"
    icons.append(g)
    # 6 The Void: a black hole, a dark core inside a tilted glowing ring (symmetric)
    g = _icon_canvas()
    disk = lambda x, y: e(6.5, 6.0, 6.0, 2.0)(x, y) and not e(6.5, 6.0, 3.2, 1.0)(x, y)  # noqa: E731
    _paint(g, lambda x, y: disk(x, y) and y < 6, "V")  # the back half of the ring
    _paint(g, e(6.5, 6.0, 2.8, 2.8), "v")  # the core
    _paint(g, lambda x, y: disk(x, y) and y >= 6, "V")  # the front half, over the core
    _paint(g, lambda x, y: disk(x, y) and y >= 6 and abs(x - 6.5) < 2.5, "u")
    icons.append(g)
    return icons


_MAP_ICONS = None


def _map_icon(im, i, x, y):
    """Stamp landmark i (with an ink outline) centred above the site."""
    global _MAP_ICONS
    if _MAP_ICONS is None:
        _MAP_ICONS = []
        for g in _icons():
            ic = Image.new("RGBA", (15, 14), (0, 0, 0, 0))
            for yy, row in enumerate(g):
                for xx, ch in enumerate(row):
                    if ch != ".":
                        ic.putpixel((xx + 1, yy + 1), hexc(WASH[ch]))
            src = ic.copy()
            for yy in range(14):
                for xx in range(15):
                    if not src.getpixel((xx, yy))[3] and any(0 <= xx + dx < 15 and 0 <= yy + dy < 14 and src.getpixel((xx + dx, yy + dy))[3]
                                                             for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        ic.putpixel((xx, yy), INK)
            _MAP_ICONS.append(ic)
    im.alpha_composite(_MAP_ICONS[i], (int(x - 7), int(y - 12)))


def _projected_text(im, text, path, step=8.0):
    """A feature name printed INTO the map: each letter is turned to the direction of `path` at its spot (so the name
    bends along a river or arches over peaks) and only darkens the paper under it a little, like old faded print."""
    from PIL import ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("consolab.ttf", 11)  # monospaced: every letter takes the same room
    except OSError:
        font = ImageFont.load_default()
    segs, total = [], 0.0
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        segs.append(((x0, y0), (x1, y1), L))
        total += L
    px = im.load()
    start = max(0.0, (total - step * len(text)) / 2)
    for k, ch in enumerate(text):
        if ch == " ":
            continue
        d = start + (k + 0.5) * step
        for (x0, y0), (x1, y1), L in segs:
            if d <= L or (x1, y1) == segs[-1][1]:
                t = d / L  # (past the end of the last segment: keep going the same way)
                cx, cy, ang = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, math.degrees(math.atan2(y1 - y0, x1 - x0))
                break
            d -= L
        glyph = Image.new("L", (16, 16), 0)  # each letter centred in its own cell, then turned
        dr = ImageDraw.Draw(glyph)
        dr.fontmode = "1"  # crisp pixels, no anti-aliasing
        dr.text((8, 8), ch, font=font, fill=255, anchor="mm")
        glyph = glyph.rotate(-ang, resample=Image.NEAREST)
        for gy in range(16):
            for gx in range(16):
                if glyph.getpixel((gx, gy)) > 127:
                    x, y = int(cx - 8 + gx), int(cy - 8 + gy)
                    if 0 <= x < im.width and 0 <= y < im.height and px[x, y][3]:
                        r, g_, b, a = px[x, y]
                        px[x, y] = (int(r * 0.8), int(g_ * 0.78), int(b * 0.76), a)


def export():
    os.makedirs("cococap/assets", exist_ok=True)
    base_map().save("cococap/assets/world_map.png")
    for i in range(len(SITES)):
        area_overlay(i).save(f"cococap/assets/world_map_area_{i}.png")
    with open("cococap/assets/world_map.json", "w", encoding="utf-8") as f:
        json.dump({"size": [W * FINE, H * FINE], "unit": FINE, "sites": [[x * FINE, y * FINE] for x, y in SITES],
                   "fog": [FOG[0] * FINE, FOG[1] * FINE]}, f)
        f.write("\n")
    print("cococap/assets/world_map.png")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        im = base_map()
        for i in range(len(SITES)):
            im.alpha_composite(area_overlay(i))
        im.resize((im.width * EXPORT, im.height * EXPORT), Image.NEAREST).save(sys.argv[1])
    else:
        export()
