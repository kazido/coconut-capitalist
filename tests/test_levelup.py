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
