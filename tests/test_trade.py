"""Trading: ask, share a window, both add things, both accept; nothing moves until both agree, and nothing moves halfway."""

import asyncio
import time

import pytest
from discord import ui

from cococap.services import trade
from cococap.user import User
from tests.test_hub import all_text, buttons, find_button, hub, select_named

NOW = 1_800_000_000.0


@pytest.fixture(autouse=True)
def _clean():
    trade.clear()
    yield
    trade.clear()


async def pair(db, ore=10, bits=5000):
    a, b = await User.get(1), await User.get(2)
    await a.add_item("material_copper_ore", ore)
    await a.add_bits(bits)
    await a.refresh()
    return a, b


def open_window(now=NOW):
    trade.ask(1, 2, now=now)
    return trade.accept_invite(2, now + 1)


# ---- asking ---------------------------------------------------------------------------------------------------------------------------------
async def test_asking_opens_one_window_both_players_share(db):
    window = open_window()
    assert trade.window_of(1, NOW + 2) is window and trade.window_of(2, NOW + 2) is window
    assert trade.invite_for(2, NOW + 2) is None and window.other(1) == 2


async def test_asking_rules_declining_expiring_and_taking_the_ask_back(db):
    for who, bot in ((1, False), (9, True)):
        with pytest.raises(trade.TradeError, match="other"):
            trade.ask(1, who, is_bot=bot, now=NOW)
    trade.ask(1, 2, now=NOW)
    with pytest.raises(trade.TradeError, match="busy"):
        trade.ask(3, 2, now=NOW + 1)  # one ask at a time
    assert trade.invite_from(1, NOW + 1).recipient_id == 2
    trade.ask(1, 4, now=NOW + 2)  # asking someone else takes the first one back
    assert trade.invite_for(2, NOW + 2) is None and trade.invite_for(4, NOW + 2)
    assert trade.withdraw_ask(1, NOW + 3) and trade.invite_for(4, NOW + 3) is None
    trade.ask(1, 2, now=NOW)
    assert trade.decline(2, NOW + 1) and "declined" in trade.pop_result(1)
    trade.ask(1, 2, now=NOW)
    with pytest.raises(trade.TradeError, match="expired"):
        trade.accept_invite(2, NOW + trade.INVITE_SECONDS + 1)


async def test_you_cannot_be_in_two_trades(db):
    open_window()
    with pytest.raises(trade.TradeError, match="already in a trade"):
        trade.ask(1, 3, now=NOW + 2)
    with pytest.raises(trade.TradeError, match="busy"):
        trade.ask(3, 2, now=NOW + 2)


# ---- the window -----------------------------------------------------------------------------------------------------------------------------
async def test_both_sides_offer_both_accept_and_everything_swaps(db):
    a, b = await pair(db)
    await b.add_item("material_tin_ore", 7)
    await b.add_bits(900)
    await b.refresh()
    start_a, start_b = a.purse, b.purse
    window = open_window()
    await trade.put_items(a, "material_copper_ore", 4, now=NOW + 2)
    await trade.put_bits(a, 500, now=NOW + 2)
    await trade.put_items(b, "material_tin_ore", 7, now=NOW + 3)
    assert await a.item_quantity("material_copper_ore") == 10  # nothing moves while you are still building
    assert await trade.accept(a, window.version, NOW + 4) is False
    assert await trade.accept(b, window.version, NOW + 5) is True
    for user in (a, b):
        await user.refresh()
    assert await a.item_quantity("material_copper_ore") == 6 and await b.item_quantity("material_copper_ore") == 4
    assert await a.item_quantity("material_tin_ore") == 7 and await b.item_quantity("material_tin_ore") == 0
    assert a.purse == start_a - 500 and b.purse == start_b + 500
    assert trade.window_of(1, NOW + 6) is None and trade.window_of(2, NOW + 6) is None
    assert "complete" in trade.pop_result(1) and "complete" in trade.pop_result(2)
    assert (await a.stats())["trades_done"] == 1


async def test_a_change_takes_both_accepts_back_and_an_old_accept_does_not_count(db):
    a, b = await pair(db)
    window = open_window()
    await trade.put_items(a, "material_copper_ore", 2, now=NOW + 2)
    seen = window.version
    await trade.accept(a, seen, NOW + 3)
    assert a.id in window.accepted
    await trade.put_items(a, "material_copper_ore", 9, now=NOW + 4)  # sneaky change after a had agreed...
    assert not window.accepted  # ...everyone has to agree again
    with pytest.raises(trade.TradeError, match="just changed"):
        await trade.accept(b, seen, NOW + 5)  # (b was still looking at the old offer)
    assert await a.item_quantity("material_copper_ore") == 10 and await b.item_quantity("material_copper_ore") == 0
    await trade.accept(b, window.version, NOW + 6)
    trade.unaccept(2, NOW + 7)
    assert window.accepted == set()


async def test_a_gift_is_a_trade_where_one_side_offers_nothing(db):
    a, b = await pair(db)
    window = open_window()
    await trade.put_items(a, "material_copper_ore", 3, now=NOW + 2)
    await trade.accept(a, window.version, NOW + 3)
    assert await trade.accept(b, window.version, NOW + 4) is True
    assert await b.item_quantity("material_copper_ore") == 3


async def test_pressing_accept_at_the_same_moment_trades_once(db):
    a, b = await pair(db)
    window = open_window()
    await trade.put_items(a, "material_copper_ore", 3, now=NOW + 2)
    await trade.accept(a, window.version, NOW + 3)
    results = await asyncio.gather(trade.accept(b, window.version, NOW + 4), trade.accept(b, window.version, NOW + 4), return_exceptions=True)
    assert results.count(True) == 1
    assert await b.item_quantity("material_copper_ore") == 3 and await a.item_quantity("material_copper_ore") == 7


async def test_what_you_may_offer(db):
    a, _ = await pair(db)
    await a.give_instance("tool_pickaxe_rookie")
    open_window()
    with pytest.raises(trade.TradeError, match="Tools"):
        await trade.put_items(a, "tool_pickaxe_rookie", 1, now=NOW + 2)
    with pytest.raises(trade.TradeError, match="that many"):
        await trade.put_items(a, "material_copper_ore", 11, now=NOW + 2)
    with pytest.raises(trade.TradeError, match="at least"):
        await trade.put_bits(a, trade.MIN_BITS - 1, now=NOW + 2)
    with pytest.raises(trade.TradeError, match="that many bits"):
        await trade.put_bits(a, 10**9, now=NOW + 2)
    assert "tool_pickaxe_rookie" not in await trade.tradable(a) and "material_copper_ore" in await trade.tradable(a)
    await trade.put_items(a, "material_copper_ore", 5, now=NOW + 2)
    window = await trade.put_items(a, "material_copper_ore", 0, now=NOW + 3)  # 0 takes it back out
    assert window.offer(1) == ({}, 0)
    with pytest.raises(trade.TradeError, match="not in a trade"):
        await trade.put_items(await User.get(3), "material_copper_ore", 1, now=NOW + 3)


async def test_cancelling_and_timing_out_move_nothing(db):
    a, b = await pair(db)
    open_window()
    await trade.put_items(a, "material_copper_ore", 3, now=NOW + 2)
    assert trade.cancel(2, NOW + 3) and trade.window_of(1, NOW + 3) is None
    assert "off" in trade.pop_result(1) and "off" in trade.pop_result(2)
    assert not trade.cancel(2, NOW + 3)
    open_window(NOW + 10)
    assert trade.window_of(1, NOW + 10 + trade.IDLE_SECONDS + 5) is None
    assert "timed out" in trade.pop_result(1)
    assert await a.item_quantity("material_copper_ore") == 10 and await b.item_quantity("material_copper_ore") == 0


async def test_if_someone_spent_things_meanwhile_nothing_moves_and_what_was_taken_comes_back(db):
    a, b = await pair(db)
    await b.add_item("material_tin_ore", 5)
    window = open_window()
    await trade.put_items(a, "material_copper_ore", 8, now=NOW + 2)
    await trade.put_bits(a, 3000, now=NOW + 2)
    await trade.put_items(b, "material_tin_ore", 5, now=NOW + 2)
    await b.remove_item("material_tin_ore", 5)  # b spends theirs after offering
    await trade.accept(a, window.version, NOW + 3)
    assert await trade.accept(b, window.version, NOW + 4) is True  # (it finished the window, but nothing moved)
    await a.refresh()
    assert "nothing moved" in trade.pop_result(1)
    assert await a.item_quantity("material_copper_ore") == 10 and a.purse == 6000  # (the bits came back too)
    assert await b.item_quantity("material_copper_ore") == 0


# ---- the Trade page -------------------------------------------------------------------------------------------------------------------------
class Member:
    def __init__(self, id, bot=False):
        self.id, self.bot = id, bot


async def test_the_trade_page_is_reachable_from_inventory_and_more(db):
    nav, inter = await hub("inventory")
    await find_button(nav, "Trade").callback(inter)
    assert nav.screen.id == "trade"
    nav, inter = await hub("more")  # Trade lives on the More page (the Home page has no room for it)
    sections = [c for c in nav.walk_children() if isinstance(c, ui.Section) and "Trade" in " ".join(getattr(t, "content", "") for t in c.children)]
    await sections[0].accessory.callback(inter)
    assert nav.screen.id == "trade"


async def test_asking_from_the_page_shows_the_request_to_the_other_player_who_accepts_into_a_shared_window(db):
    a, b = await pair(db)
    nav, inter = await hub("trade")
    await nav.screen._ask(inter, Member(9, bot=True))
    assert trade.invite_for(9) is None
    await nav.screen._ask(inter, Member(2))
    assert "Waiting for" in all_text(nav)
    nav2, inter2 = await hub("trade", user_id=2)
    assert "wants to trade" in all_text(nav2)
    await find_button(nav2, "Accept").callback(inter2)
    assert "Trading with" in all_text(nav2)
    nav, _ = await hub("trade")  # a's page now shows the window too
    assert "Trading with" in all_text(nav) and find_button(nav, "Cancel trade")


async def test_two_players_fill_and_accept_in_the_window_through_the_buttons(db):
    a, b = await pair(db)
    window = open_window()
    await trade.put_items(a, "material_copper_ore", 4, now=NOW + 2)
    nav_a, inter_a = await hub("trade", user_id=1)
    nav_b, inter_b = await hub("trade", user_id=2)
    assert "copper" in all_text(nav_b).lower()  # b sees what a offers
    await find_button(nav_a, "Accept").callback(inter_a)
    assert "accepted" in all_text(nav_a)
    await nav_b.screen.nav.refresh(inter_b)
    assert "accepted" in all_text(nav_b)  # ...and sees a has agreed
    await find_button(nav_b, "Accept").callback(inter_b)
    assert "Trade complete" in all_text(nav_b) and await b.item_quantity("material_copper_ore") == 4
    await nav_a.screen.nav.refresh(inter_a)
    assert "Trade complete" in all_text(nav_a) or trade.window_of(1) is None
    assert window.closed


async def test_the_item_dropdown_lists_ordinary_stacks_but_never_tools_and_cancel_closes_it(db):
    a, _ = await pair(db)
    await a.give_instance("tool_pickaxe_rookie")
    open_window(time.time())
    nav, inter = await hub("trade", user_id=1)
    values = {o.value for o in select_named(nav, "Add an item").options}
    assert "material_copper_ore" in values and "tool_pickaxe_rookie" not in values
    await find_button(nav, "Cancel trade").callback(inter)
    assert trade.window_of(1) is None and "off" in all_text(nav)
