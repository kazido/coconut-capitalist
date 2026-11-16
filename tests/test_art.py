"""The emoji art pipeline (art/): palette, sprite sources, build output, and the no-third-party-images rule."""
import subprocess
import tomllib
from pathlib import Path

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from art import build, palette  # noqa: E402
from art.sprite import NAME_RE, SpriteError, grid_image, load_all, load_hand  # noqa: E402
from art.wisp import SHAPES, check_shape  # noqa: E402
from cococap.constants import Rarities  # noqa: E402

ART = Path(build.ART_DIR)
ROOT = ART.parent
HAND_FILES = sorted((ART / "sprites").glob("*.toml"))


def test_palette_matches_rarities():
    colors = palette.rarity_colors()
    assert sorted(colors) == [r.value for r in Rarities]
    for r in Rarities:
        assert colors[r.value].lstrip("#").upper() == r.color[2:].upper()
        assert palette.load()["rarity"][r.value - 1]["name"] == r.rarity_name


def test_cell_tones_and_outline_from_palette():
    assert palette.cell_tones()["H"] == palette.rgb("959ba6")
    assert palette.outline_color() == palette.rgb("2e1c2c")
    t = palette.border_tones("#8E9AAF")
    assert t["l"] == palette.rgb("8E9AAF")
    assert t["H"][0] > t["l"][0] > t["b"][0] > t["s"][0]


def test_hand_sprites_are_16x16_and_use_only_palette_letters():
    assert HAND_FILES
    for path in HAND_FILES:
        for name, d in tomllib.loads(path.read_text()).items():
            row_sets = [f["rows"] for f in d["frames"]] if "frames" in d else [d["rows"]]
            for rows in row_sets:
                assert len(rows) == 16, name
                for row in rows:
                    assert len(row) == 16, name
                    assert set(row) <= set(d["palette"]) | {"."}, (name, row)


def test_names_are_unique_and_valid_discord_names():
    sprites = load_all()
    names = [s.name for s in sprites]
    assert len(names) == len(set(names))
    for n in names:
        assert NAME_RE.match(n), n


def test_bad_sprites_are_rejected(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text('[ab]\npalette = {a = "#fff000"}\nrows = ["' + "a" * 15 + '"] \n')
    with pytest.raises(SpriteError):
        load_hand(bad)
    with pytest.raises(SpriteError):
        grid_image(["z" * 16] * 16, {"a": "#ffffff"})
    bad.write_text('[Bad-Name]\npalette = {a = "#fff000"}\nrows = []\n')
    with pytest.raises(SpriteError):
        load_hand(bad)


def test_wisp_shapes_are_valid():
    for name, rows in SHAPES.items():
        check_shape(name, rows)
    with pytest.raises(ValueError):
        check_shape("x", ["##", "#"])


def test_built_png_is_64x64_rgba(tmp_path):
    sprite = next(s for s in load_all() if s.name == "iron_bar")
    path = build.build_one(sprite, tmp_path)
    im = Image.open(path)
    assert im.size == (64, 64) and im.mode == "RGBA"
    # corners of the cell stay transparent
    assert im.getpixel((0, 0))[3] == 0


def test_build_is_deterministic(tmp_path):
    sprite = next(s for s in load_all() if s.name == "ember")
    a, b = build.build_one(sprite, tmp_path / "a"), build.build_one(sprite, tmp_path / "b")
    assert a.read_bytes() == b.read_bytes()


def test_framed_output_has_rarity_border_colour(tmp_path):
    hand = [s for s in load_all() if s.framed and s.category == "items"]
    assert {s.rarity for s in hand} != {1}
    for s in hand:
        im = Image.open(build.build_one(s, tmp_path))
        # (0, 4) on the 16 grid is a border pixel of the "light" tone = the rarity colour itself; it is 4x4 pixels at 64
        want = palette.rgb(palette.rarity_colors()[s.rarity])
        assert {im.getpixel((x, y)) for x in range(4) for y in range(16, 20)} == {want}, s.name


def test_free_sprite_outline(tmp_path):
    toml = tmp_path / "icons.toml"
    rows = ["." * 16] * 16
    rows[8] = "." * 8 + "a" + "." * 7
    toml.write_text('[dot]\noutline = true\npalette = {a = "#ffffff"}\nrows = [' + ",".join(f'"{r}"' for r in rows) + "]\n")
    s = load_hand(toml)[0]
    im = build.compose(s, s.frames[0])
    assert im.getpixel((8, 8)) == palette.rgb("ffffff")
    assert im.getpixel((7, 8)) == palette.outline_color()
    assert im.getpixel((8, 9)) == palette.outline_color()
    assert im.getpixel((7, 7))[3] == 0  # diagonals are not outlined


def _anmf_count(path):
    data = path.read_bytes()
    assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return data.count(b"ANMF")


def test_animated_build_writes_webp_with_every_frame(tmp_path):
    from art.sprite import Sprite

    frames = [Image.new("RGBA", (16, 16), c) for c in ((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255))]
    s = Sprite("blink", "test", frames, [80, 120, 200], framed=True, rarity=3)
    path = build.build_one(s, tmp_path)
    assert path.suffix == ".webp"
    assert _anmf_count(path) == 3
    assert Image.open(path).size == (64, 64)


def test_contact_sheet_is_written(tmp_path):
    sprites = [s for s in load_all() if s.category == "wisps"]
    build.contact_sheet(sprites, tmp_path / "sheets" / "wisps.png")
    assert Image.open(tmp_path / "sheets" / "wisps.png").width > 64


def test_no_third_party_images_in_art():
    images = [p for p in ART.rglob("*") if p.suffix.lower() in {".png", ".webp", ".gif", ".jpg", ".jpeg"}]
    tracked = subprocess.run(["git", "ls-files", "art"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    for p in images + [ROOT / t for t in tracked]:
        low = str(p.relative_to(ROOT)).lower()
        assert "raven" not in low and "joi3" not in low, p
    # git-ignored locals and outputs
    for rel in ("art/local.toml", "art/out/x.png"):
        r = subprocess.run(["git", "check-ignore", "-q", rel], cwd=ROOT)
        assert r.returncode == 0, f"{rel} must be git-ignored"
