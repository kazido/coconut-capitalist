import discord
from logging import getLogger

from discord.ext import commands, tasks
from pydis_core import BotBase, StartupError

from cococap import emojis, exts, glyphs
from cococap.constants import DATABASE_PATH, DISABLED_EXTENSIONS
from cococap.db import Database, close_database, init_database
from cococap.services import activity
from cococap.ui.nav import stop_all_tickers
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

        # The bot's own (application) emojis, looked up by name everywhere else.
        await emojis.refresh(self)
        glyphs.install()  # plain unicode emoji in any message become our own icons on the way out

        self.idle_sweep.start()

        # Load our own extensions using function from discord.py's own bot
        await self.load_extensions(exts)

    async def on_interaction(self, interaction: discord.Interaction) -> None:
        """Every command and button press says the player is around (see services/activity)."""
        try:
            await activity.touch(interaction.user.id)
        except Exception:  # noqa: BLE001 - tracking activity must never break a command
            log.exception("Could not record activity")

    @tasks.loop(minutes=10)
    async def idle_sweep(self) -> None:
        """Take players who have gone quiet out of their parties."""
        try:
            for k in await activity.sweep():
                log.info("Removed idle user %s from party %s%s", k.user_id, k.party_id, " (disbanded)" if k.disbanded else "")
        except Exception:  # noqa: BLE001
            log.exception("Idle party sweep failed")

    async def load_extension(self, name: str, *, package: str | None = None) -> None:
        if name in DISABLED_EXTENSIONS:
            log.info("Skipping disabled extension %s (not yet ported)", name)
            return
        try:
            await super().load_extension(name, package=package)
        except commands.NoEntryPointError:
            # Helper modules that live under exts/ (helpers under exts/) have no setup().
            log.info("%s has no setup(); treating it as a helper module, not an extension", name)

    async def close(self) -> None:
        self.idle_sweep.cancel()
        await stop_all_tickers()  # panels refreshing themselves must stop before the database goes away
        await super().close()
        await close_database()
