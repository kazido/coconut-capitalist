import discord
from logging import getLogger

from beanie import init_beanie
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from pydis_core import BotBase, StartupError

from cococap import exts
from cococap.constants import DISABLED_EXTENSIONS, URI
from cococap.models.models import PartyDocument, UserDocument
from utils import logs

log = getLogger("bot")

__all__ = ["Bot", "StartupError"]


class Bot(BotBase):
    mongo: AsyncIOMotorClient

    async def setup_hook(self) -> None:
        # Logging first so everything below (including pydis_core) is captured.
        logs.setup()
        await super().setup_hook()

        # Database setup. One client for the whole process; cogs should reuse `bot.mongo`.
        self.mongo = AsyncIOMotorClient(URI, serverSelectionTimeoutMS=10_000)
        try:
            await init_beanie(
                database=self.mongo.discordbot, document_models=[UserDocument, PartyDocument]
            )
        except Exception as e:  # unreachable DB, bad credentials, or an index conflict
            raise StartupError(e) from e

        # Load our own extensions using function from discord.py's own bot
        await self.load_extensions(exts)

    async def load_extension(self, name: str, *, package: str | None = None) -> None:
        if name in DISABLED_EXTENSIONS:
            log.info("Skipping disabled extension %s (not yet ported)", name)
            return
        try:
            await super().load_extension(name, package=package)
        except commands.NoEntryPointError:
            # Helper modules that live under exts/ (e.g. exploration.nodes) have no setup().
            log.info("%s has no setup(); treating it as a helper module, not an extension", name)

    async def close(self) -> None:
        await super().close()
        if getattr(self, "mongo", None) is not None:
            self.mongo.close()
