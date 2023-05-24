from pydis_core import BotBase
from src.utils.extensions import walk_extensions
from discord.utils import setup_logging

from logging import getLogger
from src import exts

log = getLogger('bot')


class StartupError(Exception):
    """Exception class for startup errors."""

    def __init__(self, base: Exception):
        super().__init__()
        self.exception = base


class Bot(BotBase):
    async def setup_hook(self) -> None:
        await super().setup_hook()
        
        setup_logging()  # 2.1 Logging feature  
        print("Attempting to load extensions...")
        await self.load_extensions(exts)
        print("Finished loading extensions.")
        print("Printing all extensions:", self.all_extensions)
        

    # async def load_extensions(self, module):
    #     """Function for loading extensions recursively"""
    #     extensions = walk_extensions(module)
    #     for extension in extensions:
    #         await self.load_extension(extension)
