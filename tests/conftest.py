import pytest_asyncio
from sqlalchemy import update

from cococap.db import Database, close_database, get_database, init_database
from cococap.db.tables import UserRow


@pytest_asyncio.fixture
async def db(tmp_path):
    """A fresh real SQLite database (file in a temp dir) with the production schema."""
    database = await init_database(Database.from_path(tmp_path / "test.db"))
    yield database
    await close_database()


async def set_columns(user, **columns):
    """Test helper: write columns straight into a user's row and refresh the handle."""
    async with get_database().session() as session:
        await session.execute(update(UserRow).where(UserRow.discord_id == user.id).values(**columns))
    await user.refresh()
