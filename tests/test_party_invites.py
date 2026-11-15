"""Party invites: one waiting at a time, a minute to answer, shown on the Party page (which refreshes by itself)."""

import time

import pytest

from cococap.errors import CustomError
from cococap.services import party_invites as invites
from cococap.services.party import Party
from tests.test_hub import all_text, buttons, click, hub

T = 1_000_000.0


async def test_an_invite_waits_a_minute_and_then_is_gone(db):
    party = await Party.create(1)
    invite = invites.offer(party, 1, 2, now=T)
    assert invite.expires_at == T + invites.INVITE_SECONDS == T + 60
    assert invites.pending_for(2, now=T + 59) == invite
    assert invites.pending_for(2, now=T + 60) is None  # expired exactly at the minute
    with pytest.raises(CustomError, match="expired"):
        await invites.accept(2, now=T + 61)


async def test_only_one_invite_can_wait_for_a_player_at_a_time(db):
    first = await Party.create(1)
    second = await Party.create(3)
    invites.offer(first, 1, 2, now=T)
    with pytest.raises(CustomError, match="already has an invite"):
        invites.offer(second, 3, 2, now=T + 10)
    invites.offer(second, 3, 2, now=T + 61)  # once the first has expired, a new one is fine
    assert invites.pending_for(2, now=T + 62).party_id == second.party_id
    invites.offer(first, 1, 4, now=T + 62)  # and a different player can be invited meanwhile


async def test_accepting_joins_the_party_and_uses_the_invite_up(db):
    party = await Party.create(1)
    invites.offer(party, 1, 2, now=T)
    joined = await invites.accept(2, now=T + 5)
    assert joined.party_id == party.party_id and (await Party.for_user(2)).party_id == party.party_id
    assert invites.pending_for(2, now=T + 6) is None


async def test_a_failed_join_still_uses_the_invite_up_and_a_gone_party_says_so(db):
    party = await Party.create(1)
    invites.offer(party, 1, 2, now=T)
    await Party.create(2)  # they made their own party meanwhile
    with pytest.raises(CustomError, match="already in a party"):
        await invites.accept(2, now=T + 1)
    assert invites.pending_for(2, now=T + 2) is None
    invites.offer(party, 1, 3, now=T)
    await party.delete()
    with pytest.raises(CustomError, match="disbanded"):
        await invites.accept(3, now=T + 1)


async def test_declining_drops_the_invite(db):
    party = await Party.create(1)
    invites.offer(party, 1, 2, now=T)
    assert invites.decline(2, now=T + 1) is True and invites.pending_for(2, now=T + 2) is None
    assert invites.decline(2, now=T + 3) is False


# ---- the Party page ----------------------------------------------------------------------------------------------
async def test_a_waiting_invite_is_on_the_party_page_when_it_opens(db):
    party = await Party.create(2)
    invites.offer(party, 2, 1, now=time.time())
    nav, inter = await hub("party", user_id=1)
    assert "Party invite" in all_text(nav) and "expires" in all_text(nav)
    assert {"Join", "Decline"} <= {b.label for b in buttons(nav)}
    await click(nav, inter, "Join")
    assert (await Party.for_user(1)).party_id == party.party_id and "Party invite" not in all_text(nav)


async def test_declining_on_the_page_removes_the_invite(db):
    party = await Party.create(2)
    invites.offer(party, 2, 1, now=time.time())
    nav, inter = await hub("party", user_id=1)
    await click(nav, inter, "Decline")
    assert await Party.for_user(1) is None and "Party invite" not in all_text(nav) and "Create party" in {b.label for b in buttons(nav)}


async def test_an_expired_invite_is_not_shown_and_the_page_refreshes_itself_to_catch_new_ones(db):
    party = await Party.create(2)
    invites.offer(party, 2, 1, now=time.time() - 120)
    nav, _ = await hub("party", user_id=1)
    assert "Party invite" not in all_text(nav)
    assert nav.screen.refresh_every and nav.screen.refresh_every <= 10  # so an invite sent while the page is open appears
    invites.offer(party, 2, 1, now=time.time())
    await nav.screen.nav._render()  # what the timer does
    assert "Party invite" in all_text(nav)


async def test_a_stale_page_button_cannot_join_after_the_invite_expired(db):
    party = await Party.create(2)
    invites.offer(party, 2, 1, now=time.time())
    nav, inter = await hub("party", user_id=1)
    invites._pending.clear()  # (it expired while the page was on screen)
    await click(nav, inter, "Join")
    assert await Party.for_user(1) is None and "expired" in all_text(nav)


async def test_a_second_invite_is_refused_while_one_waits_and_nothing_is_posted_in_the_chat(db):
    from types import SimpleNamespace

    party = await Party.create(1)
    nav, inter = await hub("party")
    invite = next(c for c in nav.walk_children() if hasattr(c, "_values") and c.__class__.__name__ == "UserSelect")
    invite._values = [SimpleNamespace(id=2, bot=False)]
    inter.response.send_message.reset_mock()
    await invite.callback(inter)
    assert invites.pending_for(2).party_id == party.party_id
    inter.response.send_message.assert_not_called()
    with pytest.raises(CustomError, match="already has an invite"):
        await invite.callback(inter)


def test_the_old_chat_invite_message_is_gone():
    import importlib.util

    assert importlib.util.find_spec("cococap.ui.party_invite") is None
