"""Art review sheet: build the named sprites and lay them out in ONE labelled PNG, with finished look-alikes beside them.

    .venv/bin/python -m art.review tool_axe_starter tool_axe_wilted      # names or fnmatch patterns (tool_axe_*)
    .venv/bin/python -m art.review 'tool_axe_*' --context 8               # more comparison sprites
    .venv/bin/python -m art.review 'tool_axe_*' --context 0 --out art/out/sheets/review.png

Writes art/out/sheets/review.png (default) and prints its path. Targets come first, then "for comparison": other sprites of
the same category, hand-drawn ones first, closest in kind and rarity. Only the targets are rebuilt (fast).
"""
from __future__ import annotations

import argparse
import fnmatch
import tomllib
from pathlib import Path

from PIL import Image, ImageDraw

from art.build import OUT_DIR, build_one
from art.palette import ART_DIR
from art.sprite import Sprite, load_all

SCALE, PAD, LABEL, COLS = 8, 6, 14, 6
BG = (50, 50, 60, 255)


def _hand_names() -> set[str]:
    names: set[str] = set()
    for f in (ART_DIR / "sprites").glob("*.toml"):
        names |= set(tomllib.loads(f.read_text(encoding="utf-8")))
    return names


def _kind(name: str) -> str:
    parts = name.split("_")
    return "_".join(parts[:2])


def pick_context(targets: list[Sprite], pool: list[Sprite], n: int) -> list[Sprite]:
    if n <= 0 or not targets:
        return []
    hand = _hand_names()
    names = {t.name for t in targets}
    cats = {t.category for t in targets}
    kinds = {_kind(t.name) for t in targets}
    rarities = [t.rarity for t in targets]
    mid = sum(rarities) / len(rarities)

    def score(s: Sprite) -> tuple:
        return (_kind(s.name) not in kinds, s.name not in hand, abs(s.rarity - mid), s.name)

    cand = [s for s in pool if s.name not in names and s.category in cats and not s.animated]
    return sorted(cand, key=score)[:n]


def _img(s: Sprite) -> Image.Image:
    return Image.open(next(OUT_DIR.glob(f"{s.name}.*"))).convert("RGBA")


def sheet(targets: list[Sprite], context: list[Sprite], path: Path) -> None:
    cell_w, cell_h = 16 * SCALE + PAD, 16 * SCALE + PAD + LABEL
    groups = [("", targets)] + ([("for comparison", context)] if context else [])
    rows = sum(-(-len(g) // COLS) for _, g in groups)
    heads = sum(1 for t, _ in groups if t)
    cols = max(1, min(COLS, max(len(g) for _, g in groups)))
    im = Image.new("RGBA", (cols * cell_w + PAD, rows * cell_h + heads * LABEL + PAD), BG)
    d = ImageDraw.Draw(im)
    y = PAD
    for title, group in groups:
        if title:
            d.text((PAD, y), title, fill=(160, 170, 190, 255))
            y += LABEL
        for i, s in enumerate(group):
            x, yy = PAD + (i % COLS) * cell_w, y + (i // COLS) * cell_h
            art = _img(s).resize((16 * SCALE,) * 2, Image.NEAREST)
            im.paste(art, (x, yy), art)
            d.text((x, yy + 16 * SCALE + 2), s.name.removeprefix("tool_"), fill=(220, 220, 230, 255))
        y += -(-len(group) // COLS) * cell_h
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build a labelled review sheet.")
    ap.add_argument("names", nargs="+", help="sprite names or fnmatch patterns")
    ap.add_argument("--context", type=int, default=6, help="how many comparison sprites to add (default 6, 0 = none)")
    ap.add_argument("--out", default=str(OUT_DIR / "sheets" / "review.png"))
    args = ap.parse_args(argv)
    pool = load_all()
    targets = [s for s in pool if any(fnmatch.fnmatchcase(s.name, p) for p in args.names)]
    if not targets:
        ap.error(f"nothing matches {args.names}")
    for s in targets:
        build_one(s)
    context = pick_context(targets, pool, args.context)
    sheet(targets, context, Path(args.out))
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
