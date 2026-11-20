"""Apply Alembic migrations (the bot does this at startup)."""

import asyncio
import sqlite3
import time
from pathlib import Path

from alembic import command
from alembic.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _config(sync_url: str) -> Config:
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", sync_url.replace("+aiosqlite", ""))
    return cfg


def _backup_before_upgrade(url: str) -> None:
    """Copy the live database into backups/ before a migration changes it (sqlite's backup API, so WAL data is included)."""
    path = Path(url.split("///", 1)[-1])
    if not path.is_file() or path.stat().st_size == 0:
        return
    target = path.parent / "backups" / f"{path.stem}.pre-migrate-{time.strftime('%Y%m%d-%H%M%S')}.db"
    target.parent.mkdir(exist_ok=True)
    src, dst = sqlite3.connect(path), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _pending(url: str, revision: str) -> bool:
    """True when the database is not yet at `revision` (a brand-new file has nothing to lose, `_backup_before_upgrade` skips it)."""
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    cfg = _config(url)
    target = ScriptDirectory.from_config(cfg).get_revision(revision).revision if revision != "head" else ScriptDirectory.from_config(cfg).get_current_head()
    engine = create_engine(cfg.get_main_option("sqlalchemy.url"))
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision() != target
    finally:
        engine.dispose()


def upgrade_sync(url: str, revision: str = "head") -> None:
    if _pending(url, revision):
        _backup_before_upgrade(url)
    command.upgrade(_config(url), revision)


async def upgrade(url: str, revision: str = "head") -> None:
    # Alembic is synchronous: keep it off the event loop.
    await asyncio.to_thread(upgrade_sync, url, revision)
