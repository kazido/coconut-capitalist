import discord

from pydis_core import BotBase
from logging import getLogger

from cococap import exts
from cococap.models import UserDocument, PartyDocument
from cococap.constants import URI
from cococap.persistent import PersistentView

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from utils import logs

log = getLogger("bot")


MY_GUILD = discord.Object(id=856915776345866240)


class StartupError(Exception):
    """Exception class for startup errors."""

    def __init__(self, base: Exception):
        super().__init__()
        self.exception = base


class Bot(BotBase):
    async def setup_hook(self) -> None:
        await super().setup_hook()
        self.add_view(PersistentView(), message_id=1371094892805361674)

        # Logging setup
        logs.setup()

        # Database setup
        client = AsyncIOMotorClient(URI)
        await init_beanie(database=client.discordbot, document_models=[UserDocument, PartyDocument])

        # Load our own extensions using function from discord.py's own bot
        await self.load_extensions(exts)
