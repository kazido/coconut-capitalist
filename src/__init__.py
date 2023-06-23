import asyncio
import os
import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord.ext.commands import Bot

# On Windows, the selector event loop is required for aiodns.
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


instance: "Bot" = None  # Global Bot instance.
