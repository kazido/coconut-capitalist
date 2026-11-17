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


def test_the_material_cull_refunds_the_removed_items_at_their_sell_price(tmp_path):
    """Migration 0008: whoever held a removed material gets its sell price per item in bits, and the stack is deleted."""
    import sqlite3

    from cococap.db.migrate import upgrade_sync

    url = f"sqlite:///{tmp_path / 'old.db'}"
    upgrade_sync(url, "0007")
    con = sqlite3.connect(tmp_path / "old.db")
    # every required column gets a filler (the old schema has no database defaults), then the purse
    cols = [(r[1], r[2]) for r in con.execute("PRAGMA table_info(users)") if r[3] and r[4] is None]
    for uid, purse in ((1, 1000), (2, 5)):
        values = {name: (uid if name == "discord_id" else purse if name == "purse" else "x" if "CHAR" in kind.upper() or kind.upper() == "TEXT" else 0) for name, kind in cols}
        con.execute(f"INSERT INTO users ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", list(values.values()))
    con.executemany(
        "INSERT INTO user_items (user_id, item_id, quantity) VALUES (?, ?, ?)",
        [(1, "pine_resin", 3), (1, "golden_pollen", 2), (1, "hardwood", 7), (2, "copper_ore", 4)],
    )
    con.commit()
    con.close()
    upgrade_sync(url)
    con = sqlite3.connect(tmp_path / "old.db")
    purses = dict(con.execute("SELECT discord_id, purse FROM users"))
    items = set(con.execute("SELECT user_id, item_id FROM user_items"))
    assert purses == {1: 1000 + 3 * 3500 + 2 * 50000, 2: 5}
    assert items == {(1, "hardwood"), (2, "copper_ore")}
