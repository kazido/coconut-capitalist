import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from cococap.ui import ConfirmView, OwnedView


def interaction(user_id):
    return SimpleNamespace(
        user=SimpleNamespace(id=user_id),
        response=SimpleNamespace(send_message=AsyncMock(), edit_message=AsyncMock()),
    )


async def test_only_the_owner_may_use_the_view():
    view = OwnedView(SimpleNamespace(id=1))
    assert await view.interaction_check(interaction(1)) is True
    stranger = interaction(2)
    assert await view.interaction_check(stranger) is False
    assert stranger.response.send_message.call_args.kwargs["ephemeral"] is True


async def test_timeout_removes_buttons_from_the_message():
    view = OwnedView(SimpleNamespace(id=1))
    view.message = SimpleNamespace(edit=AsyncMock())
    await view.on_timeout()
    view.message.edit.assert_awaited_with(view=None)


async def test_timeout_without_a_message_is_safe():
    await OwnedView(SimpleNamespace(id=1)).on_timeout()


async def test_confirm_yes_no_and_timeout():
    for button, expected in (("confirm", True), ("cancel", False)):
        first = interaction(1)
        first.response.send_message = AsyncMock()

        async def click(first=first, name=button):
            await asyncio.sleep(0)
            view_obj = first.response.send_message.call_args.kwargs["view"]
            await getattr(view_obj, name).callback(interaction(1))

        result, _ = await asyncio.gather(ConfirmView.ask(first, "sure?"), click())
        assert result is expected

    # No click (a timeout stops the view without setting a value) counts as "no".
    timed_out = interaction(1)

    async def expire():
        await asyncio.sleep(0)
        timed_out.response.send_message.call_args.kwargs["view"].stop()

    result, _ = await asyncio.gather(ConfirmView.ask(timed_out, "sure?"), expire())
    assert result is False
