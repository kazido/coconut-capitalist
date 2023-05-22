import asyncio
import os
import discord
from typing import TYPE_CHECKING

from pydis_core.utils import apply_monkey_patches

if TYPE_CHECKING:
    from discord.ext.commands import Bot

# On Windows, the selector event loop is required for aiodns.
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

apply_monkey_patches()

instance: "Bot" = None  # Global Bot instance.
