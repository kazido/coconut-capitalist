"""The Share / Close popup (rare drops, level-ups)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from cococap.registry import get_registry
from cococap.services import odds
from cococap.ui import popup

REG = get_registry()


def finds():
    return popup.sorted_finds({"scroll_keen": 1, "material_iron_wedge": 2}, odds.foraging())


def test_the_embed_lists_each_find_with_quantity_rarity_and_odds():
    embed = popup.rare_embed(finds())
    assert embed.title == "A super rare find!" and len(embed.fields) == 2
    assert "Keen" in embed.fields[0].name and "trees felled" in embed.fields[0].value
    assert "2 ×" in embed.fields[1].name


def inter():
    user = SimpleNamespace(display_name="Pat", display_avatar=SimpleNamespace(url="http://x/a.png"), id=1)
    return MagicMock(user=user, response=MagicMock(edit_message=AsyncMock(), defer=AsyncMock()), delete_original_response=AsyncMock(),
                     followup=MagicMock(send=AsyncMock()), client=MagicMock())


async def test_send_is_ephemeral_with_share_and_close():
    i = inter()
    await popup.send(i, popup.rare_embed(finds()))
    kw = i.followup.send.await_args.kwargs
    assert kw["ephemeral"] is True and [c.label for c in kw["view"].children] == ["Share", "Close"]


async def test_only_the_player_can_press_share_or_close_on_a_public_popup():
    i = inter()
    await popup.send(i, popup.rare_embed(finds()), ephemeral=False)
    view = i.followup.send.await_args.kwargs["view"]
    stranger = inter()
    stranger.user = SimpleNamespace(display_name="Sam", display_avatar=None, id=2)
    stranger.response.send_message = AsyncMock()
    await view.close.callback(stranger)
    await view.share.callback(stranger)
    stranger.delete_original_response.assert_not_awaited()
    assert stranger.response.send_message.await_count == 2
    assert stranger.response.edit_message.await_count == 0
    await view.close.callback(i)  # the player can still close it
    i.delete_original_response.assert_awaited_once()


async def test_a_failing_send_never_raises():
    i = inter()
    i.followup.send.side_effect = RuntimeError("boom")
    await popup.send(i, popup.rare_embed(finds()))


async def test_close_deletes_the_popup():
    i = inter()
    view = popup.PopupView(popup.rare_embed(finds()), i.user)
    await view.close.callback(i)
    i.delete_original_response.assert_awaited_once()


async def test_share_posts_the_embed_publicly_with_the_players_name():
    i = inter()
    view = popup.ShareView(popup.PopupView(popup.rare_embed(finds()), i.user))
    channel = SimpleNamespace(id=5, send=AsyncMock(), mention="<#5>")
    note = await view.post(i, channel)
    embed = channel.send.await_args.kwargs["embed"]
    assert embed.author.name == "Pat" and embed.title == "A super rare find!" and "Shared" in note


async def test_share_in_a_channel_the_bot_cannot_post_in_says_so_politely():
    i = inter()
    view = popup.ShareView(popup.PopupView(popup.rare_embed(finds()), i.user))
    channel = SimpleNamespace(id=5, send=AsyncMock(side_effect=discord.Forbidden(MagicMock(status=403), "no")))
    assert "can't post" in await view.post(i, channel)
