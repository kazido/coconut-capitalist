import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from cococap.db import Database, close_database, init_database
from cococap.db.migrate import upgrade_sync
from cococap.db.tables import Base
from cococap.user import User


def test_migrations_produce_exactly_the_model_schema(tmp_path):
    """If someone edits tables.py without adding a migration, this fails."""
    path = tmp_path / "m.db"
    upgrade_sync(f"sqlite:///{path}")
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"tables.py differs from migrations: {diff}"


def test_migrating_twice_is_a_noop(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    upgrade_sync(url)
    upgrade_sync(url)


async def test_bot_startup_path_uses_migrations_and_enforces_constraints(tmp_path):
    db = await init_database(Database.from_path(tmp_path / "prod.db"), migrate=True)
    try:
        user = await User.get(1)
        await user.add_item("cod", 2)
        assert await user.items() == {"cod": 2}
        async with db.session() as session:
            with pytest.raises(IntegrityError):  # CHECK constraints exist in the migrated schema too
                await session.execute(text("UPDATE users SET purse = -5"))
    finally:
        await close_database()


async def test_wal_mode_and_foreign_keys_are_on(db):
    async with db.session() as session:
        assert (await session.execute(text("PRAGMA journal_mode"))).scalar() == "wal"
        assert (await session.execute(text("PRAGMA foreign_keys"))).scalar() == 1
