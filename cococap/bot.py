from pydis_core import BotBase
from logging import getLogger

from cococap import exts, logs
from cococap.models import UserDocument, PartyDocument
from cococap.constants import URI

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

log = getLogger('bot')


class StartupError(Exception):
    """Exception class for startup errors."""

    def __init__(self, base: Exception):
        super().__init__()
        self.exception = base


class Bot(BotBase):
    async def setup_hook(self) -> None:
        await super().setup_hook()
        
        # Logging setup
        logs.setup()
        
        # Database setup
        client = AsyncIOMotorClient(URI)
        await init_beanie(database=client.discordbot, document_models=[UserDocument, PartyDocument])
        
        await self.load_extensions(exts)
        
        fmt = "%m-%d-%Y %H:%M:%S"
        print(f"Ran at: {datetime.strftime(datetime.now(), fmt)}")
