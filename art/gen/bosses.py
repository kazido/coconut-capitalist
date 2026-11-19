"""Fishing boss portraits: 96x96 pixel art (drawn on a 48x48 logical grid, x2 fine) with an idle animation, shown big as a thumbnail when a boss bites.

Each boss is a function draw_<id>(t) -> 48x48 RGBA for loop position t in [0, 1). Shapes come from math (ellipses,
curves), shaded with 4-5 tone ramps lit from the top-left, then outlined in a dark tone. Exported as an animated
.webp at x6 (288px) into cococap/assets/bosses/<id>.webp, so the bot can attach it with no Discord emoji slot.
Run: python art/gen/bosses.py [preview.png]
"""
import math
import os
import sys

from PIL import Image

N = 48  # logical grid every boss is drawn on
K = 2   # fine pixels per logical pixel: the picture is 96x96
FRAMES, MS = 12, 110
OUTLINE = (24, 16, 28, 255)


def hexc(h, a=255):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


class Img:
    """A picture drawn in LOGICAL 48x48 coordinates on a K-times finer pixel grid (96x96): shapes, lines and outlines are
    computed per fine pixel, so curves are smooth and outlines/whiskers are 1 fine pixel thin; `put` fills a KxK block
    (a logical pixel), `putp` one fine pixel."""

    def __init__(self):
        self.P = N * K
        self.im = Image.new("RGBA", (self.P, self.P), (0, 0, 0, 0))

    def putp(self, px, py, c):
        px, py = int(round(px)), int(round(py))
        if 0 <= px < self.P and 0 <= py < self.P:
            self.im.putpixel((px, py), c)

    def put(self, x, y, c):
        x0, y0 = int(round(x)) * K, int(round(y)) * K
        for dy in range(K):
            for dx in range(K):
                self.putp(x0 + dx, y0 + dy, c)

    def fill(self, colour_at):
        """colour_at(x, y) in logical coords (floats) for every fine pixel; None leaves it empty."""
        for py in range(self.P):
            for px in range(self.P):
                c = colour_at((px + 0.5) / K, (py + 0.5) / K)
                if c is not None:
                    self.im.putpixel((px, py), c)

    def blob(self, inside, ramp):
        """Every fine pixel where inside(x, y) gives a value in [0,1] (None = outside), coloured from the ramp."""
        self.fill(lambda x, y: None if (v := inside(x, y)) is None else ramp[max(0, min(len(ramp) - 1, int(v * len(ramp))))])

    def line(self, pts, c):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = int(max(abs(x1 - x0), abs(y1 - y0)) * K * 1.5) + 1
            for i in range(n + 1):
                self.putp((x0 + (x1 - x0) * i / n) * K, (y0 + (y1 - y0) * i / n) * K, c)

    def outline(self, c=OUTLINE):
        src, P = self.im.copy(), self.P
        for y in range(P):
            for x in range(P):
                if src.getpixel((x, y))[3]:
                    continue
                if any(0 <= x + dx < P and 0 <= y + dy < P and src.getpixel((x + dx, y + dy))[3] and src.getpixel((x + dx, y + dy)) != c
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                    self.im.putpixel((x, y), c)


def shade_ellipse(cx, cy, rx, ry, light=(-0.55, -0.75)):
    """inside() for an ellipse: 0 = lit (top-left) ... 1 = shadow (bottom-right)."""
    def f(x, y):
        u, v = (x - cx) / rx, (y - cy) / ry
        d = u * u + v * v
        if d > 1:
            return None
        nz = math.sqrt(max(0.0, 1 - d))
        lit = -(u * light[0] + v * light[1]) + nz * 0.6  # higher = brighter
        return max(0.0, min(0.999, 0.75 - lit * 0.55))
    return f


# ---- Old Whiskers: an ancient catfish, broad flat head, long swaying barbels, a few bubbles -------------------------------
MUD = [hexc(c) for c in ("#c9b27a", "#a08a52", "#7a6a3c", "#55492a", "#3a301c")]
BELLY = [hexc(c) for c in ("#efe2b8", "#d8c690", "#b9a46c")]
FIN = [hexc(c) for c in ("#8a7444", "#65532f", "#46391f")]
WHISK = hexc("#e8dcae")
BUBBLE = hexc("#bfe6ff")


def _noise(x, y):
    """A fixed 0..1 hash per pixel, for mottling that does not crawl between frames."""
    n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return (n & 0xFFFF) / 0xFFFF


def draw_old_whiskers(t):
    c = Img()
    tau = 2 * math.pi * t
    bob = round(math.sin(tau))  # the whole fish rises and sinks a pixel
    cy = 25 + bob
    X0, X1 = 3, 39  # snout .. tail root

    def profile(x):
        """A catfish side profile: a broad, flat, wedge-shaped head; the body deepest just behind it; a long taper to a
        narrow tail root. Returns (top, bottom) in logical pixels."""
        k = (x - X0) / (X1 - X0)
        snout = math.sin(min(1.0, (x - X0) / 5) * math.pi / 2) ** 0.55  # round only the very tip
        if k < 0.38:
            e = math.sin(k / 0.38 * math.pi / 2)
            up, down = 5.2 + 4.6 * e, 5.6 + 2.6 * e  # the head is low and flat, rising to the shoulder
        else:
            e = ((k - 0.38) / 0.62) ** 1.15
            up, down = 9.8 - 7.6 * e, 8.2 - 6.0 * e  # a long, smooth taper to a thin tail root
        mid = cy + 1.0 + 1.6 * k
        return mid - up * snout, mid + down * snout

    # tail fan behind the body, flicking
    flick = 2.5 * math.sin(tau + 1.2)
    def tail(x, y):
        if not X1 - 2 <= x <= 46:
            return None
        k = (x - (X1 - 2)) / (46 - X1 + 2)
        half = 2.2 + 7.5 * k
        mid = cy + 2 + flick * k
        if abs(y - mid) > half or (k > 0.75 and abs(y - mid) < 2.2 * (k - 0.75) * 8):  # a notch in the fan
            return None
        return 0.25 + 0.6 * ((y - mid) / half + 1) / 2
    c.blob(tail, FIN)
    # dorsal and anal fins, rippling
    def dorsal(x, y):
        if not 17 <= x <= 30:
            return None
        top, _ = profile(x)
        peak = top - 6 * math.sin(math.pi * (x - 17) / 13) ** 0.8 - 0.7 * math.sin(tau + x * 0.4)
        return 0.15 + 0.6 * (y - peak) / max(1, top - peak) if peak <= y <= top + 1 else None
    c.blob(dorsal, FIN)
    def anal(x, y):
        if not 25 <= x <= 35:
            return None
        _, bot = profile(x)
        low = bot + 3.5 * math.sin(math.pi * (x - 25) / 10) + 0.6 * math.sin(tau + x * 0.5)
        return 0.4 + 0.5 * (y - bot) / max(1, low - bot) if bot - 1 <= y <= low else None
    c.blob(anal, FIN)
    # body, lit from above and a little from the front, with dark mottling on the back
    def body(x, y):
        if not X0 <= x <= X1:
            return None
        top, bot = profile(x)
        if not top <= y <= bot:
            return None
        v = (y - (top + bot) / 2) / max(1, (bot - top) / 2)
        u = (x - 20) / 20
        tone = 0.5 - 0.42 * (-v) + 0.12 * u + 0.22 * abs(v) ** 4
        if v < 0.1 and _onoise(x * 0.55, (y - cy) * 0.55) > 0.68:
            tone += 0.18  # soft mottled patches on the back, pinned to the fish so they move with it
        return max(0.0, min(0.999, tone))
    c.blob(body, MUD)
    # pale belly
    def belly(x, y):
        if not X0 + 2 <= x <= X1 - 6:
            return None
        top, bot = profile(x)
        cut = top + (bot - top) * (0.74 - 0.06 * math.sin(math.pi * (x - X0) / (X1 - X0)))  # a belly that bulges a little
        return 0.35 + 0.64 * (y - cut) / max(1, bot - cut) if cut <= y <= bot - 0.5 else None
    c.blob(belly, BELLY)
    # pectoral fin, paddling
    pf = math.sin(tau * 2)
    def pect(x, y):
        dx, dy = x - 14, y - (cy + 5)
        ang = 0.5 + 0.25 * pf
        u = dx * math.cos(ang) + dy * math.sin(ang)
        w = -dx * math.sin(ang) + dy * math.cos(ang)
        return 0.2 + 0.6 * u / 6 if 0 <= u <= 6 and abs(w) <= 2.2 * (1 - u / 7) else None
    c.blob(pect, FIN)
    # wide mouth: a dark gape line and a pale lower lip
    c.line([(X0 + 1, cy + 2), (X0 + 9, cy + 3.3)], MUD[4])
    c.line([(X0 + 1.5, cy + 2.7), (X0 + 9, cy + 4)], BELLY[1])
    # eye high on the head: dark, with a glint and a heavy brow
    ex, ey = 10.5 * K, (cy - 3.5) * K
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            c.putp(ex + dx, ey + dy, hexc("#140f0a"))
    c.putp(ex - 1, ey - 1, hexc("#f4efd8"))
    c.line([(9, cy - 5.2), (12.5, cy - 6)], MUD[4])  # a heavy, grumpy brow
    for i, (ax, ay, length, lift, phase) in enumerate(((4, cy + 1, 16, -0.2, 0.0), (6, cy + 2, 13, 0.25, 0.9),
                                                         (7, cy + 5, 7, 0.9, 1.7), (9, cy + 5, 6, 1.1, 2.4))):
        # each barbel sweeps forward (left) and curls down toward its tip, swaying more at the tip
        pts = []
        for j in range(length + 1):
            s_ = j / length
            pts.append((ax - j * (1.0 - 0.35 * s_), ay + lift * j + 5.5 * s_ ** 2.2 + 1.8 * math.sin(tau + phase + 2.4 * s_) * s_))
        c.line(pts, WHISK if i < 2 else BELLY[1])
    c.outline()
    # bubbles rising from the snout, two of them, looping
    for k, off in enumerate((0.0, 0.5)):
        p = (t + off) % 1
        bx, by = 3 + 1.2 * math.sin(2 * math.pi * p * 2 + k), cy - 6 - p * 18
        if by > 1:
            r = 1 if p < 0.45 else 2
            for ang in range(0, 360, 30):
                c.putp(bx * K + r * math.cos(math.radians(ang)), by * K + r * math.sin(math.radians(ang)), BUBBLE)
            c.putp(bx * K - r * 0.5, by * K - r * 0.5, (255, 255, 255, 255))
    return c.im


# ---- the shared scene: a murky backdrop per boss, then the boss frame ---------------------------------------------------
ORN = 10             # room outside the frame for the ornaments (wings, curls)
BAND = 5             # the gold band itself
FRAME_W = ORN + BAND # the picture starts this far in
FULL = N * K + 2 * FRAME_W  # 126x126, exported x3 = 378px
EXPORT = 3
BONE = [hexc(c) for c in ("#f6eedb", "#dccfae", "#b3a37f", "#7d6f53", "#4a4132")]
BLOOD = [hexc(c) for c in ("#ff6a5a", "#d8302a", "#8e1a18", "#4e0c0c")]


def river_backdrop(t):
    """Deep, murky river water: a dark green-teal gradient, slow light shafts, drifting silt, a muddy bed with reeds."""
    bg = Img()
    tau = 2 * math.pi * t
    top, bot = hexc("#2c5450"), hexc("#0b1a1b")

    def water(x, y):
        k = y / N
        base = [top[i] + (bot[i] - top[i]) * k for i in range(3)]
        shaft = math.sin((x + y * 0.55 + 2.5 * math.sin(tau)) * 0.32)  # light shafts that sway left and right (a clean loop)
        lift = max(0.0, shaft) ** 6 * 26 * (1 - k)
        bed = 44 + 1.5 * math.sin(x * 0.45) + 0.8 * math.sin(x * 1.3)
        if y >= bed:  # the muddy bed: a lighter lip, darker mud below
            return hexc("#3b3322") if y < bed + 0.8 else hexc("#2a2418")
        return tuple(min(255, int(v + lift)) for v in base) + (255,)
    bg.fill(water)
    for rx, ry, r in ((8, 45, 2.5), (31, 46, 3), (42, 45, 2)):
        bg.blob(shade_ellipse(rx, ry, r * 1.4, r), [hexc(c) for c in ("#55524a", "#3e3c36", "#2a2925", "#1c1b18")])
    for i, x0 in enumerate((3, 14, 20, 37, 45)):  # reeds swaying from the bed
        h = 9 + (i * 5) % 7
        for j in range(h):
            s_ = j / h
            bg.line([(x0 + 2.2 * math.sin(tau + i) * s_ ** 1.5, 45 - j), (x0 + 2.2 * math.sin(tau + i) * ((j + 1) / h) ** 1.5, 44 - j)],
                    hexc("#1f3b26") if j % 3 else hexc("#2c5233"))
    for i in range(14):  # drifting silt
        px = (i * 13.7 + t * N * (0.6 + (i % 3) * 0.2)) % N
        py = (i * 7.3 + 3 * math.sin(tau + i)) % 42
        bg.putp(px * K, py * K, hexc("#4f7a6e") if i % 2 else hexc("#6a958a"))
    return bg.im


def _onoise(a, b):
    """Smooth-ish value noise in [0,1] for wood grain (interpolated hash)."""
    ia, ib = int(math.floor(a)), int(math.floor(b))
    fa, fb = a - ia, b - ib
    def h(i, j):
        return _noise(i * 3 + 11, j * 7 + 5)
    top = h(ia, ib) * (1 - fa) + h(ia + 1, ib) * fa
    bot = h(ia, ib + 1) * (1 - fa) + h(ia + 1, ib + 1) * fa
    return top * (1 - fb) + bot * fb


def _edge_coords(x, y):
    """(depth from the outer edge, position along that edge, side 0-3) for a fine pixel of the FULL canvas."""
    d = [y, FULL - 1 - x, FULL - 1 - y, x]
    side = min(range(4), key=lambda i: d[i])
    along = [x, y, FULL - 1 - x, FULL - 1 - y][side]
    return d[side], along, side


GOLD = [hexc(c) for c in ("#fff6c8", "#ffd95a", "#e8a92a", "#b0701a", "#6e3f10")]  # light -> dark
SOCKET = hexc("#241c33")
RUBY = [hexc(c) for c in ("#ffb0a0", "#ff4a3c", "#b81c1c", "#5e0a10")]


def _outline_img(im, c=OUTLINE):
    src = im.copy()
    for y in range(im.height):
        for x in range(im.width):
            if not src.getpixel((x, y))[3] and any(0 <= x + dx < im.width and 0 <= y + dy < im.height and src.getpixel((x + dx, y + dy))[3]
                                                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                im.putpixel((x, y), c)


def _mirror_fill(im, colour_at):
    """Fill the left half from colour_at(x, y) and mirror it, so the shape is exactly symmetric. Shading that must not
    mirror (the light comes from the top-left) is passed `right` = True for the mirrored half."""
    w = im.width
    for y in range(im.height):
        for x in range((w + 1) // 2):
            for xx, right in ((x, False), (w - 1 - x, True)):
                c = colour_at(x + 0.5, y + 0.5, right)
                if c is not None:
                    im.putpixel((xx, y), c)


# ---- the regal gold frame -----------------------------------------------------------------------------------------------
# Every gold element is first drawn as a flat MASK (frame band, wings, laurel, corner scrolls, the skull); one pass then
# embosses the whole mask from its distance to the edge, lit from the top-left, so every piece shares the same shiny,
# rounded gold. Detail lines (feathers, the skull features) are cut in afterwards. Everything is drawn on the left half
# and mirrored, so it is exactly symmetric.
HALF = FULL / 2


def _cap(x0, y0, x1, y1, r):
    """A capsule (a thick line with round ends) as a point test."""
    vx, vy = x1 - x0, y1 - y0
    L2 = vx * vx + vy * vy or 1

    def f(x, y):
        k = max(0.0, min(1.0, ((x - x0) * vx + (y - y0) * vy) / L2))
        return math.hypot(x - (x0 + vx * k), y - (y0 + vy * k)) <= r
    return f


def _leaf(cx, cy, ang, length, width):
    """A pointed leaf or feather: a lens shape from (cx, cy) along angle `ang` (radians)."""
    ca, sa = math.cos(ang), math.sin(ang)

    def f(x, y):
        u = (x - cx) * ca + (y - cy) * sa
        w = -(x - cx) * sa + (y - cy) * ca
        if not 0 <= u <= length:
            return False
        return abs(w) <= width * math.sin(math.pi * u / length) ** 0.8
    return f


def _spiral(cx, cy, r0, turns, start, direction, width):
    """A shrinking spiral (a scroll curl) as a list of capsule tests."""
    pts, n = [], 40
    for i in range(n + 1):
        a = start + direction * 2 * math.pi * turns * i / n
        r = r0 * (1 - 0.8 * i / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return [_cap(*pts[i], *pts[i + 1], width * (1 - 0.5 * i / n)) for i in range(n)]


FEATHERS = ((198, 26, 3.4), (208, 24, 3.2), (218, 21, 3.0), (229, 17, 2.7), (240, 12, 2.4))  # angle, length, width
SKULL_CY = 9.5
SKULL_SCALE = 0.72  # the skull drawn at 72% of its design size


def _sk(x, y):
    """Map a canvas point into the skull's design coordinates (so the design shrinks about its centre)."""
    return HALF + (x - HALF) / SKULL_SCALE, 11 + (y - 11) / SKULL_SCALE


def _corner_shapes():
    """The top-left corner ornament: three leaves fanning out of the corner, a round boss, and a scroll curl
    running along each edge."""
    cx, cy = ORN + 2.5, ORN + 2.5
    return ([_leaf(cx, cy, math.radians(225), 11, 2.8), _leaf(cx + 1, cy, math.radians(190), 9, 2.4),
             _leaf(cx, cy + 1, math.radians(260), 9, 2.4), lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= 3.2 ** 2]
            + _spiral(ORN + 12, ORN - 3.0, 3.6, 0.9, math.radians(90), 1, 1.2)
            + _spiral(ORN - 3.0, ORN + 12, 3.6, 0.9, math.radians(0), -1, 1.2))


def _wing_shapes():
    return [_leaf(HALF - 6, 11 + i * 0.6, math.radians(ang), length, width) for i, (ang, length, width) in enumerate(FEATHERS)]


def _laurel_shapes():
    """A laurel arm on an arc round the skull, from under the jaw up past its side, leaves pointing out and up."""
    shapes, pts = [], []
    for i in range(15):
        a = math.radians(95 + 120 * i / 14)
        pts.append((HALF + 16 * math.cos(a), 12 + 13 * math.sin(a)))
    for p0, p1 in zip(pts, pts[1:]):
        shapes.append(_cap(*p0, *p1, 0.8))
    for j, i in enumerate((2, 5, 8, 11)):  # four big leaves, all pointing outward, tilted up along the arm
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        tang = math.atan2(y1 - y0, x1 - x0)
        shapes.append(_leaf(x0, y0, tang - 0.7, 8, 2.6))
        shapes.append(_leaf(x0, y0, tang + 0.5, 6, 2.0))
    return shapes


def _skull_shape(x, y):
    x, y = _sk(x, y)
    u, v = (x - HALF) / 8.8, (y - SKULL_CY) / 8.0
    hw = 5.4 - max(0.0, y - 17.5) * 0.9
    return u * u + v * v <= 1 or (13 <= y <= 21.5 and abs(x - HALF) <= hw)


def _band(x, y):
    """The frame band: a rounded-rectangle ring."""
    R = 6
    if not (ORN <= x <= FULL - ORN and ORN <= y <= FULL - ORN):
        return False
    cx_ = min(max(x, ORN + R), FULL - ORN - R)
    cy_ = min(max(y, ORN + R), FULL - ORN - R)
    if math.hypot(x - cx_, y - cy_) > R:
        return False
    return min(x - FRAME_W, y - FRAME_W, FULL - FRAME_W - x, FULL - FRAME_W - y) < 0


def _mask(shapes, flip_bottom=False):
    """A symmetric mask: shapes are tested on the left half and mirrored; flip_bottom also mirrors top to bottom."""
    m = [[False] * FULL for _ in range(FULL)]
    for y in range(FULL):
        for x in range(int(math.ceil(HALF))):
            px, py = x + 0.5, y + 0.5
            if flip_bottom and py > HALF:
                py = FULL - py
            if any(f(px, py) for f in shapes):
                m[y][x] = m[y][FULL - 1 - x] = True
    return m


def _distance(m):
    """4-neighbour distance from each gold pixel to the nearest empty one (capped)."""
    d = [[9 if m[y][x] else 0 for x in range(FULL)] for y in range(FULL)]
    for _ in range(4):
        for y in range(FULL):
            for x in range(FULL):
                if d[y][x]:
                    n = min(d[y + dy][x + dx] if 0 <= x + dx < FULL and 0 <= y + dy < FULL else 0
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                    d[y][x] = min(d[y][x], n + 1)
    return d


def _emboss(m):
    """Shiny embossed gold from a mask: tone from the height map's slope, lit from the top-left, then outlined."""
    d = _distance(m)
    im = Image.new("RGBA", (FULL, FULL), (0, 0, 0, 0))

    def h(x, y):
        return min(3, d[y][x]) if 0 <= x < FULL and 0 <= y < FULL else 0
    for y in range(FULL):
        for x in range(FULL):
            if m[y][x]:
                lit = (h(x + 1, y) - h(x - 1, y)) + (h(x, y + 1) - h(x, y - 1))
                tone = 2 - lit * 0.75 - (0.6 if d[y][x] >= 3 else 0)
                im.putpixel((x, y), GOLD[max(0, min(4, int(round(tone))))])
    _outline_img(im)
    return im


_BASE = None


def _gold_base():
    """The gold layers, back to front (each embossed and outlined on its own, so they stay distinct): computed once."""
    global _BASE
    if _BASE is not None:
        return _BASE
    im = Image.new("RGBA", (FULL, FULL), (0, 0, 0, 0))
    medallion = [lambda x, y: (x - HALF) ** 2 + (y - (FULL - ORN - 2.5)) ** 2 <= 4.5 ** 2]
    band = _emboss(_mask([_band]))
    for y in range(FULL):  # an engraved groove down the middle of the band, with a bright stud every 8 px
        for x in range(FULL):
            if not band.getpixel((x, y))[3]:
                continue
            d = min(x, y, FULL - 1 - x, FULL - 1 - y) - ORN
            along = x if min(y, FULL - 1 - y) < min(x, FULL - 1 - x) else y
            if d == BAND // 2 and ORN + 8 < along < FULL - ORN - 8:
                band.putpixel((x, y), GOLD[0] if along % 8 == 4 else GOLD[4])
    im.alpha_composite(band)
    beads = []  # a scalloped row of beads along the outer edge of the band, all four sides
    for k in range(ORN + 9, int(HALF) + 1, 4):
        beads.append(lambda x, y, k=k: (x - k) ** 2 + (y - (ORN + 0.5)) ** 2 <= 1.7 ** 2)
        beads.append(lambda x, y, k=k: (y - k) ** 2 + (x - (ORN + 0.5)) ** 2 <= 1.7 ** 2)
    im.alpha_composite(_emboss(_mask(beads, flip_bottom=True)))
    side = [_leaf(ORN + 2.5, HALF, math.radians(250), 9, 2.4), _leaf(ORN + 2.5, HALF, math.radians(110), 9, 2.4),
            _leaf(ORN + 2.5, HALF, math.radians(180), 7, 2.2), lambda x, y: (x - (ORN + 2.5)) ** 2 + (y - HALF) ** 2 <= 2.6 ** 2]
    im.alpha_composite(_emboss(_mask(side)))
    im.alpha_composite(_emboss(_mask(_corner_shapes(), flip_bottom=True)))
    im.alpha_composite(_emboss(_mask(medallion)))
    wings = _emboss(_mask(_wing_shapes()))
    for i, (ang, length, _w) in enumerate(FEATHERS):  # a darker spine down each feather
        a = math.radians(ang)
        for j in range(3, int(length) - 2):
            x, y = HALF - 6 + math.cos(a) * j, 11 + i * 0.6 + math.sin(a) * j
            for xx in (int(x), FULL - 1 - int(x)):
                if 0 <= xx < FULL and 0 <= int(y) < FULL and wings.getpixel((xx, int(y)))[3]:
                    wings.putpixel((xx, int(y)), GOLD[3])
    im.alpha_composite(wings)
    skull = _emboss(_mask([_skull_shape]))
    for y in range(FULL):  # the face: round sockets, a nose WIDER at the bottom, a row of teeth
        for x in range(int(math.ceil(HALF))):
            px, py = _sk(x + 0.5, y + 0.5)
            dx = abs(px - HALF)
            sock = ((dx - 3.6) / 2.4) ** 2 + ((py - 10.8) / 2.3) ** 2 <= 1
            nose = 13.4 <= py <= 15.9 and dx <= 0.3 + (py - 13.4) * 0.55
            bite = 18.0 <= py <= 18.9 and dx <= 4.2
            gaps = 17.4 <= py <= 20.6 and 0.5 < dx <= 4.2 and int(dx + 0.5) % 2 == 1
            if sock or nose or bite or gaps:
                for xx in (x, FULL - 1 - x):
                    skull.putpixel((xx, y), SOCKET)
    im.alpha_composite(skull)
    _BASE = im
    return im


def gold_frame(pic, t):
    """The boss frame: one regal gold border (wings, laurel, corner scrolls, a gold skull with ruby eyes) with a shine
    sweeping across it once per loop."""
    tau = 2 * math.pi * t
    out = Image.new("RGBA", (FULL, FULL), (0, 0, 0, 0))
    out.paste(pic, (FRAME_W, FRAME_W))
    gold = _gold_base().copy()
    band = -40 + t * (2 * FULL + 80)  # the shine's diagonal (x + y)
    for y in range(FULL):
        for x in range(FULL):
            c = gold.getpixel((x, y))
            if c in GOLD[1:4] and abs((x + y) - band) < 4:
                gold.putpixel((x, y), GOLD[0] if abs((x + y) - band) < 2 else GOLD[GOLD.index(c) - 1])
    eye = RUBY[1] if math.sin(tau) > -0.2 else RUBY[2]
    for ex in (int(HALF - 2.6 * SKULL_SCALE / 0.72 - 0.5), int(HALF + 2.6 * SKULL_SCALE / 0.72 - 0.5)):  # an ember in each socket
        gold.putpixel((ex, 11), eye)
        gold.putpixel((ex, 12), RUBY[2])
    gy = FULL - ORN - 2.5
    for y in range(int(gy) - 2, int(gy) + 3):  # the medallion's ruby
        for x in range(int(HALF) - 2, int(HALF) + 2):
            if (x + 0.5 - HALF) ** 2 + (y + 0.5 - gy) ** 2 <= 3.3:
                gold.putpixel((x, y), RUBY[0] if (x < HALF - 1 and y < gy - 1) else RUBY[1] if math.sin(tau) > 0 else RUBY[2])
    out.alpha_composite(gold)
    return out


def portrait(draw, backdrop, frame):
    return lambda t: frame(Image.alpha_composite(backdrop(t), draw(t)), t)


BOSSES = {"old_whiskers": portrait(draw_old_whiskers, river_backdrop, gold_frame)}


def frames(fn):
    return [fn(i / FRAMES) for i in range(FRAMES)]


def export(boss_id, fn, out_dir="cococap/assets/bosses"):
    os.makedirs(out_dir, exist_ok=True)
    big = [f.resize((f.width * EXPORT, f.height * EXPORT), Image.NEAREST) for f in frames(fn)]
    path = os.path.join(out_dir, f"{boss_id}.webp")
    big[0].save(path, save_all=True, append_images=big[1:], duration=MS, loop=0, lossless=True)
    return path


def preview(path):
    """An animated GIF of every boss portrait at its real size, on Discord-dark."""
    rows = [frames(fn) for fn in BOSSES.values()]
    w = FULL * EXPORT
    gif = []
    for i in range(FRAMES):
        g = Image.new("RGBA", (len(rows) * (w + 16) + 16, w + 32), (49, 51, 56, 255))
        for r, fr in enumerate(rows):
            g.alpha_composite(fr[i].resize((w, w), Image.NEAREST), (16 + r * (w + 16), 16))
        gif.append(g.convert("RGB"))
    gif[0].save(path.replace(".png", ".gif"), save_all=True, append_images=gif[1:], duration=MS, loop=0)
    gif[3].save(path)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        preview(sys.argv[1])
    else:
        for bid, fn in BOSSES.items():
            print(export(bid, fn))
