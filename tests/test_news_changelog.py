"""The Changelog pages hold about CHANGES_PER_PAGE changes each, newest first, with nothing lost."""

from cococap.registry import get_registry
from cococap.services import news


def test_changelog_pages_hold_a_few_changes_each_in_order():
    entries = get_registry().changelog
    pages = news.changelog_pages()
    assert all(1 <= len(page) <= news.CHANGES_PER_PAGE for page in pages)
    flat = [block for page in pages for block in page]
    assert flat == [news.entry_text(e) for e in entries]
