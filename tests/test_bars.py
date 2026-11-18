"""Coloured pixel-art bars (hp/wear green-yellow-red by amount, progress green, meter blue) and their plain fallback."""

import pytest

from cococap import emojis
from cococap.ui.components import BAR_COLOURS, bar, health_colour


class E:
    def __init__(self, name, id):
        self.name, self.id = name, id

    def __str__(self):
        return f"<:{self.name}:{self.id}>"


@pytest.fixture
def loaded():
    names = [f"ui_bar_{c}_{p}" for c in ("green", "yellow", "red", "blue", "empty") for p in ("left", "mid", "right")]
    emojis.load([E(n, i + 1) for i, n in enumerate(names)])
    yield
    emojis.load([])


def parts(text):
    return [chunk.split(":")[0] for chunk in text.split("<:")[1:]]


def test_a_half_full_hp_bar_is_yellow_then_dark(loaded):
    got = parts(bar(0.5, 4, "hp"))
    assert got == ["ui_bar_yellow_left", "ui_bar_yellow_mid", "ui_bar_yellow_mid", "ui_bar_empty_mid", "ui_bar_empty_mid", "ui_bar_empty_right"]


@pytest.mark.parametrize("fraction,colour", [(1, "green"), (0.76, "green"), (0.75, "yellow"), (0.25, "yellow"), (0.24, "red"), (0.1, "red")])
@pytest.mark.parametrize("kind", ["hp", "wear"])
def test_health_bars_pick_their_colour_from_what_is_left(loaded, kind, fraction, colour):
    assert health_colour(fraction) == colour
    assert f"ui_bar_{colour}_mid" in bar(fraction, 8, kind)


def test_the_ends_follow_empty_and_full(loaded):
    assert parts(bar(0, 3, "wear"))[0] == "ui_bar_empty_left" and parts(bar(0, 3, "wear"))[-1] == "ui_bar_empty_right"
    assert parts(bar(1, 3, "wear"))[-1] == "ui_bar_green_right"


@pytest.mark.parametrize("kind,colour", BAR_COLOURS.items())
def test_each_kind_has_its_own_colour(loaded, kind, colour):
    assert f"ui_bar_{colour}_" in bar(0.7, 5, kind)
    assert len(set(BAR_COLOURS.values())) == 2  # goal bars green, meters blue (hp/wear follow health_colour)


def test_without_the_emojis_it_is_the_plain_text_bar():
    emojis.load([])
    assert bar(0.5, 4, "hp") == "▰▰▱▱" == bar(0.5, 4)
