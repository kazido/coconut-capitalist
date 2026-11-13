"""Alembic environment: schema changes are versioned in migrations/versions/.

    alembic revision --autogenerate -m "describe the change"   # after editing cococap/db/tables.py
    alembic upgrade head                                       # also done automatically at bot startup
"""

from alembic import context
from sqlalchemy import create_engine

from cococap.constants import DATABASE_PATH
from cococap.db.tables import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # An explicit URL (set by cococap.db.migrate / tests) wins over the configured database file.
    return config.get_main_option("sqlalchemy.url") or f"sqlite:///{DATABASE_PATH}"


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite can't ALTER most things in place
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations_online()
