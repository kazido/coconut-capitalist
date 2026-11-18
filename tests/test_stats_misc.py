"""The Pets, Shipments and Casino stat pages: existing numbers show at once, new counters start from the update and count once per record."""

import pathlib
import random

import pytest

from cococap.constants import BOT_ID
from cococap.models.pethouse import OwnedPet
from cococap.registry import get_registry
from cococap.services import blackjack as bj
from cococap.services import highlow as hl
from cococap.services import pets, shipments as sh
from cococap.services.stats_casino import page as casino_page
from cococap.services.stats_pets import page as pets_page
from cococap.services.stats_shipments import page as shipments_page
from cococap.user import User
from tests.conftest import set_columns
from tests.test_hub import all_text, choose, hub, select_named
from tests.test_shipments import XP10, level_up

SERVICES = pathlib.Path(__file__).resolve().parents[1] / "cococap" / "services"


@pytest.fixture(autouse=True)
def stake_bits(monkeypatch):
    """Bets are placed in purse here, so the casino tests don't depend on the luckbucks setting."""
    monkeypatch.setattr("cococap.constants.CASINO_CURRENCY", "purse")


def rows(page):
    """(label, value) pairs of a stat page, as a dict."""
    return {label: value for _group, lines in page.groups for label, value in lines}


async def with_pet(user, stars=1, xp=0):
    pet_id = next(iter(get_registry().pets))

    def add(house):
        house.pets[pet_id] = OwnedPet(stars=stars, xp=xp)
        house.active = pet_id

    await user.update_pethouse(add)
    return pet_id


# ---- pets ---------------------------------------------------------------------------------------------
async def test_pets_page_shows_the_pethouse_for_an_existing_player_with_no_counters(db):
    user = await User.get(1)
    pet_id = await with_pet(user, xp=500)
    stats = await user.stats()
    assert stats.get("orbs_opened", 0) == 0 and "pet_foods_fed" not in stats  # no counter rows yet
    got = rows(await pets_page(user, stats))
    reg = get_registry()
    assert got["Pets owned"] == 1 and got["Active pet"] == reg.pets[pet_id].name
    assert got["Highest pet level"] >= 1
    assert got["Orbs opened"] == 0 and got["Pet foods fed"] == 0


async def test_one_orb_opened_adds_exactly_one(db):
    user = await User.get(1)
    await user.add_item(pets.ORB, 2)
    await pets.open_orb(user, random.Random(3))
    assert rows(await pets_page(user, await user.stats()))["Orbs opened"] == 1
    await pets.open_orb(user, random.Random(4))
    assert rows(await pets_page(user, await user.stats()))["Orbs opened"] == 2


async def test_feeding_a_pet_adds_the_amount_fed_once(db):
    user = await User.get(1)
    await with_pet(user)
    crop = next(i for i, item in get_registry().items.items() if item.crop)
    await user.add_item(crop, 3)
    await pets.feed(user, crop, 3)
    assert rows(await pets_page(user, await user.stats()))["Pet foods fed"] == 3


# ---- shipments ----------------------------------------------------------------------------------------
async def test_shipments_page_shows_the_old_total_and_the_crates_in_progress(db):
    user = await level_up(await User.get(1), "mining", XP10)
    await user.inc_stat("shipments_shipped", 5)  # an existing player's total, from before the page
    got = rows(await shipments_page(user, await user.stats()))
    assert got["Total crates"] == 5 and got["Mining"] == 0 and got["Total bits paid"] == 0
    assert got["Ready to ship"] == 0 and got["Still filling"] >= 1


async def test_one_shipped_crate_counts_once_per_skill_and_in_bits(db):
    user = await level_up(await User.get(1), "mining", XP10)
    crate = (await sh.mine(user))[0]
    for item, need in crate.need.items():
        await user.add_item(item, need)
    await sh.fill(user, "mining:basic")
    sent = await sh.ship(user, "mining:basic")
    got = rows(await shipments_page(user, await user.stats()))
    assert got["Mining"] == 1 and got["Total crates"] == 1
    assert got["Total bits paid"] == sent.bits and sent.bits > 0


# ---- casino -------------------------------------------------------------------------------------------
async def test_casino_page_shows_the_existing_game_count_for_an_existing_player(db):
    user = await User.get(1)
    await user.inc_stat("highlow_games", 4)
    await user.inc_stat("blackjack_games", 2)
    got = rows(await casino_page(user, await user.stats()))
    assert got["Games played"] == 6
    assert got["Biggest bet"] == 0 and got["Total won"] == 0 and got["Net"] == 0


async def test_one_highlow_win_counts_the_bet_the_win_and_the_net_once(db):
    user = await User.get(1)
    await set_columns(user, purse=1000)
    game = await hl.start(user, "100", random.Random(1))
    game.roll = 9
    await hl.guess(user, game, True)
    assert await hl.cash_out(user, game) == 200
    got = rows(await casino_page(user, await user.stats()))
    assert got["Games played"] == 1 and got["Total wagered"] == 100 and got["Biggest bet"] == 100
    assert got["Total won"] == 100 and got["Total lost"] == 0 and got["Net"] == 100


async def test_a_blackjack_fold_counts_what_was_lost_once(db):
    user = await User.get(1)
    await set_columns(user, purse=1000)
    game = await bj.start(user, "50", random.Random(2))
    await bj.fold(user, game)  # folding gives part of the bet back: only the rest is lost
    lost = 50 - game.payout
    got = rows(await casino_page(user, await user.stats()))
    assert got["Total wagered"] == 50 and got["Total lost"] == lost and got["Net"] == -lost


# ---- the pages render in the Stats tab ----------------------------------------------------------------
@pytest.mark.parametrize("key, label", [("pets", "Pets owned"), ("shipments", "Total bits paid"), ("casino", "Total wagered")])
async def test_each_page_renders_in_the_stats_dropdown(db, key, label):
    nav, inter = await hub("player", tab="stats")
    await choose(nav, inter, select_named(nav, "Pick a page"), key)
    assert label in all_text(nav)


# ---- every new counter is written in the services ----------------------------------------------------
@pytest.mark.parametrize("needle", [
    "orbs_opened", "pet_foods_fed", "shipments_shipped", "shipped_{crate.theme}", "shipment_bits",
    "casino_wagered", "biggest_bet", "casino_won", "casino_lost",
])
def test_each_counter_is_recorded_in_a_service(needle):
    source = "".join(p.read_text(encoding="utf-8") for p in SERVICES.glob("*.py"))
    assert needle in source
