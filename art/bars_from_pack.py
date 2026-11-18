"""Cut the pixel UI pack's bars into emoji segments (left end, middle, right end) in four colours.

    .venv/Scripts/python.exe -m art.bars_from_pack

Reads `art/downloaded/Pixel UI pack 3.zip` (a third-party pack that stays local, never committed) and writes
`art/sources/ui_bar_<colour>_<part>/` (frame_00.png + meta.toml), which `python -m art.build` turns into emoji. Style: the beveled
(slanted) bars. A bar is built in code from segments: left + middle x N + right, using the coloured segments for the filled part
and the shared `ui_bar_empty_*` segments for the rest (see cococap/ui/components.py `colored_bar`).
Colours (top to bottom in the pack): red, yellow, blue, green.
"""

import io
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
ZIP = ROOT / "downloaded" / "Pixel UI pack 3.zip"
SHEET = "04.png"
FULL_X = (51, 92)  # a full bar's columns on the sheet (the beveled style), then an empty one:
EMPTY_X = (291, 332)
BANDS = {"red": (6, 10), "yellow": (22, 26), "blue": (38, 42), "green": (54, 58)}  # rows of each colour's bar


def _cell(bar: Image.Image, part: str) -> Image.Image:
    """A 16x16 emoji cell holding the left end, a middle slice or the right end of a bar, centred vertically."""
    w, h = bar.size
    x = {"left": 0, "mid": w // 2 - 8, "right": w - 16}[part]
    cell = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    piece = bar.crop((x, 0, x + 16, h))
    cell.paste(piece, (0, (16 - h) // 2), piece)
    return cell


def _write(name: str, cell: Image.Image) -> None:
    folder = ROOT / "sources" / name
    folder.mkdir(parents=True, exist_ok=True)
    cell.save(folder / "frame_00.png")
    (folder / "meta.toml").write_text(f'source = "Pixel UI pack 3.zip ({SHEET}), cut by art/bars_from_pack.py"\nframed = false\nemit = true\ncanvas = 16\nms = [0]\n')


def main() -> None:
    with zipfile.ZipFile(ZIP) as z:
        sheet = Image.open(io.BytesIO(z.read(SHEET))).convert("RGBA")
    made = 0
    for colour, (y0, y1) in BANDS.items():
        full = sheet.crop((FULL_X[0], y0, FULL_X[1] + 1, y1 + 1))
        for part in ("left", "mid", "right"):
            _write(f"ui_bar_{colour}_{part}", _cell(full, part))
            made += 1
    empty = sheet.crop((EMPTY_X[0], BANDS["red"][0], EMPTY_X[1] + 1, BANDS["red"][1] + 1))  # the empty bars are the same in every colour
    for part in ("left", "mid", "right"):
        _write(f"ui_bar_empty_{part}", _cell(empty, part))
        made += 1
    print(f"wrote {made} bar segments to art/sources/")


if __name__ == "__main__":
    main()
