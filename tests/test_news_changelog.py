"""The Changelog tab shows only the newest RECENT_CHANGES entries; the rest are paged on Older changes."""

from cococap.registry import get_registry
from cococap.services import news


def test_changelog_tab_shows_only_the_newest_entries():
    entries = get_registry().changelog
    shown = [block for page in news.changelog_pages() for block in page]
    assert shown == [news.entry_text(e) for e in entries[:news.RECENT_CHANGES]]


def test_older_changes_hold_the_rest_with_nothing_lost():
    entries = get_registry().changelog
    older = [block for page in news.older_changelog_pages() for block in page]
    assert older == [news.entry_text(e) for e in entries[news.RECENT_CHANGES:]]
