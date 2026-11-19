import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from cococap.screens import open_screen
from cococap.services import community, trade
from cococap.ui import nav as nav_module
from tests.test_hub import fake_interaction


def menu_message(message_id: int, channel_id: int = 5):
    return SimpleNamespace(id=message_id, channel=SimpleNamespace(id=channel_id), edit=AsyncMock(), delete=AsyncMock())


async def open_menu(user_id: int, message):
    inter = fake_interaction(user_id)
    inter.original_response = AsyncMock(return_value=message)
    nav = await open_screen(inter, "home")
    return nav, inter


async def test_opening_a_new_menu_deletes_the_players_old_one(db):
    first, second = menu_message(1), menu_message(2)
    await open_menu(7, first)
    await open_menu(7, second)
    first.delete.assert_awaited()
    second.delete.assert_not_awaited()
    assert (await community.read("menu:7", {}))["message"] == 2  # the id is stored


async def test_a_menu_left_over_from_before_a_restart_is_deleted_by_its_stored_id(db):
    await community.update("menu:8", {}, lambda data: data.update({"channel": 5, "message": 99}))
    nav_module._LIVE.clear()  # (a restart forgets every Navigator)
    deleted = AsyncMock()
    inter = fake_interaction(8)
    inter.original_response = AsyncMock(return_value=menu_message(100))
    inter.client.get_partial_messageable = MagicMock(return_value=SimpleNamespace(get_partial_message=lambda mid: SimpleNamespace(delete=deleted)))
    await open_screen(inter, "home")
    deleted.assert_awaited()


async def test_another_players_menu_is_left_alone(db):
    mine, theirs = menu_message(10), menu_message(11)
    await open_menu(20, mine)
    await open_menu(21, theirs)
    mine.delete.assert_not_awaited()


async def test_a_trade_request_redraws_the_invitees_open_menu(db):
    trade.clear()
    nav, _ = await open_menu(31, menu_message(30))
    nav._push = AsyncMock()
    trade.ask(30, 31)
    await asyncio.sleep(0.05)  # (the listener schedules the redraw)
    nav._push.assert_awaited()
    assert trade.invite_for(31) is not None
