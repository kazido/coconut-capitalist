"""Render every sprite to art/out/<name>.png (static) or .webp (animated), 64x64, plus contact sheets.

    .venv/bin/python -m art.build [--only NAME] [--sheets]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from art.palette import ART_DIR, frame_image, outline_color
from art.sprite import Sprite, load_all

SCALE = 4  # 16 -> 64
OUT_DIR = ART_DIR / "out"
IMG2WEBP = shutil.which("img2webp") or "/opt/homebrew/bin/img2webp"
_FRAMES: dict[int, Image.Image] = {}


def add_outline(im: Image.Image) -> Image.Image:
    """A one-pixel plum outline around the opaque pixels (4-neighbour), inside the 16x16 grid."""
    plum, out = outline_color(), im.copy()
    for y in range(im.height):
        for x in range(im.width):
            if im.getpixel((x, y))[3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < im.width and 0 <= ny < im.height and im.getpixel((nx, ny))[3]:
                    out.putpixel((x, y), plum)
                    break
    return out


def compose(sprite: Sprite, frame: Image.Image) -> Image.Image:
    """One 16x16 frame as it is exported: in its rarity cell (framed) or alone, outlined if asked (free)."""
    if sprite.framed:
        if sprite.rarity not in _FRAMES:
            _FRAMES[sprite.rarity] = frame_image(sprite.rarity)
        base = _FRAMES[sprite.rarity].copy()
        base.alpha_composite(frame)  # the sprite may overlap the border; the cell's transparent corners stay as they are
        corners = _FRAMES[sprite.rarity]
        for x, y in ((0, 0), (15, 0), (0, 15), (15, 15)):
            if corners.getpixel((x, y))[3] == 0:
                base.putpixel((x, y), (0, 0, 0, 0))
        return base
    return add_outline(frame) if sprite.outline else frame.copy()


def render(sprite: Sprite) -> list[Image.Image]:
    """The 64x64 frames of a sprite."""
    return [compose(sprite, f).resize((16 * SCALE, 16 * SCALE), Image.NEAREST) for f in sprite.frames]


def write_webp(frames: list[Image.Image], ms: list[int], path: Path) -> None:
    if Path(IMG2WEBP).exists():
        with tempfile.TemporaryDirectory() as tmp:
            args = [IMG2WEBP, "-lossless"]
            for i, (f, d) in enumerate(zip(frames, ms, strict=True)):
                p = Path(tmp) / f"f{i:03d}.png"
                f.save(p)
                args += ["-d", str(d), str(p)]
            subprocess.run([*args, "-o", str(path)], check=True, capture_output=True)
        return
    # No img2webp: let Pillow write the animated WebP itself (needs libwebp, which the wheels bundle).
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0, lossless=True)


def build_one(sprite: Sprite, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = render(sprite)
    if sprite.animated:
        path = out_dir / f"{sprite.name}.webp"
        write_webp(frames, sprite.ms, path)
    else:
        path = out_dir / f"{sprite.name}.png"
        frames[0].save(path)
    return path


def contact_sheet(sprites: list[Sprite], path: Path, cols: int = 6) -> None:
    """Every sprite at 64px on a Discord-dark background, labelled with its name (first frame if animated)."""
    font = ImageFont.load_default(size=10)
    cw, ch, pad = 120, 64 + 28, 12
    rows = -(-len(sprites) // cols)
    sheet = Image.new("RGBA", (cols * cw + pad, rows * ch + pad), (0x31, 0x33, 0x38, 255))
    d = ImageDraw.Draw(sheet)
    for i, s in enumerate(sprites):
        x, y = pad + (i % cols) * cw, pad + (i // cols) * ch
        sheet.alpha_composite(render(s)[0], (x, y))
        label = s.name
        while d.textlength(label, font=font) > cw - 8 and len(label) > 3:
            label = label[:-2]
        d.text((x, y + 68), label + (" *" if s.animated else ""), fill=(210, 214, 220, 255), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the emoji art.")
    ap.add_argument("--only", metavar="NAME", help="build just this sprite")
    ap.add_argument("--sheets", action="store_true", help="also write contact sheets to art/out/sheets/<category>.png")
    args = ap.parse_args(argv)
    sprites = load_all()
    if args.only:
        sprites = [s for s in sprites if s.name == args.only]
        if not sprites:
            ap.error(f"no sprite named {args.only!r}")
    for s in sprites:
        build_one(s)
    if args.sheets:
        for cat in sorted({s.category for s in sprites}):
            contact_sheet([s for s in sprites if s.category == cat], OUT_DIR / "sheets" / f"{cat}.png")
    print(f"built {len(sprites)} sprites into {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
