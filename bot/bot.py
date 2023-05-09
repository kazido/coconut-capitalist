from collections import defaultdict

from pydis_core import BotBase
from utils.extensions import walk_extensions

from logging import getLogger
from bot import exts

log = getLogger('bot')


class StartupError(Exception):
    """Exception class for startup errors."""

    def __init__(self, base: Exception):
        super().__init__()
        self.exception = base


class Bot(BotBase):
    async def setup_hook(self) -> None:
        await super().setup_hook()

        await self.load_extensions(exts)
        print("Printing all extensions:", self.all_extensions)
        

    # async def load_extensions(self, module):
    #     """Function for loading extensions recursively"""
    #     extensions = walk_extensions(module)
    #     for extension in extensions:
    #         await self.load_extension(extension)
