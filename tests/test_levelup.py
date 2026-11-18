from cococap.ui import levelup
from cococap.user import User


def test_message_names_the_skill_the_level_and_the_next_goal():
    xp = User.level_to_xp(12)
    text = levelup.message("mining", 12, xp)
    assert "Mining" in text and "level 12" in text and "to level 13" in text


def test_notification_removes_itself_after_a_few_seconds():
    assert 3 <= levelup.LIFETIME <= 15


def test_every_skill_with_an_icon_is_watched():
    assert set(levelup.SKILLS) == {"mining", "fishing", "foraging", "farming", "combat"}


async def test_a_click_that_levels_you_up_sends_the_notification(db, monkeypatch):
    from cococap.services import foraging
    from tests.test_hub import chop, click, freeze_time, hub, with_axe

    monkeypatch.setattr(levelup, "SETTLE", 0)
    freeze_time(monkeypatch)
    user = await with_axe()
    nav, inter = await hub("forage")

    def near_level_up(skill):
        skill.xp = User.level_to_xp(User.xp_to_level(skill.xp) + 1) - 1

    await user.update_skill("foraging", near_level_up)
    await click(nav, inter, "Chop a tree")
    nav.screen.tree = foraging.Tree(1, 1, 1)
    await chop(nav, inter)
    await levelup.flush(user.id)
    assert inter.followup.send.await_count == 1


async def test_a_burst_of_level_ups_is_announced_once_at_the_final_level(db, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr(levelup, "SETTLE", 0.3)
    user = await User.get(1)
    seen = await levelup.snapshot(user)
    inter = MagicMock(followup=MagicMock(send=AsyncMock()))
    for bump in (1, 3, 6):  # three clicks, each a higher level, before the timer fires
        await user.update_skill("mining", lambda s, n=bump: setattr(s, "xp", User.level_to_xp(seen["mining"] + n)))
        await levelup.check(inter, user, seen)
    await levelup.flush(user.id)
    assert inter.followup.send.await_count == 1
    assert f"level {seen['mining'] + 6}" in inter.followup.send.await_args.args[0]
