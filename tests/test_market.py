"""The part market: the Travelling Merchant and the Black Market (services/market.py, screens/shop.py MarketPane).

Numbers come from the registry (configs/market.toml), never hard-coded here.
"""

import pytest

from cococap.errors import GameRuleError
from cococap.registry import get_registry
from cococap.services import community, market
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, choose, click, hub, select_named

REG = get_registry()
MERCHANT = REG.market.merchant
BLACK = REG.market.black_market
NOW = 300 * MERCHANT.refresh_seconds + 10  # well inside one window


@pytest.fixture(autouse=True)
async def _real_db(db):
    yield


async def reach(user: User, area_id: str) -> None:
    """Give the player a ship that has reached this area (the shops open on your furthest area)."""
    index = next(i for i, a in enumerate(REG.areas.areas) if a.id == area_id)
    await community.update(f"ship:{user.id}", {"tier": 0, "current": 0, "highest": 0},
                           lambda d: d.update(highest=index, current=index))


async def rich(purse=10_000_000) -> User:
    user = await User.get(1)
    await set_columns(user, purse=purse)
    return user


def shape(offers):
    return [(o.part_type, o.tier, o.traits, o.price) for o in offers]


async def test_the_same_stock_inside_one_window_and_new_stock_after_it(db):
    user = await rich()
    first = await market.stock(user, "merchant", NOW)
    assert shape(first) == shape(await market.stock(user, "merchant", NOW + 1))
    assert len(first) == MERCHANT.slots
    later = [shape(await market.stock(user, "merchant", NOW + k * MERCHANT.refresh_seconds)) for k in range(1, 6)]
    assert any(s != shape(first) for s in later)


async def test_the_merchant_is_closed_until_rust_belt(db):
    user = await rich()
    assert not await market.unlocked(user, "merchant")
    assert "Rust Belt" in market.unlock_text("merchant")
    with pytest.raises(GameRuleError, match="Rust Belt"):
        await market.buy(user, "merchant", 0, NOW)
    await reach(user, "rust_belt")
    assert await market.unlocked(user, "merchant")


async def test_the_black_market_needs_star_kingdom_and_rolls_rich_parts(db):
    user = await rich()
    await reach(user, "rust_belt")
    assert not await market.unlocked(user, "black_market")
    await reach(user, "star_kingdom")
    assert await market.unlocked(user, "black_market")
    offers = await market.stock(user, "black_market", NOW)
    assert len(offers) == BLACK.slots
    assert all(o.tier >= 4 for o in offers)  # the black market only rolls the rich tiers (weights 0 below 4)


async def test_buying_charges_the_listed_price_and_gives_the_part_as_rolled(db):
    user = await rich()
    await reach(user, "rust_belt")
    offer = (await market.stock(user, "merchant", NOW))[0]
    before = await user.get_bits()
    bought = await market.buy(user, "merchant", 0, NOW)
    assert await user.get_bits() == before - offer.price == before - bought.price
    part = (await user.instances())[-1]
    assert part.template_id == f"part_{offer.part_type}"
    assert int(part.rolled["tier"]) == offer.tier
    assert sorted(part.traits) == sorted(offer.traits)


async def test_a_slot_can_be_bought_only_once_per_restock(db):
    user = await rich()
    await reach(user, "rust_belt")
    await market.buy(user, "merchant", 1, NOW)
    with pytest.raises(GameRuleError, match="already"):
        await market.buy(user, "merchant", 1, NOW)
    assert (await market.stock(user, "merchant", NOW))[1].bought
    assert await market.stock(user, "merchant", NOW + MERCHANT.refresh_seconds)  # the next restock is open again


async def test_too_poor_is_refused_and_nothing_changes(db):
    user = await rich(purse=0)
    await reach(user, "rust_belt")
    with pytest.raises(GameRuleError, match="bits"):
        await market.buy(user, "merchant", 0, NOW)
    assert await user.get_bits() == 0
    assert not (await market.stock(user, "merchant", NOW))[0].bought


async def test_both_market_panes_show_the_offers_and_buy(db):
    user = await rich()
    await reach(user, "rust_belt")
    nav, inter = await hub("shop", tab="merchant")
    assert "Restocks in" in all_text(nav)
    await choose(nav, inter, select_named(nav, "Pick a part"), "2")
    await click(nav, inter, "Buy")
    assert "Bought" in all_text(nav)
    assert (await market.stock(user, "merchant", NOW))[2] is not None
    nav, _ = await hub("shop", tab="black_market")
    assert "closed until you reach Star Kingdom" in all_text(nav)
