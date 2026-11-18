from datetime import datetime, timedelta, timezone

from cococap.services.janitor import JanitorConfig, can_bulk, idle_minutes, load_config, should_delete

CFG = JanitorConfig(True, (1,), 5, 30, 180, 0.1)


def test_config_loads_and_has_channels():
    cfg = load_config()
    assert cfg.channel_ids and cfg.menu_max_age_minutes < cfg.other_max_age_minutes


def test_never_deletes_other_authors():
    assert not should_delete(age_minutes=10_000, from_bot=False, is_menu=True, cfg=CFG)


def test_menu_limit_is_shorter_than_other_limit():
    assert should_delete(age_minutes=31, from_bot=True, is_menu=True, cfg=CFG)
    assert not should_delete(age_minutes=31, from_bot=True, is_menu=False, cfg=CFG)
    assert should_delete(age_minutes=181, from_bot=True, is_menu=False, cfg=CFG)
    assert not should_delete(age_minutes=29, from_bot=True, is_menu=True, cfg=CFG)


def test_bulk_limit():
    assert can_bulk(1) and not can_bulk(14) and not can_bulk(30)


def test_a_recently_edited_menu_counts_as_just_touched():
    now = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    posted = now - timedelta(minutes=120)
    assert idle_minutes(posted, None, now) == 120  # never edited: its age
    assert idle_minutes(posted, now - timedelta(minutes=2), now) == 2  # edited 2 minutes ago: still in use
    # the sweep rule on top of it: that menu survives, an abandoned one (last edit long ago) goes
    assert not should_delete(age_minutes=idle_minutes(posted, now - timedelta(minutes=2), now), from_bot=True, is_menu=True, cfg=CFG)
    assert should_delete(age_minutes=idle_minutes(posted, now - timedelta(minutes=90), now), from_bot=True, is_menu=True, cfg=CFG)
