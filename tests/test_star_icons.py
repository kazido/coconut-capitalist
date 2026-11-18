from cococap import emojis
from cococap.registry import get_registry
from cococap.screens.pets import stars_text


def test_pet_stars_are_star_icons():
    assert stars_text(3) == emojis.stars(3) and stars_text(0) == ""


def test_a_starred_material_shows_star_icons_and_the_plain_materials_art():
    reg = get_registry()
    base, two = reg.item("material_iron_ore"), reg.item("material_iron_ore_s2")
    assert emojis.stars(2) in two.display and "★" not in two.display
    assert two.emoji == base.emoji  # no art of its own yet: the plain one's
    assert emojis.stars(1) not in base.display
