import asyncio
import traceback
import sys
import discord

from discord.ext import commands
from discord.ext.commands import Cog
from discord import app_commands

from cococap.bot import Bot
from utils.decorators import AlreadyInGame


class ErrorHandler(Cog):
    """Handles errors emitted from commands."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_app_command_error

    @Cog.listener()
    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Listener for handling all slash command related errors"""
        if isinstance(error, app_commands.CommandOnCooldown):
            error_embed = discord.Embed(title=error, color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed)
            await asyncio.sleep(2)
            await interaction.delete_original_response()

        elif isinstance(error, AlreadyInGame):
            error_embed = discord.Embed(title=error, color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed)
            await asyncio.sleep(2)
            await interaction.delete_original_response()

        else:  # If it's a regular error, send the normal traceback
            error_embed = discord.Embed(title=error, color=discord.Color.dark_gray())
            await interaction.response.send_message(embed=error_embed)
            await interaction.delete_original_response()
            print(
                "Ignoring exception in [SLASH] command {}:".format(
                    interaction.command.qualified_name
                ),
                file=sys.stderr,
            )
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await interaction.response.send_message(
                "```Ignoring exception in [SLASH] command {}```:".format(
                    interaction.command.qualified_name
                ),
                file=sys.stderr,
            )

    @Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Listener for handling all prefix command related errors"""
        if isinstance(error, commands.CommandNotFound):
            return

        else:
            print("Ignoring exception in [PREFIX] command {}:".format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


async def setup(bot: Bot) -> None:
    """Load the ErrorHandler cog."""
    await bot.add_cog(ErrorHandler(bot))
