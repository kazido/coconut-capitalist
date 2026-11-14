import pytest
import pytest_asyncio
from sqlalchemy import update

from cococap.ui.nav import stop_all_tickers
from cococap.db import Database, close_database, get_database, init_database
from cococap.db.tables import UserRow


@pytest_asyncio.fixture
async def db(tmp_path):
    """A fresh real SQLite database (file in a temp dir) with the production schema."""
    database = await init_database(Database.from_path(tmp_path / "test.db"))
    yield database
    await stop_all_tickers()  # a panel's self-refresh must not be mid-query when the database closes
    await close_database()


async def set_columns(user, **columns):
    """Test helper: write columns straight into a user's row and refresh the handle."""
    async with get_database().session() as session:
        await session.execute(update(UserRow).where(UserRow.discord_id == user.id).values(**columns))
    await user.refresh()


@pytest.fixture(autouse=True)
def _free_pickaxe(request, monkeypatch):
    """Mining needs a pickaxe. Most mining tests are about the mine itself, so they get a power-1 pickaxe for free,
    unless the player really has one equipped. Mark a test ``bare_hands`` to see the real no-pickaxe behaviour."""
    if request.node.get_closest_marker("bare_hands"):
        return
    from cococap.services import equipment

    real = equipment.equipped_stats

    async def with_default(user, skill, registry=None):
        found = await real(user, skill, registry)
        if found is None and skill == "mining":
            return equipment.EffectiveStats(power=1, requirement=0, stats={"power": 1.0})
        return found

    from cococap.screens import mining as mining_screen
    from cococap.services import mining as mining_service

    monkeypatch.setattr(mining_service, "equipped_stats", with_default)
    monkeypatch.setattr(mining_screen, "equipped_stats", with_default)
