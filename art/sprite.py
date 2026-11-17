"""Sprites: a 16x16 RGBA art grid (or several frames) plus metadata, and every place one can come from.

Sources (see docs/DESIGN.md, "Emoji art pipeline"):
  art/sprites/<category>.toml   hand-authored: [name] palette = {letter = "#hex"}, rows = [16 x 16 chars], optional frames
  art/wisps.toml                generated: [name] shape, base, inverted (art/wisp.py)
  art/sources/<name>/           the owner's own emoji, extracted: frame_NN.png (16x16) + meta.toml (ms = [..], framed = bool)
  art/mappings/raven.toml       third-party icons, LOCAL ONLY: item_id = [row, col] into the pack's 16x16 sheet
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from art.palette import ART_DIR, rgb
from art.wisp import render_wisp

NAME_RE = re.compile(r"^[a-z0-9_]{2,32}$")  # Discord emoji names
GRID = 16
RAVEN_SHEET = "Full Spritesheet/16x16.png"


SHINE_MIN_RARITY = 6  # Premium and Mythical items shine; set to 8 to turn the shine off


class SpriteError(ValueError):
    pass


@dataclass
class Sprite:
    name: str
    category: str
    frames: list[Image.Image]            # 16x16 RGBA
    ms: list[int] = field(default_factory=list)  # per-frame duration, only when animated
    framed: bool = False                 # sits in the cell, recoloured by rarity
    rarity: int = 1                      # 1-7, framed only
    outline: bool = False                # free sprites: add the plum outline automatically

    @property
    def animated(self) -> bool:
        return len(self.frames) > 1


def _check_name(name: str, where: str) -> None:
    if not NAME_RE.match(name):
        raise SpriteError(f"{where}: name {name!r} must match [a-z0-9_]{{2,32}}")


def _check_rarity(r: int, name: str) -> int:
    if not isinstance(r, int) or not 1 <= r <= 7:
        raise SpriteError(f"{name}: rarity must be 1-7, got {r!r}")
    return r


def grid_image(rows: list[str], palette: dict[str, str], name: str = "?") -> Image.Image:
    """Turn 16 strings of 16 palette letters into an image. '.' is transparent."""
    if len(rows) != GRID:
        raise SpriteError(f"{name}: needs {GRID} rows, has {len(rows)}")
    pal = {k: rgb(v) for k, v in palette.items()}
    if "." in pal:
        raise SpriteError(f"{name}: '.' is reserved for transparent")
    im = Image.new("RGBA", (GRID, GRID), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        if len(row) != GRID:
            raise SpriteError(f"{name}: row {y} has {len(row)} chars, needs {GRID}")
        for x, ch in enumerate(row):
            if ch == ".":
                continue
            if ch not in pal:
                raise SpriteError(f"{name}: row {y} uses {ch!r}, which is not in its palette")
            im.putpixel((x, y), pal[ch])
    return im


def _read(path: Path) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_hand(path: Path) -> list[Sprite]:
    category = path.stem
    out = []
    for name, d in _read(path).items():
        _check_name(name, str(path))
        pal = d.get("palette", {})
        if "frames" in d:
            frames = [grid_image(f["rows"], pal, name) for f in d["frames"]]
            ms = [int(f.get("ms", d.get("ms", 100))) for f in d["frames"]]
        else:
            frames, ms = [grid_image(d["rows"], pal, name)], []
        kind = d.get("kind", "framed" if "rarity" in d else "free")
        if kind not in ("framed", "free"):
            raise SpriteError(f"{name}: kind must be 'framed' or 'free'")
        framed = kind == "framed"
        out.append(Sprite(name, category, frames, ms, framed, _check_rarity(d.get("rarity", 1), name) if framed else 1,
                          bool(d.get("outline", False)) and not framed))
    return out


def load_wisps(path: Path) -> list[Sprite]:
    out = []
    for name, d in _read(path).items():
        _check_name(name, str(path))
        if d.get("kind") == "flame":  # slim flame wisps (art/flame.py): animated, frameless, no outline
            from art.flame import FRAME_MS, render_flame_frames

            frames = render_flame_frames(d["base"], d.get("face", "core"), bool(d.get("embers", True)), d.get("accent"))
            out.append(Sprite(name, "wisps", frames, [FRAME_MS] * len(frames), False, 1, False))
            continue
        framed = "rarity" in d
        im = render_wisp(d["shape"], d["base"], bool(d.get("inverted", False)), framed)
        out.append(Sprite(name, "wisps", [im], [], framed, _check_rarity(d["rarity"], name) if framed else 1))
    return out


def _legacy_items() -> dict[str, str]:
    """{old emoji name: item id} for the owner's emoji that are items (cococap.emojis.ALIASES), minus names that already equal the item id."""
    from cococap.emojis import ALIASES

    return {k: v for k, v in ALIASES.items() if k != v}


def load_sources(root: Path) -> list[Sprite]:
    """The owner's extracted emoji: <root>/<name>/frame_NN.png + meta.toml."""
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        files = sorted(d.glob("frame_*.png"))
        if not files:
            continue
        _check_name(d.name, str(d))
        meta = _read(d / "meta.toml") if (d / "meta.toml").exists() else {}
        # The owner's emoji are named for how they were first uploaded (gemstone_sanity, ore_iron). Those that ARE items are rebuilt under the
        # ITEM id with the item's real rarity (the game finds an emoji named by item id first); the rest (cells, xp bars, wyrmhole...)
        # are UI pieces already uploaded under their old names and stay exactly as they are (not built).
        name, rarity = d.name, _check_rarity(meta.get("rarity", 1), d.name)
        if "item" in meta or d.name in _legacy_items():
            name = str(meta.get("item", _legacy_items().get(d.name)))
            rarity = _item_rarity(name)
        elif not meta.get("emit", False):
            continue
        frames = []
        for f in files:
            im = Image.open(f).convert("RGBA")
            if im.size != (GRID, GRID):
                raise SpriteError(f"{f}: must be {GRID}x{GRID}, is {im.size}")
            frames.append(im)
        ms = [int(m) for m in meta.get("ms", [])] if len(frames) > 1 else []
        if len(frames) > 1 and len(ms) != len(frames):
            raise SpriteError(f"{d}: meta.toml ms needs {len(frames)} entries")
        framed = bool(meta.get("framed", False))
        if name != d.name and meta.get("restyle", True):  # the owner's item art gets the shared refresh (outline, richer colour, specular)
            from art.restyle import restyle_frames

            frames = restyle_frames(frames)
        out.append(Sprite(name, "sources", frames, ms, framed, rarity, False))
    return out


def raven_dir() -> Path | None:
    """The unzipped pack folder from art/local.toml (git-ignored), or None when not configured here."""
    local = ART_DIR / "local.toml"
    if not local.exists():
        return None
    p = _read(local).get("raven_dir")
    return Path(p).expanduser() if p else None


def _recolor(im: Image.Image, hue: float = 0.0, sat: float = 1.0, val: float = 1.0) -> Image.Image:
    """Shift hue (degrees), scale saturation and value of every opaque pixel (palette swap: copper -> iron -> gold from one icon)."""
    import colorsys

    out = im.copy()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = out.getpixel((x, y))
            if a:
                h, s_, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                r2, g2, b2 = colorsys.hsv_to_rgb((h + hue / 360) % 1.0, min(1.0, s_ * sat), min(1.0, v * val))
                out.putpixel((x, y), (round(r2 * 255), round(g2 * 255), round(b2 * 255), a))
    return out


def _item_rarity(name: str) -> int:
    """The item's rarity from the game data (1 when the id is not an item)."""
    try:
        from cococap.registry import get_registry

        item = get_registry().find_item(name)
        return int(item.rarity) if item is not None else 1
    except Exception:  # (art tooling must still run when the game data cannot load)
        return 1


def load_raven(mapping: Path, pack: Path | None) -> list[Sprite]:
    """Third-party icons cut from the Raven sheet. Local only: skipped when the pack is not on this machine.

    A mapping value is `[row, col]` or a table `{cell = [row, col], hue = 40, sat = 1.0, val = 1.0, nudge = [dx, dy], rarity = 3}`;
    the rarity defaults to the item's own rarity."""
    if pack is None or not (pack / RAVEN_SHEET).exists() or not mapping.exists():
        return []
    sheet = Image.open(pack / RAVEN_SHEET).convert("RGBA")
    out = []
    for name, v in _read(mapping).items():
        _check_name(name, str(mapping))
        opts = v if isinstance(v, dict) else {"cell": v}
        row, col = opts["cell"][0], opts["cell"][1]
        rarity = _check_rarity(opts.get("rarity", _item_rarity(name)), name)
        cell = sheet.crop((col * GRID, row * GRID, col * GRID + GRID, row * GRID + GRID))
        if any(k in opts for k in ("hue", "sat", "val")):
            cell = _recolor(cell, float(opts.get("hue", 0)), float(opts.get("sat", 1.0)), float(opts.get("val", 1.0)))
        dx, dy = opts.get("nudge", [0, 0])
        if dx or dy:
            moved = Image.new("RGBA", cell.size, (0, 0, 0, 0))
            moved.alpha_composite(cell, (dx, dy)) if dx >= 0 and dy >= 0 else moved.paste(cell, (dx, dy))
            cell = moved
        out.append(Sprite(name, "raven", [cell], [], True, rarity))
    return out


def load_all(art_dir: Path = ART_DIR) -> list[Sprite]:
    """Every sprite, sorted by (category, name). Names must be unique across all sources."""
    sprites: list[Sprite] = []
    for p in sorted((art_dir / "sprites").glob("*.toml")):
        sprites += load_hand(p)
    if (art_dir / "wisps.toml").exists():
        sprites += load_wisps(art_dir / "wisps.toml")
    sprites += load_sources(art_dir / "sources")
    for mp in sorted((art_dir / "mappings").glob("raven*.toml")):
        sprites += load_raven(mp, raven_dir())
    # A hand-drawn (or owner) sprite replaces a third-party pick of the same name: drawing a better icon never needs a mapping edit.
    own = {s.name for s in sprites if s.category != "raven"}
    sprites = [s for s in sprites if s.category != "raven" or s.name not in own]
    seen: dict[str, str] = {}
    for s in sprites:
        if s.name in seen:
            raise SpriteError(f"duplicate sprite name {s.name!r} ({seen[s.name]} and {s.category})")
        seen[s.name] = s.category
    for s in sprites:  # the top rarities get a gentle shine (art/shine.py); art with its own animation keeps it
        if s.framed and len(s.frames) == 1 and s.rarity >= SHINE_MIN_RARITY and s.category not in ("sources", "wisps"):
            from art.shine import shine_frames

            s.frames, s.ms = shine_frames(s.frames[0])
    return sorted(sprites, key=lambda s: (s.category, s.name))
