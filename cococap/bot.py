import discord
from logging import getLogger

from discord.ext import commands
from pydis_core import BotBase, StartupError

from cococap import exts
from cococap.constants import DATABASE_PATH, DISABLED_EXTENSIONS
from cococap.db import Database, close_database, init_database
from utils import logs

log = getLogger("bot")

__all__ = ["Bot", "StartupError"]


class Bot(BotBase):
    async def setup_hook(self) -> None:
        # Logging first so everything below (including pydis_core) is captured.
        logs.setup()
        await super().setup_hook()

        # Database: a single SQLite file; Alembic creates/updates the tables at startup.
        try:
            await init_database(Database.from_path(DATABASE_PATH), migrate=True)
        except Exception as e:
            raise StartupError(e) from e
        log.info("Using database %s", DATABASE_PATH)

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
        await close_database()
