"""Database engine management.

One ``Database`` per process. SQLite is opened in WAL mode with foreign keys on, and every
transaction starts with ``BEGIN IMMEDIATE`` so concurrent read-modify-write sequences are
serialized by the database (the bot is a single process, so this is cheap and removes a whole
class of race conditions).
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .tables import Base

__all__ = ["Database", "get_database", "init_database", "close_database"]


class Database:
    def __init__(self, url: str):
        self.url = url
        self.engine: AsyncEngine = create_async_engine(url)
        self._sessionmaker = async_sessionmaker(self.engine, expire_on_commit=False)
        self._configure_sqlite(self.engine)

    @staticmethod
    def _configure_sqlite(engine: AsyncEngine) -> None:
        sync_engine = engine.sync_engine

        @event.listens_for(sync_engine, "connect")
        def on_connect(dbapi_connection, _record):
            dbapi_connection.isolation_level = None  # we emit BEGIN ourselves (below)
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        @event.listens_for(sync_engine, "begin")
        def on_begin(connection):
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    @classmethod
    def from_path(cls, path: str | Path) -> "Database":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(f"sqlite+aiosqlite:///{path}")

    async def create_schema(self) -> None:
        """Create any missing tables (idempotent). Schema *changes* go through Alembic."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """A transaction: commits on success, rolls back on any exception."""
        async with self._sessionmaker() as session, session.begin():
            yield session

    async def close(self) -> None:
        await self.engine.dispose()


_database: Database | None = None


def get_database() -> Database:
    if _database is None:
        raise RuntimeError("Database not initialised: call init_database() at startup")
    return _database


async def init_database(db: Database, *, migrate: bool = False) -> Database:
    """Make `db` the process-wide database and bring its schema up to date.

    ``migrate=True`` (production) runs the Alembic migrations; the default creates the tables
    directly, which is what the tests want (a test checks both end up identical).
    """
    global _database
    _database = db
    if migrate:
        from .migrate import upgrade

        await upgrade(db.url)
    else:
        await db.create_schema()
    return db


async def close_database() -> None:
    global _database
    if _database is not None:
        await _database.close()
        _database = None
