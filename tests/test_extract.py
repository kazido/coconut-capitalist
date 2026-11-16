"""The owner's emoji art, extracted to 16x16 frames with the cell stripped (art/extract.py)."""
import tomllib
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from art import extract as E  # noqa: E402

# Not on the 16x16 grid (drawn at a finer scale / sub-pixel motion): reported, not extracted.
UNALIGNED = {"spirit_of_the_forest", "spirit_of_the_mines", "spirit_of_the_sea", "autominer"}

if not E.DEFAULT_SRC.exists() or not E.SOURCES.exists():
    pytest.skip("owner art or art/sources missing", allow_module_level=True)

EXTRACTED = [n for n in E.NAMES if n not in UNALIGNED]


def frames(name):
    return [Image.open(p).convert("RGBA") for p in sorted((E.SOURCES / name).glob("frame_*.png"))]


@pytest.mark.parametrize("name", EXTRACTED)
def test_source_frames(name):
    meta = tomllib.loads((E.SOURCES / name / "meta.toml").read_text())
    fr = frames(name)
    assert fr and meta["canvas"] == 16 and meta["source"] == f"{name}.webp"
    assert len(meta["ms"]) == len(fr)
    assert all(f.size == (16, 16) for f in fr)


@pytest.mark.parametrize("name", EXTRACTED)
def test_no_cell_tone_left_on_border(name):
    meta = tomllib.loads((E.SOURCES / name / "meta.toml").read_text())
    if not meta["framed"]:
        return
    for f in frames(name):
        for x, y in E.border_positions():
            p = f.getpixel((x, y))
            assert p[3] == 0 or p != E.cell_at(x, y), (name, x, y)


def test_unaligned_have_no_sources():
    assert all(not (E.SOURCES / n).exists() for n in UNALIGNED)
    assert (E.SOURCES / "_cell.png").exists()
