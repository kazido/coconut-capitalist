"""Runtime tool renderer (cococap/art_runtime.py) and its data file, which must match the generator."""
import io
import json
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from art.gen.tool_layers import TIERS, layers  # noqa: E402
from cococap import art_runtime  # noqa: E402

KINDS = sorted(layers())
DATA_PATH = Path(art_runtime.__file__).resolve().parent / "assets" / "tool_layers.json"


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("tiers", [(1, 1, 1), (3, 3, 1), (7, 7, 7), (8, 8, 8)])
def test_every_kind_renders_a_valid_png(kind, tiers):
    scale = 4
    png = art_runtime.render_tool(kind, *tiers, scale=scale, cache_dir=None)
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.mode == "RGBA"
    assert img.size == (18 * scale, 18 * scale)


def test_different_tiers_give_different_bytes():
    a = art_runtime.render_tool("pickaxe", 1, 1, 1, cache_dir=None)
    b = art_runtime.render_tool("pickaxe", 7, 7, 7, cache_dir=None)
    assert a != b


def test_cache_file_is_written_and_reused(tmp_path):
    first = art_runtime.render_tool("axe", 3, 5, 2, scale=8, cache_dir=tmp_path)
    cached = tmp_path / "axe_352_x8.png"
    assert cached.exists()
    assert cached.read_bytes() == first
    # A reused cache must be served from disk, not re-rendered.
    cached.write_bytes(b"sentinel")
    assert art_runtime.render_tool("axe", 3, 5, 2, scale=8, cache_dir=tmp_path) == b"sentinel"


@pytest.mark.parametrize(
    "kind, tier",
    [("nope", 1), ("pickaxe", 0), ("pickaxe", 9)],
)
def test_bad_kind_or_tier_raises(kind, tier):
    with pytest.raises(ValueError):
        art_runtime.render_tool(kind, tier, 1, 1, cache_dir=None)


def test_bad_trim_or_accent_tier_raises():
    with pytest.raises(ValueError):
        art_runtime.render_tool("can", 1, 9, 1, cache_dir=None)
    with pytest.raises(ValueError):
        art_runtime.render_tool("can", 1, 1, 0, cache_dir=None)


def test_data_file_matches_generator():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert data["tiers"] == {str(n): list(ramp) for n, ramp in TIERS.items()}
    assert data["kinds"] == {k: ["".join(row) for row in g] for k, g in layers().items()}
