import discord

import random
import asyncio

from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice

from cococap.user import User
from utils.custom_embeds import CustomEmbed


class Minigames(commands.Cog, name="Minigames"):
    """A collection of fun minigames. They might even give some bits as rewards!"""

    def __init__(self):
        # Initialize any shared state or resources for the cog here.
        # Example: self.active_games = {} to track ongoing minigames per user.
        super().__init__()

    async def cog_load(self):
        # Called when the cog is loaded.
        # Idea: Set up background tasks, initialize resources, or log cog loading.
        pass

    async def cog_unload(self):
        # Called when the cog is unloaded.
        # Idea: Clean up resources, cancel background tasks, or save state.
        pass

    async def interaction_check(self, interaction):
        # Called before any app command in this cog is invoked.
        # Idea: Prevent users from running multiple minigames at once, check permissions, etc.
        return await super().interaction_check(interaction)

    async def cog_app_command_error(self, interaction, error):
        # Called when an error occurs in an app command in this cog.
        # Idea: Log errors, send user-friendly error messages, or handle specific exceptions.
        return await super().cog_app_command_error(interaction, error)

    async def bot_check(self, ctx):
        # Called before any command in this cog is invoked.
        # Idea: Restrict commands to certain channels, check user roles, etc.
        return await super().bot_check(ctx)

    async def cog_before_invoke(self, ctx):
        # Runs before every command in this cog.
        # Idea: Load user data, set up context variables, or log command usage.
        user = await User(ctx.author.id).load()
        ctx.interaction.extras.update(user=user)
        return await super().cog_before_invoke(ctx)

    async def cog_after_invoke(self, ctx):
        # Runs after every command in this cog.
        # Idea: Save user data, clean up temporary state, or log command completion.
        return await super().cog_after_invoke(ctx)

    async def cog_command_error(self, ctx, error):
        # Called when an error occurs in a command in this cog.
        # Idea: Send error messages to users, log errors, or handle specific exceptions.
        pass

    async def cog_check(self, ctx):
        # Called before any command in this cog is invoked.
        # Idea: Add custom checks, such as cooldowns or user eligibility.
        return True
