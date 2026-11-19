"""Render every sprite to art/out/<name>.png (static) or .webp (animated): free sprites 64x64, framed items 120x120 (art/rarity_style.py), plus contact sheets.

    .venv/bin/python -m art.build [--only NAME] [--sheets]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from art import rarity_style
from art.palette import ART_DIR, outline_color
from art.sprite import Sprite, load_all

SCALE = 4  # 16 -> 64
OUT_DIR = ART_DIR / "out"
IMG2WEBP = shutil.which("img2webp") or "/opt/homebrew/bin/img2webp"


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
    """One free 16x16 frame as it is exported: outlined if asked. (Framed items are built by rarity_style.framed.)"""
    return add_outline(frame) if sprite.outline else frame.copy()


def render_timed(sprite: Sprite) -> tuple[list[Image.Image], list[int]]:
    """The exported frames of a sprite and their ms (ms empty when the output is still)."""
    if sprite.framed:
        frames, ms = rarity_style.framed(sprite)
        return [rarity_style.scale(f) for f in frames], ms
    return [compose(sprite, f).resize((16 * SCALE, 16 * SCALE), Image.NEAREST) for f in sprite.frames], sprite.ms


def render(sprite: Sprite) -> list[Image.Image]:
    """The exported frames of a sprite (see render_timed)."""
    return render_timed(sprite)[0]


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
    frames, ms = render_timed(sprite)
    if len(frames) > 1:
        path = out_dir / f"{sprite.name}.webp"
        write_webp(frames, ms, path)
        stale = out_dir / f"{sprite.name}.png"
    else:
        path = out_dir / f"{sprite.name}.png"
        frames[0].save(path)
        stale = out_dir / f"{sprite.name}.webp"
    stale.unlink(missing_ok=True)  # the uploader marks a name INVALID when both files exist
    return path


def contact_sheet(sprites: list[Sprite], path: Path, cols: int = 6) -> None:
    """Every sprite on a Discord-dark background, labelled with its name (first frame if animated)."""
    font = ImageFont.load_default(size=10)
    cw, ch, pad = 124, 124 + 28, 12
    rows = -(-len(sprites) // cols)
    sheet = Image.new("RGBA", (cols * cw + pad, rows * ch + pad), (0x31, 0x33, 0x38, 255))
    d = ImageDraw.Draw(sheet)
    for i, s in enumerate(sprites):
        x, y = pad + (i % cols) * cw, pad + (i // cols) * ch
        sheet.alpha_composite(render(s)[0], (x, y))
        label = s.name
        while d.textlength(label, font=font) > cw - 8 and len(label) > 3:
            label = label[:-2]
        d.text((x, y + 128), label + (" *" if s.animated else ""), fill=(210, 214, 220, 255), font=font)
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
