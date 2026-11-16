"""Extract the owner's emoji art (.webp, 16x16 grid exported at 3x/4x) into 16x16 sprite frames with the stone cell stripped.

    python -m art.extract [--src DIR]

Writes art/sources/<name>/frame_NN.png + meta.toml (ms, source, framed, canvas) and art/sources/_cell.png.
Pillow's WebP decoder composes animated frames on the full canvas (offset/blend/dispose honoured by libwebp).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
SOURCES = HERE / "sources"
DEFAULT_SRC = Path.home() / "Downloads" / "bot emojis"
CANVAS = 16
NAMES = [
    "gemstone_balance", "gemstone_oreo", "gemstone_peace", "gemstone_rage", "gemstone_sanity", "gemstone_implosion",
    "spirit_of_the_forest", "spirit_of_the_mines", "spirit_of_the_sea", "ore_copper", "ore_gold", "ore_iron", "wyrmhole",
    "autominer", "cell", "cell_upgraded", "empty_cell", "seed_weathered", "xp_bar_empty", "xp_bar_full", "xp_bar_left", "xp_bar_right",
]
FILL = (0x2B, 0x2D, 0x31, 255)
TONES = {"H": (0x95, 0x9B, 0xA6, 255), "l": (0x6F, 0x75, 0x82, 255), "b": (0x60, 0x66, 0x74, 255), "s": (0x4D, 0x51, 0x5A, 255), "f": FILL}
CELL_ROWS = [
    ".HHHHlHHlllllll.", "HHffffffffffffbb", "Hffffffffffffffl", "Hffffffffffffffl", *["lffffffffffffffb"] * 8,
    "bffffffffffffffb", "lffffffffffffffs", "bbffffffffffffsb", ".bbbbbbbbssbsss.",
]
TRANSPARENT = (0, 0, 0, 0)
FRAMED_MIN = 0.9


def cell_at(x: int, y: int):
    ch = CELL_ROWS[y][x]
    return None if ch == "." else TONES[ch]


def border_positions():
    return [(x, y) for y in range(CANVAS) for x in range(CANVAS) if CELL_ROWS[y][x] not in ".f"]


def cell_image() -> Image.Image:
    im = Image.new("RGBA", (CANVAS, CANVAS), TRANSPARENT)
    for y in range(CANVAS):
        for x in range(CANVAS):
            c = cell_at(x, y)
            if c:
                im.putpixel((x, y), c)
    return im


def load_frames(path: Path):
    """Full-canvas RGBA frames and their durations in ms."""
    frames, ms = [], []
    with Image.open(path) as im:
        for i in range(getattr(im, "n_frames", 1)):
            im.seek(i)
            frames.append(im.convert("RGBA").copy())
            ms.append(int(im.info.get("duration", 0)))
    return frames, ms


NOISE: list[str] = []


def _near(block, tol: int = 3) -> bool:
    return all(p[3] == 255 for p in block) and all(max(p[i] for p in block) - min(p[i] for p in block) <= tol for i in range(3))


def downscale(frame: Image.Image, problems: list[str], label: str) -> Image.Image | None:
    w, h = frame.size
    if w != h or w % CANVAS:
        problems.append(f"{label}: canvas {w}x{h} is not a multiple of {CANVAS}")
        return None
    k = w // CANVAS
    out = Image.new("RGBA", (CANVAS, CANVAS))
    bad = 0
    for y in range(CANVAS):
        for x in range(CANVAS):
            block = {frame.getpixel((x * k + dx, y * k + dy)) for dx in range(k) for dy in range(k)}
            # fully transparent pixels may differ in rgb only
            block = {(0, 0, 0, 0) if p[3] == 0 else p for p in block}
            if len(block) > 1 and _near(block):
                # lossy-encoder noise (1-3 levels per channel): snap to the block's most common colour
                count = {}
                for dx in range(k):
                    for dy in range(k):
                        p = frame.getpixel((x * k + dx, y * k + dy))
                        count[p] = count.get(p, 0) + 1
                block = {max(count, key=count.get)}
                NOISE.append(label)
            if len(block) != 1:
                bad += 1
                continue
            out.putpixel((x, y), block.pop())
    if bad:
        problems.append(f"{label}: {bad} of 256 blocks are not uniform at scale {k}")
        return None
    return out


def is_framed(first: Image.Image) -> bool:
    pos = border_positions()
    hits = sum(first.getpixel(p) == cell_at(*p) for p in pos)
    return hits / len(pos) >= FRAMED_MIN


def is_cell(p, x: int, y: int) -> bool:
    """A pixel that is just the cell showing through in this frame (glow that animates over it differs, so it survives)."""
    if p == FILL and 1 <= x <= 14 and 1 <= y <= 14:
        return True
    return p == cell_at(x, y)


def strip(frames: list[Image.Image]) -> list[Image.Image]:
    out = []
    for f in frames:
        g = f.copy()
        for y in range(CANVAS):
            for x in range(CANVAS):
                if is_cell(f.getpixel((x, y)), x, y):
                    g.putpixel((x, y), TRANSPARENT)
        out.append(g)
    return out


def write_meta(d: Path, ms: list[int], source: str, framed: bool):
    d.joinpath("meta.toml").write_text(
        f'source = "{source}"\nframed = {str(framed).lower()}\ncanvas = {CANVAS}\nms = [{", ".join(map(str, ms))}]\n'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    args = ap.parse_args()
    SOURCES.mkdir(parents=True, exist_ok=True)
    cell_image().save(SOURCES / "_cell.png")
    # sanity: the shipped cell map must match empty_cell.webp
    empty = args.src / "empty_cell.webp"
    if empty.exists():
        fr, _ = load_frames(empty)
        small = downscale(fr[0], [], "empty_cell")
        assert small is not None and small.tobytes() == cell_image().tobytes(), "cell map differs from empty_cell.webp"
    problems: list[str] = []
    for name in NAMES:
        path = args.src / f"{name}.webp"
        big, ms = load_frames(path)
        k = big[0].size[0] // CANVAS
        small = [downscale(f, problems, f"{name}[{i}]") for i, f in enumerate(big)]
        if any(s is None for s in small):
            print(f"{name}: SKIPPED (not block-aligned)")
            continue
        framed = is_framed(small[0])
        frames = strip(small) if framed else small
        d = SOURCES / name
        d.mkdir(exist_ok=True)
        for old in d.glob("frame_*.png"):
            old.unlink()
        for i, f in enumerate(frames):
            f.save(d / f"frame_{i:02d}.png")
        write_meta(d, ms, f"{name}.webp", framed)
        print(f"{name}: framed={framed} frames={len(frames)} scale={k} ms={ms}")
    for lbl in sorted(set(NOISE)):
        print("NOTE noise-snapped blocks in", lbl)
    for p in problems:
        print("PROBLEM", p)


if __name__ == "__main__":
    main()
