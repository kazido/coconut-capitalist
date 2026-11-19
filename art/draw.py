"""Tiny helpers for drawing 16x16 sprites in code (the way the owner-approved icons were made).

Why code, not freehand rows: shapes come out exact (circles, ellipses, straight lines), shading follows one light
direction (top-left) everywhere, and a tweak is a number change, not re-typing 16 strings.

Usage (from a scratch script):

    from art.draw import Canvas, ell, circ, union
    c = Canvas()
    c.shade(circ(7.5, 6, 5), "Hmsd")          # 4-tone ramp, light -> dark
    c.rect(7, 10, 8, 14, "B")                  # trunk
    c.sprite("species_oak", {"H": "#b6e86a", "m": "#6cc044", "s": "#3c8c34", "d": "#22582a", "B": "#9a6a44"})
    open("art/sprites/my_file.toml", "w").write(c.toml(header="# what these are"))

Every sprite is `kind = "free"` with `outline = true`: the build adds the plum outline, so leave a 1px empty margin.
"""
from __future__ import annotations

import math

N = 16


def ell(cx: float, cy: float, rx: float, ry: float):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def circ(cx: float, cy: float, r: float):
    return lambda x, y: math.hypot(x - cx, y - cy) <= r


def union(*masks):
    return lambda x, y: any(m(x, y) for m in masks)


class Canvas:
    """One 16x16 grid of palette letters ('.' = transparent), plus the sprites finished so far."""

    def __init__(self):
        self.g = [["." for _ in range(N)] for _ in range(N)]
        self.done: dict[str, tuple[list[list[str]], dict[str, str]]] = {}

    def put(self, x: int, y: int, c: str) -> None:
        if 0 <= x < N and 0 <= y < N:
            self.g[y][x] = c

    def rect(self, x0: int, y0: int, x1: int, y1: int, c: str) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c)

    def line(self, x0: int, y0: int, x1: int, y1: int, c: str) -> None:
        n = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(n + 1):
            self.put(round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n), c)

    def fill(self, mask, c: str) -> None:
        for y in range(N):
            for x in range(N):
                if mask(x, y):
                    self.put(x, y, c)

    def shade(self, mask, ramp: str, cx: float = 7.5, cy: float = 7.5, r: float = 6) -> None:
        """Fill `mask` with a light->dark `ramp` (2-4 letters), lit from the top-left; the bottom-right rim is kept in shadow."""
        for y in range(N):
            for x in range(N):
                if not mask(x, y):
                    continue
                light = -((x - cx) + (y - cy)) / (math.sqrt(2) * r)
                i = 0 if light > 0.5 else 1 if light > -0.05 else 2 if light > -0.6 else 3
                if not mask(x + 1, y + 1) and i < 2:
                    i = 2
                self.put(x, y, ramp[min(i, len(ramp) - 1)])

    def sprite(self, name: str, palette: dict[str, str]) -> None:
        """Finish the current drawing as `name` and start a blank one."""
        self.done[name] = (self.g, palette)
        self.g = [["." for _ in range(N)] for _ in range(N)]

    def toml(self, header: str = "") -> str:
        out = [header + "\n"] if header else []
        for name, (g, pal) in self.done.items():
            used = {c for row in g for c in row if c != "."}
            missing = used - set(pal)
            if missing:
                raise ValueError(f"{name}: palette has no colour for {sorted(missing)}")
            out += [f"[{name}]", 'kind = "free"', "outline = true",
                    "palette = { " + ", ".join(f'{k} = "{v}"' for k, v in pal.items() if k in used) + " }", "rows = ["]
            out += [f'  "{"".join(row)}",' for row in g]
            out.append("]\n")
        return "\n".join(out)
