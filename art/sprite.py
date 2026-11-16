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
        framed = "rarity" in d
        im = render_wisp(d["shape"], d["base"], bool(d.get("inverted", False)), framed)
        out.append(Sprite(name, "wisps", [im], [], framed, _check_rarity(d["rarity"], name) if framed else 1))
    return out


def load_sources(root: Path) -> list[Sprite]:
    """The owner's extracted emoji: <root>/<name>/frame_NN.png + meta.toml."""
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        files = sorted(d.glob("frame_*.png"))
        if not files:
            continue
        _check_name(d.name, str(d))
        meta = _read(d / "meta.toml") if (d / "meta.toml").exists() else {}
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
        out.append(Sprite(d.name, "sources", frames, ms, framed, _check_rarity(meta.get("rarity", 1), d.name), False))
    return out


def raven_dir() -> Path | None:
    """The unzipped pack folder from art/local.toml (git-ignored), or None when not configured here."""
    local = ART_DIR / "local.toml"
    if not local.exists():
        return None
    p = _read(local).get("raven_dir")
    return Path(p).expanduser() if p else None


def load_raven(mapping: Path, pack: Path | None) -> list[Sprite]:
    """Third-party icons cut from the Raven sheet. Local only: skipped when the pack is not on this machine."""
    if pack is None or not (pack / RAVEN_SHEET).exists() or not mapping.exists():
        return []
    sheet = Image.open(pack / RAVEN_SHEET).convert("RGBA")
    out = []
    for name, v in _read(mapping).items():
        _check_name(name, str(mapping))
        row, col = v[0], v[1]
        rarity = _check_rarity(v[2], name) if len(v) > 2 else 1
        cell = sheet.crop((col * GRID, row * GRID, col * GRID + GRID, row * GRID + GRID))
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
    sprites += load_raven(art_dir / "mappings" / "raven.toml", raven_dir())
    seen: dict[str, str] = {}
    for s in sprites:
        if s.name in seen:
            raise SpriteError(f"duplicate sprite name {s.name!r} ({seen[s.name]} and {s.category})")
        seen[s.name] = s.category
    return sorted(sprites, key=lambda s: (s.category, s.name))
