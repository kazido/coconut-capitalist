import discord

from pydis_core import BotBase
from logging import getLogger

from cococap import exts, logs
from cococap.models import UserDocument, PartyDocument
from cococap.constants import URI

from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

log = getLogger('bot')


MY_GUILD = discord.Object(id=856915776345866240)

class StartupError(Exception):
    """Exception class for startup errors."""

    def __init__(self, base: Exception):
        super().__init__()
        self.exception = base


class Bot(BotBase):
    async def setup_hook(self) -> None:
        await super().setup_hook()
        
        # Copy the global commands over to my guild TODO: This will need to be changed when global
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)
        
        # Logging setup
        logs.setup()
        
        # Database setup
        client = AsyncIOMotorClient(URI)
        await init_beanie(database=client.discordbot, document_models=[UserDocument, PartyDocument])
        
        # Load our own extensions using function from discord.py's own bot
        await self.load_extensions(exts)
