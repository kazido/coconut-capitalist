"""Farming fields: each of the 14 fields opens one crop, and the seed shop only sells seeds of fields you have reached."""

import pytest

from cococap.registry import get_registry
from cococap.services import areas, community, farming
from cococap.services.shop import ShopError, buy
from cococap.user import User
from tests.conftest import set_columns

REG = get_registry()
SEEDS = REG.farming.field_seeds
LEVELS = REG.areas.location_levels


async def go_to(user, area_index, level):
    await community.update(areas._key(user.id), areas._DEFAULT, lambda d: d.update(current=area_index, highest=area_index))
    await user.update_skill("farming", lambda s: setattr(s, "xp", User.level_to_xp(level + 1)))
    await set_columns(user, purse=10**12)


def test_every_field_opens_a_different_buyable_or_dropped_seed():
    assert len(SEEDS) == len(REG.locations["farming"]) == len(set(SEEDS))
    assert all(REG.item(s).seed for s in SEEDS)


def test_every_crop_has_a_field():
    crops = {i.seed.grows_into for i in REG.items.values() if i.seed}
    assert crops == {REG.item(s).seed.grows_into for s in SEEDS}


def test_fields_run_from_cheap_crops_to_dear_ones():
    sells = [REG.item(REG.item(s).seed.grows_into).sell_price for s in SEEDS]
    assert sells == sorted(sells)


async def test_new_player_can_only_buy_the_first_fields_seed(db):
    user = await User.get(1)
    await set_columns(user, purse=10**12)
    locked = await farming.locked_seeds(user)
    assert SEEDS[0] not in locked and SEEDS[1] in locked
    await buy(user, SEEDS[0], 1)
    with pytest.raises(ShopError, match="Reach"):
        await buy(user, SEEDS[1], 1)


async def test_level_alone_is_not_enough_you_must_have_reached_the_area(db):
    user = await User.get(1)
    await go_to(user, 0, 50)
    assert await areas.reached_locations(user, "farming") == 2  # Slime Hill holds two fields
    assert SEEDS[2] in await farming.locked_seeds(user)


async def test_a_field_opens_at_its_level_and_stays_open_after_travelling_back(db):
    user = await User.get(1)
    n = SEEDS.index("seed_rustroot")  # field 5, first of the Rust Belt
    await go_to(user, n // 2, LEVELS[n] - 1)
    assert "seed_rustroot" in await farming.locked_seeds(user)
    await go_to(user, n // 2, LEVELS[n])
    assert "seed_rustroot" not in await farming.locked_seeds(user)
    await buy(user, "seed_rustroot", 1)
    await community.update(areas._key(user.id), areas._DEFAULT, lambda d: d.update(current=0))  # fly home
    assert "seed_rustroot" not in await farming.locked_seeds(user)


async def test_owned_seeds_still_plant_whatever_the_field(db):
    user = await User.get(1)
    await user.add_item("seed_voidbloom", 1)
    await farming.plant(user, 1, "seed_voidbloom")
