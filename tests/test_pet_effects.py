"""The Magpie, Mole, Fox, Bee and Raven: pets with small effects that are not xp and never forgive a mistake."""

import pytest

from cococap.models.pethouse import OwnedPet
from cococap.registry import get_registry
from cococap.services import pets, shop
from cococap.user import User
from tests.test_pets import with_pet

REG = get_registry()
RULES = REG.economy.pets

NEW_PETS = {"magpie": "sell_bonus", "mole": "dig_shave", "fox": "rare_reroll", "bee": "extra_harvest", "raven": "payout_bonus"}


def built() -> dict[str, str]:
    """The new pets that exist so far (pet id -> its stat)."""
    return {p: stat for p, stat in NEW_PETS.items() if p in REG.pets and any(b.stat == stat for b in REG.pets[p].bonuses)}


def value(pet_id: str) -> float:
    """What the pet gives at max level with one star, read from the registry."""
    return next(b.value for b in REG.pets[pet_id].bonuses if b.stat == NEW_PETS[pet_id])


def test_the_new_pets_are_small_and_of_a_similar_size():
    for pet_id, stat in built().items():
        assert [b.stat for b in REG.pets[pet_id].bonuses] == [stat], pet_id  # one effect each, and it is not an xp one
        assert not stat.startswith("xp_")
        assert 0.04 <= value(pet_id) <= 0.16, pet_id  # modest at max level...
        assert value(pet_id) * (1 + RULES.star_bonus * (RULES.max_stars - 1)) <= 0.32, pet_id  # ...and still modest at five stars
    values = [value(p) for p in built()]
    assert max(values) / min(values) <= 3  # the five sit in one band


def test_the_new_pets_have_the_rarity_and_skill_they_were_given():
    wanted = {"magpie": (3, "global"), "mole": (3, "mining"), "fox": (4, "global"), "bee": (2, "farming"), "raven": (5, "global")}
    assert {p: (REG.pets[p].rarity, REG.pets[p].skill) for p in built()} == {p: wanted[p] for p in built()}


# ---- Magpie -------------------------------------------------------------------------------------------------------
async def test_a_magpie_makes_every_sale_pay_more_and_more_with_strength(db):
    ore = REG.item("gold_ore")
    plain = await User.get(1)
    await plain.add_item(ore.id, 100)
    base = await shop.sell(plain, ore.id, 100, REG)
    assert base == ore.sell_price * 100

    user = await with_pet("magpie", user_id=2)
    await user.add_item(ore.id, 100)
    paid = await shop.sell(user, ore.id, 100, REG)
    assert paid == round(base * (1 + value("magpie"))) and paid > base

    young = await with_pet("magpie", user_id=3, xp=0)
    star3 = await with_pet("magpie", user_id=4, stars=3)
    assert 0 < await shop.haggle(young, ore, REG) < value("magpie") < await shop.haggle(star3, ore, REG)
    assert await shop.haggle(star3, ore, REG) == pytest.approx(value("magpie") * (1 + 2 * RULES.star_bonus))
