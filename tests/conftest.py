import os

os.environ["COCOCAP_NO_LOCAL_CONFIG"] = "1"  # the tests run on the shared numbers, never a personal configs/local/ overlay

import pytest
import pytest_asyncio
from sqlalchemy import update

from cococap.ui.nav import stop_all_tickers
from cococap.db import Database, close_database, get_database, init_database
from cococap.db.tables import UserRow
from cococap.registry import get_registry

# The tests are written against the shipped economy numbers. Tuning these in configs/economy.toml (a quick idle limit to try the party
# sweep, no starting luckbucks, ...) must not break them, so they run with these values whatever the file says.
_economy = get_registry().economy
for _name, _value in (("starting_luckbucks", 100), ("weekly_luckbucks", 100), ("party_idle_hours", 24)):
    _economy.__dict__[_name] = _value


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
def _no_leftover_invites():
    """Pending party invites live in memory: never let one test's invite show up in the next."""
    from cococap.services import party_invites

    party_invites.clear()
    yield
    party_invites.clear()


@pytest.fixture(autouse=True)
def _no_leftover_mines():
    """Who is in a mine lives in memory (the magnet cannot be fed down there): never let one test's run block the next."""
    from cococap.services import mining

    mining._LIVE_RUNS.clear()
    yield
    mining._LIVE_RUNS.clear()


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


def with_signature_drops(reg):
    """A copy of the registry whose tree species have two signature drops each (the shipped data has none, since the old species
    materials were removed). Lets the tests keep covering the mechanic: birch drops clay/sapphire, every other species coal/emerald."""
    import copy

    from cococap.registry.models import SpeciesDrop

    pairs = {"birch": ("material_clay", "material_sapphire")}
    species = []
    for sp in reg.foraging.species:
        common, rare = pairs.get(sp.id, ("material_coal", "material_emerald"))
        drops = [SpeciesDrop(item=common, rate=0.3, min=1, max=2), SpeciesDrop(item=rare, rate=0.02, min=1, max=1)]
        species.append(sp.model_copy(update={"drops": drops}))
    other = copy.copy(reg)
    other.foraging = reg.foraging.model_copy(update={"species": species})
    return other
