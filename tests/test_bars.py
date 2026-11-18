"""Coloured pixel-art bars (HP red, wear yellow, progress green, meter blue) and their plain fallback."""

import pytest

from cococap import emojis
from cococap.ui.components import BAR_COLOURS, bar


class E:
    def __init__(self, name, id):
        self.name, self.id = name, id

    def __str__(self):
        return f"<:{self.name}:{self.id}>"


@pytest.fixture
def loaded():
    names = [f"ui_bar_{c}_{p}" for c in (*BAR_COLOURS.values(), "empty") for p in ("left", "mid", "right")]
    emojis.load([E(n, i + 1) for i, n in enumerate(names)])
    yield
    emojis.load([])


def parts(text):
    return [chunk.split(":")[0] for chunk in text.split("<:")[1:]]


def test_a_half_full_hp_bar_is_red_then_dark(loaded):
    got = parts(bar(0.5, 4, "hp"))
    assert got == ["ui_bar_red_left", "ui_bar_red_mid", "ui_bar_red_mid", "ui_bar_empty_mid", "ui_bar_empty_mid", "ui_bar_empty_right"]


def test_the_ends_follow_empty_and_full(loaded):
    assert parts(bar(0, 3, "wear"))[0] == "ui_bar_empty_left" and parts(bar(0, 3, "wear"))[-1] == "ui_bar_empty_right"
    assert parts(bar(1, 3, "wear"))[-1] == "ui_bar_yellow_right"


@pytest.mark.parametrize("kind,colour", BAR_COLOURS.items())
def test_each_kind_has_its_own_colour(loaded, kind, colour):
    assert f"ui_bar_{colour}_" in bar(0.7, 5, kind)
    assert len(set(BAR_COLOURS.values())) == 4  # HP and wear (and the others) are all different colours


def test_without_the_emojis_it_is_the_plain_text_bar():
    emojis.load([])
    assert bar(0.5, 4, "hp") == "▰▰▱▱" == bar(0.5, 4)
