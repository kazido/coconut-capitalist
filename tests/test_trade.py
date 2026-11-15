"""Gifts: offer, accept, decline; nothing moves until accepted, and nothing moves halfway."""

import asyncio

import pytest

from cococap.services import trade
from cococap.user import User

NOW = 1_800_000_000.0


@pytest.fixture(autouse=True)
def _clean():
    trade.clear()
    yield
    trade.clear()


async def pair(db, ore=10, bits=5000):
    a, b = await User.get(1), await User.get(2)
    await a.add_item("copper_ore", ore)
    await a.add_bits(bits)
    await a.refresh()
    return a, b


async def test_an_offer_moves_nothing_until_it_is_accepted_and_then_moves_everything(db):
    a, b = await pair(db)
    start_a, start_b = a.purse, b.purse
    offer = await trade.offer(a, 2, {"copper_ore": 4}, 500, now=NOW)
    assert trade.pending_for(2, NOW) == offer and trade.sent_by(1, NOW) == offer
    assert await a.item_quantity("copper_ore") == 10 and await b.item_quantity("copper_ore") == 0
    got = await trade.accept(b, NOW + 5)
    assert got == offer and trade.pending_for(2, NOW + 5) is None
    await a.refresh()
    await b.refresh()
    assert await a.item_quantity("copper_ore") == 6 and await b.item_quantity("copper_ore") == 4
    assert a.purse == start_a - 500 and b.purse == start_b + 500
    assert (await a.stats())["gifts_sent"] == 1 and (await b.stats())["gifts_received"] == 1


async def test_pressing_accept_twice_gives_once(db):
    a, b = await pair(db)
    await trade.offer(a, 2, {"copper_ore": 4}, 0, now=NOW)
    results = await asyncio.gather(trade.accept(b, NOW + 1), trade.accept(b, NOW + 1), return_exceptions=True)
    assert sum(isinstance(r, trade.Offer) for r in results) == 1
    assert await b.item_quantity("copper_ore") == 4 and await a.item_quantity("copper_ore") == 6


async def test_declining_withdrawing_and_expiring_move_nothing(db):
    a, b = await pair(db)
    await trade.offer(a, 2, {"copper_ore": 1}, 0, now=NOW)
    assert trade.decline(2, NOW + 1) and trade.pending_for(2, NOW + 1) is None and not trade.decline(2, NOW + 1)
    await trade.offer(a, 2, {"copper_ore": 1}, 0, now=NOW)
    assert trade.withdraw(1, NOW + 1) and trade.pending_for(2, NOW + 1) is None
    await trade.offer(a, 2, {"copper_ore": 1}, 0, now=NOW)
    with pytest.raises(trade.TradeError, match="expired"):
        await trade.accept(b, NOW + trade.OFFER_SECONDS + 1)
    assert await a.item_quantity("copper_ore") == 10 and await b.item_quantity("copper_ore") == 0


async def test_the_rules(db):
    a, b = await pair(db)
    cases = [
        (dict(recipient_id=1, items={"copper_ore": 1}, bits=0), "other"),  # yourself
        (dict(recipient_id=2, items={"copper_ore": 1}, bits=0, is_bot=True), "other"),
        (dict(recipient_id=2, items={}, bits=0), "something"),
        (dict(recipient_id=2, items={}, bits=trade.MIN_BITS - 1), "at least"),
        (dict(recipient_id=2, items={"copper_ore": 11}, bits=0), "do not have"),
        (dict(recipient_id=2, items={}, bits=10**9), "many bits"),
    ]
    for kwargs, message in cases:
        with pytest.raises(trade.TradeError, match=message):
            await trade.offer(a, now=NOW, **kwargs)
    assert trade.pending_for(2, NOW) is None
    await trade.offer(a, 2, {"copper_ore": 1}, 0, now=NOW)
    with pytest.raises(trade.TradeError, match="already has a gift"):
        await trade.offer(a, 2, {"copper_ore": 2}, 0, now=NOW)  # (one at a time)


async def test_tools_cannot_be_sent(db):
    a, _ = await pair(db)
    instance = await a.give_instance("rookiepickaxe")
    assert not trade.can_send("rookiepickaxe") and trade.can_send("copper_ore") and not trade.can_send("not_an_item")
    assert "rookiepickaxe" not in await trade.tradable(a) and instance
    with pytest.raises(trade.TradeError, match="Tools"):
        await trade.offer(a, 2, {"rookiepickaxe": 1}, 0, now=NOW)


async def test_if_the_sender_spent_things_meanwhile_nothing_moves_and_what_was_taken_comes_back(db):
    a, b = await pair(db)
    await trade.offer(a, 2, {"copper_ore": 8}, 3000, now=NOW)
    await a.remove_bits(a.purse - 100)  # spent the bits
    await a.refresh()
    with pytest.raises(trade.TradeError, match="nothing moved"):
        await trade.accept(b, NOW + 1)
    assert await a.item_quantity("copper_ore") == 10 and await b.item_quantity("copper_ore") == 0 and a.purse == 100
    await trade.offer(a, 2, {"copper_ore": 8}, 0, now=NOW + 2)
    await a.remove_item("copper_ore", 5)
    with pytest.raises(trade.TradeError, match="nothing moved"):
        await trade.accept(b, NOW + 3)
    assert await a.item_quantity("copper_ore") == 5 and await b.item_quantity("copper_ore") == 0


async def test_a_gift_of_only_bits_works(db):
    a, b = await pair(db)
    before = b.purse
    await trade.offer(a, 2, {}, 1000, now=NOW)
    await trade.accept(b, NOW + 1)
    await b.refresh()
    assert b.purse == before + 1000


# ---- the Trade page ------------------------------------------------------------------------------------------------------------------------
from tests.test_hub import all_text, buttons, find_button, hub, select_named  # noqa: E402


class Member:
    def __init__(self, id, bot=False):
        self.id, self.bot = id, bot


async def test_the_trade_page_is_reachable_from_inventory_more_and_the_command_exists(db):
    nav, inter = await hub("inventory")
    await find_button(nav, "Trade").callback(inter)
    assert nav.screen.id == "trade"
    nav, _ = await hub("more")
    assert "Trade" in all_text(nav)


async def test_building_and_sending_a_gift_from_the_page_and_accepting_it_on_the_other_side(db):
    a, b = await pair(db)
    nav, inter = await hub("trade")
    screen = nav.screen
    assert find_button(nav, "Send").disabled
    await screen._pick_player(inter, Member(2))
    screen.items["copper_ore"] = 3  # (the quantity pop-up is a Discord modal; the draft it fills is set directly)
    screen.bits = 500
    await screen.refresh(inter)
    assert not find_button(nav, "Send").disabled and "copper" in all_text(nav).lower()
    await find_button(nav, "Send").callback(inter)
    assert trade.pending_for(2) is not None and "Waiting for" in all_text(nav) and not screen.items
    nav2, inter2 = await hub("trade", user_id=2)
    assert "A gift from" in all_text(nav2)
    await find_button(nav2, "Accept").callback(inter2)
    assert await b.item_quantity("copper_ore") == 3 and trade.pending_for(2) is None and "received a gift" in all_text(nav2)


async def test_the_page_refuses_bots_and_yourself_and_can_decline_and_take_back(db):
    a, b = await pair(db)
    nav, inter = await hub("trade")
    await nav.screen._pick_player(inter, Member(9, bot=True))
    assert nav.screen.to is None
    await nav.screen._pick_player(inter, Member(1))
    assert nav.screen.to is None
    await trade.offer(a, 2, {"copper_ore": 1}, 0)
    nav, inter = await hub("trade")
    await find_button(nav, "Take back").callback(inter)
    assert trade.pending_for(2) is None
    await trade.offer(a, 2, {"copper_ore": 1}, 0)
    nav2, inter2 = await hub("trade", user_id=2)
    await find_button(nav2, "Decline").callback(inter2)
    assert trade.pending_for(2) is None and await a.item_quantity("copper_ore") == 10


async def test_the_item_dropdown_lists_ordinary_stacks_but_never_tools(db):
    a, _ = await pair(db)
    await a.give_instance("rookiepickaxe")
    nav, _ = await hub("trade")
    values = {o.value for o in select_named(nav, "Add an item").options}
    assert "copper_ore" in values and "rookiepickaxe" not in values
