from datetime import datetime, timedelta, timezone

from cococap.services.janitor import can_bulk, idle_minutes, load_config, should_delete


def test_config_loads_and_has_channels():
    cfg = load_config()
    assert cfg.channel_ids and cfg.idle_minutes > 0 and cfg.interval_minutes > 0


def test_never_deletes_other_authors():
    assert not should_delete(idle=10_000, from_bot=False, limit=0)


def test_one_limit_for_every_bot_message():
    assert should_delete(idle=6, from_bot=True, limit=5)
    assert not should_delete(idle=4, from_bot=True, limit=5)


def test_the_startup_pass_deletes_every_bot_message():
    assert should_delete(idle=0, from_bot=True, limit=0)  # even one posted a moment ago


def test_bulk_limit():
    assert can_bulk(1) and not can_bulk(14) and not can_bulk(30)


def test_an_edited_menu_counts_as_just_touched():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    posted = now - timedelta(minutes=120)
    assert idle_minutes(posted, None, now) == 120  # never edited: its age
    assert idle_minutes(posted, now - timedelta(minutes=2), now) == 2  # clicked 2 minutes ago: still being played
    assert not should_delete(idle=idle_minutes(posted, now - timedelta(minutes=2), now), from_bot=True, limit=5)
    assert should_delete(idle=idle_minutes(posted, now - timedelta(minutes=9), now), from_bot=True, limit=5)  # abandoned


def test_channels_are_found_by_category_name_and_missing_ids_are_reported():
    from types import SimpleNamespace as NS

    from cococap.exts.ops.janitor import find_channels
    from cococap.services.janitor import JanitorConfig

    play, other = NS(id=1, name="play"), NS(id=2, name="chat")
    guild = NS(categories=[NS(name="🎲︱21 Gamble St.", text_channels=[play]), NS(name="General", text_channels=[other])])
    bot = NS(guilds=[NS(name="x", id=5, categories=guild.categories)], get_channel=lambda cid: None, user="bot")
    cfg = JanitorConfig(True, (999,), ("gamble",), 5, 24, 5, 0.1)
    channels, problems = find_channels(bot, cfg)
    assert channels == [play] and "999" in problems[0] and "can see" in problems[-1]
    none_found, problems = find_channels(NS(guilds=[], get_channel=lambda cid: None, user="bot"), JanitorConfig(True, (), ("gamble",), 5, 24, 5, 0.1))
    assert none_found == [] and "no category" in problems[0]
