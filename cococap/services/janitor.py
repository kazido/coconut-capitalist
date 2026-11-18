"""Deciding which of the bot's old messages to delete. No Discord objects here, so the rules are easy to test."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "janitor.toml"
BULK_LIMIT_DAYS = 14  # Discord refuses to bulk delete anything older than this


@dataclass(frozen=True)
class JanitorConfig:
    enabled: bool
    channel_ids: tuple[int, ...]
    interval_minutes: int
    menu_max_age_minutes: float
    other_max_age_minutes: float
    delete_delay_seconds: float


def load_config(path: Path = CONFIG_PATH) -> JanitorConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return JanitorConfig(
        enabled=bool(raw["enabled"]),
        channel_ids=tuple(int(i) for i in raw["channel_ids"]),
        interval_minutes=int(raw["interval_minutes"]),
        menu_max_age_minutes=float(raw["menu_max_age_minutes"]),
        other_max_age_minutes=float(raw["other_max_age_minutes"]),
        delete_delay_seconds=float(raw["delete_delay_seconds"]),
    )


def should_delete(*, age_minutes: float, from_bot: bool, is_menu: bool, cfg: JanitorConfig) -> bool:
    """Only the bot's own messages, and only once they are older than their limit (menus sooner than other messages)."""
    if not from_bot:
        return False
    limit = cfg.menu_max_age_minutes if is_menu else cfg.other_max_age_minutes
    return age_minutes >= limit


def idle_minutes(created_at, edited_at, now) -> float:
    """Minutes since a message was last touched: its last edit if it has one, else when it was posted. A play menu that is edited on every
    click keeps being touched, so a menu somebody is still using is never swept; an abandoned one goes quiet and is."""
    last = edited_at or created_at
    return (now - last).total_seconds() / 60


def can_bulk(age_days: float) -> bool:
    return age_days < BULK_LIMIT_DAYS - 0.01  # a small margin so a message cannot cross the line mid-request
