from cococap.ui import levelup
from cococap.user import User


def test_message_names_the_skill_the_level_and_the_next_goal():
    xp = User.level_to_xp(12)
    text = levelup.message("mining", 11, 12, xp)
    assert "Mining" in text and "11 -> 12" in text and "to level 13" in text


def test_notification_removes_itself_after_a_few_seconds():
    assert 3 <= levelup.LIFETIME <= 15


def test_every_skill_with_an_icon_is_watched():
    assert set(levelup.SKILLS) == {"mining", "fishing", "foraging", "farming", "combat"}


async def test_a_click_that_levels_you_up_sends_the_notification(db, monkeypatch):
    from cococap.services import foraging
    from tests.test_hub import chop, click, freeze_time, hub, with_axe

    freeze_time(monkeypatch)
    user = await with_axe()
    nav, inter = await hub("forage")

    def near_level_up(skill):
        skill.xp = User.level_to_xp(User.xp_to_level(skill.xp) + 1) - 1

    await user.update_skill("foraging", near_level_up)
    await click(nav, inter, "Chop a tree")
    nav.screen.tree = foraging.Tree(1, 1, 1)
    await chop(nav, inter)
    assert inter.followup.send.await_count == 1
    assert inter.followup.send.await_args.kwargs["wait"] is True  # (Webhook.send has no delete_after; the message is deleted after sending)


async def test_jumping_several_levels_in_one_click_is_one_notice_old_to_new(db):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    user = await User.get(1)
    seen = await levelup.snapshot(user)
    await user.update_skill("mining", lambda s: setattr(s, "xp", User.level_to_xp(seen["mining"] + 5)))
    sent = SimpleNamespace(delete=AsyncMock())
    inter = MagicMock(followup=MagicMock(send=AsyncMock(return_value=sent)))
    await levelup.check(inter, user, seen)
    assert inter.followup.send.await_count == 1
    new = (await levelup.snapshot(user))["mining"]
    assert new > seen["mining"] + 1  # a real multi-level jump
    assert f"{seen['mining']} -> {new}" in inter.followup.send.await_args.args[0]
    sent.delete.assert_awaited_once_with(delay=levelup.LIFETIME)
