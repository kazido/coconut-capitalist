"""Player news: notices (pop up once each, then archived on More -> News -> Messages) and the changelog. No discord here.

Seen notice ids live in the player's settings (`Settings.seen_notices`), so a notice shows once per player across restarts.
"""

from cococap.registry import get_registry
from cococap.registry.models import ChangelogEntry, Notice
from cococap.user import User

PAGE_CHARS = 1800  # text per Messages/Changelog page: several short entries share a page, a long one gets its own


def unseen(user: User) -> list[Notice]:
    """The notices this player has not had popped up yet, newest first."""
    seen = set(user.settings.seen_notices)
    return [n for n in get_registry().notices if n.id not in seen]


async def mark_seen(user: User, notices: list[Notice]) -> None:
    """Remember these notices as shown. Ids of notices that no longer exist are dropped, so the list never grows past the file."""
    known = {n.id for n in get_registry().notices}
    ids = [i for i in user.settings.seen_notices if i in known]
    ids += [n.id for n in notices if n.id not in ids]
    if ids != user.settings.seen_notices:
        await user.set_setting("seen_notices", ids)


def day(d) -> str:
    return f"{d:%B} {d.day}, {d.year}"


def notice_text(notice: Notice) -> str:
    return f"### {notice.title}\n-# {day(notice.date)}\n{notice.body.strip()}"


def entry_text(entry: ChangelogEntry) -> str:
    star = "⭐ " if entry.major else ""
    return f"### {star}{entry.title}\n-# {day(entry.date)}\n{entry.body.strip()}"


def pages(blocks: list[str], per_page: int = PAGE_CHARS) -> list[list[str]]:
    """Blocks packed in order onto pages of at most `per_page` characters (a block longer than that gets a page of its own). Always one page."""
    out: list[list[str]] = [[]]
    size = 0
    for block in blocks:
        if out[-1] and size + len(block) > per_page:
            out.append([])
            size = 0
        out[-1].append(block)
        size += len(block)
    return out


def message_pages() -> list[list[str]]:
    return pages([notice_text(n) for n in get_registry().notices])


def changelog_pages() -> list[list[str]]:
    return pages([entry_text(e) for e in get_registry().changelog])
