"""Colours and the cell frame, read from art/palette.toml. Needs Pillow."""
from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

from PIL import Image

ART_DIR = Path(__file__).resolve().parent
RGBA = tuple[int, int, int, int]

# The owner's cell, read off their drawing. H highlight, l light, b base, s shadow, f fill, . transparent corner.
FRAME = [
    ".HHHHlHHlllllll.", "HHffffffffffffbb", "Hffffffffffffffl", "Hffffffffffffffl",
    "lffffffffffffffb", "lffffffffffffffb", "lffffffffffffffb", "lffffffffffffffb",
    "lffffffffffffffb", "lffffffffffffffb", "lffffffffffffffb", "lffffffffffffffb",
    "bffffffffffffffb", "lffffffffffffffs", "bbffffffffffffsb", ".bbbbbbbbssbsss.",
]

WHITE: RGBA = (255, 255, 255, 255)
BLACK: RGBA = (0, 0, 0, 255)


def rgb(hex_: str) -> RGBA:
    h = hex_.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def mix(c: RGBA, target: RGBA, k: float) -> RGBA:
    return (*(round(c[i] + (target[i] - c[i]) * k) for i in range(3)), 255)


@lru_cache(maxsize=1)
def load() -> dict:
    with open(ART_DIR / "palette.toml", "rb") as f:
        return tomllib.load(f)


def outline_color() -> RGBA:
    return rgb(load()["outline"]["color"])


def rarity_colors() -> dict[int, str]:
    """rarity value (1-7) -> '#RRGGBB'."""
    return {r["value"]: r["color"] for r in load()["rarity"]}


def border_tones(color_hex: str) -> dict[str, RGBA]:
    """H, l, b, s border tones for a rarity colour (the prototype's tones())."""
    c, m = rgb(color_hex), load()["border_mix"]
    return {"H": mix(c, WHITE, m["highlight"]), "l": c, "b": mix(c, BLACK, m["base"]), "s": mix(c, BLACK, m["shadow"])}


def cell_tones() -> dict[str, RGBA]:
    t = load()["cell"]
    return {"H": rgb(t["highlight"]), "l": rgb(t["light"]), "b": rgb(t["base"]), "s": rgb(t["shadow"])}


def frame_image(rarity: int | None = None) -> Image.Image:
    """A 16x16 cell. rarity None = the owner's grey cell; 1-7 = the border recoloured to that rarity."""
    tones = cell_tones() if rarity is None else border_tones(rarity_colors()[rarity])
    fill = rgb(load()["cell"]["fill"])
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(FRAME):
        for x, ch in enumerate(row):
            if ch != ".":
                im.putpixel((x, y), fill if ch == "f" else tones[ch])
    return im
