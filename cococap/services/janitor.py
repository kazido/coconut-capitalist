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
    idle_minutes: float  # a bot message untouched for this long is swept (the startup pass ignores it: everything goes)
    delete_delay_seconds: float


def load_config(path: Path = CONFIG_PATH) -> JanitorConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return JanitorConfig(
        enabled=bool(raw["enabled"]),
        channel_ids=tuple(int(i) for i in raw["channel_ids"]),
        interval_minutes=int(raw["interval_minutes"]),
        idle_minutes=float(raw["idle_minutes"]),
        delete_delay_seconds=float(raw["delete_delay_seconds"]),
    )


def should_delete(*, idle: float, from_bot: bool, limit: float) -> bool:
    """Only the bot's own messages, and only once nobody has touched them (posted or edited) for `limit` minutes. Limit 0 = every one."""
    return from_bot and idle >= limit


def idle_minutes(created_at, edited_at, now) -> float:
    """Minutes since a message was last touched: its last edit if it has one, else when it was posted. A play menu that is edited on every
    click keeps being touched, so a menu somebody is still using is never swept; an abandoned one goes quiet and is."""
    last = edited_at or created_at
    return (now - last).total_seconds() / 60


def can_bulk(age_days: float) -> bool:
    return age_days < BULK_LIMIT_DAYS - 0.01  # a small margin so a message cannot cross the line mid-request
