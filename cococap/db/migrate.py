"""Apply Alembic migrations (the bot does this at startup)."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _config(sync_url: str) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", sync_url.replace("+aiosqlite", ""))
    return cfg


def upgrade_sync(url: str, revision: str = "head") -> None:
    command.upgrade(_config(url), revision)


async def upgrade(url: str, revision: str = "head") -> None:
    # Alembic is synchronous: keep it off the event loop.
    await asyncio.to_thread(upgrade_sync, url, revision)
