import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from cococap.models.models import PartyDocument, UserDocument


@pytest_asyncio.fixture
async def db():
    """A fresh in-memory MongoDB (mongomock) with the real Beanie models and indexes."""
    client = AsyncMongoMockClient()
    await init_beanie(database=client.testdb, document_models=[UserDocument, PartyDocument])
    yield client.testdb
    client.close()
