"""Player news: notices pop up once per player; the News page (Messages, Changelog) renders and pages."""

from datetime import date

import pytest

from cococap.registry import get_registry
from cococap.registry.models import ChangelogEntry, Notice
from cococap.screens import SCREENS, open_screen
from cococap.services import news
from cococap.user import User
from tests.test_hub import all_text, fake_interaction, find_button, hub


def notice(i: int, body: str = "Something changed.") -> Notice:
    return Notice(id=f"n{i}", date=date(2026, 1, i), title=f"Notice {i}", body=body)


@pytest.fixture
def two_notices(monkeypatch):
    reg = get_registry()
    monkeypatch.setattr(reg, "notices", [notice(2), notice(1)])
    return reg.notices


async def test_a_new_notice_pops_up_once_and_never_again(db, two_notices):
    inter = fake_interaction()
    await open_screen(inter, "home")
    kw = inter.followup.send.await_args.kwargs
    assert inter.followup.send.await_count == 1 and kw["ephemeral"] is True
    assert kw["embed"].title == "Notice 2"  # newest first
    assert (await User.get(1)).settings.seen_notices == ["n2", "n1"]

    again = fake_interaction()
    await open_screen(again, "mining")  # any shortcut opens the hub the same way
    again.followup.send.assert_not_awaited()


async def test_only_the_notice_added_later_pops_up(db, two_notices, monkeypatch):
    await open_screen(fake_interaction(), "home")
    monkeypatch.setattr(get_registry(), "notices", [notice(3), *two_notices])
    inter = fake_interaction()
    await open_screen(inter, "home")
    view = inter.followup.send.await_args.kwargs["view"]
    assert view.notices == [get_registry().notices[0]] and [c.label for c in view.children] == ["Close"]


async def test_several_new_notices_are_one_paged_popup(db, two_notices):
    inter = fake_interaction()
    await open_screen(inter, "home")
    view = inter.followup.send.await_args.kwargs["view"]
    assert view.prev.disabled and not view.next.disabled
    await view.next.callback(inter)
    assert inter.response.edit_message.await_args.kwargs["embed"].title == "Notice 1"
    assert view.next.disabled and not view.prev.disabled


async def test_a_failed_popup_leaves_the_notices_unseen(db, two_notices):
    inter = fake_interaction()
    inter.followup.send.side_effect = RuntimeError("discord down")
    await open_screen(inter, "home")  # the menu still opens
    assert (await User.get(1)).settings.seen_notices == []


def test_shipped_news_files_load():
    reg = get_registry()
    assert reg.notices and reg.changelog
    assert [n.date for n in reg.notices] == sorted((n.date for n in reg.notices), reverse=True)
    assert [e.date for e in reg.changelog] == sorted((e.date for e in reg.changelog), reverse=True)


def test_pages_pack_blocks_in_order_under_the_budget():
    blocks = ["a" * 700, "b" * 700, "c" * 700, "d" * 3000]
    pages = news.pages(blocks, per_page=1500)
    assert pages == [["a" * 700, "b" * 700], ["c" * 700], ["d" * 3000]]
    assert news.pages([]) == [[]]


@pytest.mark.parametrize("tab", list(SCREENS["news"].panes))
async def test_every_news_tab_renders_valid_layout(db, tab, monkeypatch):
    long = "x" * 1400  # max-ish bodies, so the layout check covers a full page
    monkeypatch.setattr(get_registry(), "notices", [notice(i, long) for i in range(5, 0, -1)])
    monkeypatch.setattr(get_registry(), "changelog", [ChangelogEntry(date=date(2026, 1, i), title=f"E{i}", body=long, major=i % 2 == 0)
                                                     for i in range(5, 0, -1)])
    nav, inter = await hub("news", tab=tab)
    nav.to_components()
    assert nav.total_children_count <= 40 and nav.content_length() <= 4000
    assert "E5" in all_text(nav) or "Notice 5" in all_text(nav)  # newest first
    assert find_button(nav, "1/5").disabled  # the page counter is a label, not a button
    next_button = [b for b in nav.walk_children() if getattr(b, "label", None) is None and getattr(b, "emoji", None) and not b.disabled][-1]
    await next_button.callback(inter)
    assert find_button(nav, "2/5") is not None
    nav.to_components()
    assert nav.content_length() <= 4000


async def test_more_page_links_to_news(db):
    nav, inter = await hub("more")
    assert "News" in all_text(nav)
