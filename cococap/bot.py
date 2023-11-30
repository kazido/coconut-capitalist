from pydis_core import BotBase
from logging import getLogger

from cococap import exts
from cococap.logs import setup

from datetime import datetime

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
        setup()
        
        await self.load_extensions(exts)
        
        fmt = "%m-%d-%Y %H:%M:%S"
        print(f"-- BOT READY --\nRan at: {datetime.strftime(datetime.now(), fmt)}")