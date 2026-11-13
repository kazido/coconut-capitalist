"""The mining buttons: they must only translate clicks into service calls and redraw."""

from collections import Counter
from random import Random
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cococap.exts.skills import mining as cog
from cococap.registry import get_registry
from cococap.services import mining as svc
from cococap.user import User
from tests.test_mining import fixed_mine


def fake_interaction(user_id=1):
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id, name="tester", display_name="tester", display_avatar="http://x/a.png"),
        response=SimpleNamespace(edit_message=AsyncMock(), send_message=AsyncMock(), defer=AsyncMock(), send_modal=AsyncMock()),
        original_response=AsyncMock(),
    )


def last_embed(interaction):
    return interaction.response.edit_message.call_args.kwargs["embed"]


async def make_view(session=None, user_id=1):
    user = await User.get(user_id)
    inter = fake_interaction(user_id)
    return cog.MineView(inter, user, session or fixed_mine(), xp=0), inter, user


def test_grid_rendering_shows_cursor_wyrmholes_and_revealed_cells():
    mine = fixed_mine(wyrmholes={(3, 0)})
    mine.mine_row()  # reveals row 0, col 2
    text = cog.render_grid(mine)
    header, *rows = text.split("\n")
    assert header.count(cog.CURSOR) == 1 and len(rows) == 5
    assert cog.WYRMHOLE in rows[3] and cog.CELL_EMPTY not in rows[0]
    assert rows[0].count(cog.CELL) == 4  # the other four cells in row 0 are still unmined


async def test_move_buttons_only_move_the_cursor(db):
    view, inter, _ = await make_view()
    await view.right.callback(inter)
    assert view.session.cursors == [3]
    await view.left.callback(inter)
    await view.left.callback(inter)
    assert view.session.cursors == [1]
    assert last_embed(inter).fields  # redrawn


async def test_dig_button_banks_loot_and_advances_a_row(db):
    view, inter, user = await make_view()
    await view.dig.callback(inter)
    assert await user.items() == {"copper_ore": 1} and view.session.row == 1


async def test_finishing_the_mine_awards_xp_and_offers_to_leave_or_continue(db, monkeypatch):
    monkeypatch.setattr(svc, "scarab_appears", lambda *a: False)
    view, inter, user = await make_view()
    for _ in range(5):
        await view.dig.callback(inter)
    assert (await user.skill("mining")).xp == 10
    assert isinstance(inter.response.edit_message.call_args.kwargs["view"], cog.FinishedView)
    assert await user.item_quantity("copper_ore") == 13


async def test_walking_into_a_wyrmhole_hands_over_to_the_wyrmhole_screen(db):
    view, inter, user = await make_view(fixed_mine(wyrmholes={(0, 2)}))
    await view.dig.callback(inter)
    assert isinstance(inter.response.edit_message.call_args.kwargs["view"], cog.WyrmholeView)
    assert await user.items() == {}  # nothing banked from the aborted row


async def test_wyrmhole_dig_banks_one_node(db):
    user = await User.get(1)
    inter = fake_interaction()
    view = cog.WyrmholeView(inter, user, svc.generate_wyrmhole(get_registry().mining, Random(3)), xp=0)
    await view.dig.callback(inter)
    assert sum((await user.items()).values()) > 0 and view.hole.finished


async def test_scarab_right_and_wrong_answers(db):
    user = await User.get(1)
    parent, inter, _ = await make_view()
    challenge = svc.ScarabChallenge("lantern", "ternlan", 30)

    right = cog.ScarabView(inter, user, challenge, parent)
    await right.resolve(inter, "LANTERN")
    assert await user.item_quantity("scarab_bomb") > 0
    assert isinstance(inter.response.edit_message.call_args.kwargs["view"], cog.FinishedView)
    bombs = await user.item_quantity("scarab_bomb")
    await right.resolve(inter, "lantern")  # a second submit can't pay twice
    assert await user.item_quantity("scarab_bomb") == bombs

    wrong = cog.ScarabView(inter, user, challenge, parent)
    await wrong.resolve(inter, "nope")
    assert await user.item_quantity("scarab_bomb") == bombs


async def test_reactor_claim_and_insert_buttons(db):
    user = await User.get(1)
    inter = fake_interaction()
    await user.add_xp("mining", User.level_to_xp(10) + 1)
    await user.add_item("sanity_gemstone", 1)
    view = await cog.ReactorView.build(inter, user)
    await view.insert.callback(inter)
    assert (await user.skill("mining")).reactor.core_1.gem_id == "sanity_gemstone"
    assert "Inserted" in last_embed(inter).footer.text
    await view.claim.callback(inter)  # nothing waiting yet; must not crash
    assert "Claimed 0" in last_embed(inter).footer.text


async def test_mine_command_shows_menu_for_a_new_player(db):
    inter = fake_interaction()
    command = cog.MiningCog()
    await command.mine.callback(command, inter)
    sent = inter.response.send_message.call_args.kwargs
    assert isinstance(sent["view"], cog.MineMenu) and sent["embed"].title.startswith("Level")


def test_loot_lines_bold_rare_items():
    text = cog.loot_lines(Counter({"copper_ore": 3, "implosion_gemstone": 1}))
    assert "+3 Copper Ore" in text and "**Implosion Gem**" in text
