import sys
import traceback

from discord import Interaction, InteractionResponded
from discord.app_commands import AppCommandError
from discord.ext import commands
from utils.custom_embeds import ErrorEmbed


class CustomError(AppCommandError):
    def __init__(self, message, title=None, footer=None):
        super().__init__(message)
        self.title = title
        self.footer = footer


class AlreadyInGame(AppCommandError):
    pass


class InvalidAmount(AppCommandError):
    pass


class ButtonCheckFailure(AppCommandError):
    pass


class ErrorHandler(commands.Cog):
    """Handles errors emitted from commands."""

    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_app_command_error

    # APP/SLASH COMMAND ERRORS
    @commands.Cog.listener()
    async def on_app_command_error(self, i: Interaction, e: AppCommandError):
        error_embed = ErrorEmbed()
        error_embed.description = e.args[0]
        if hasattr(e, "title") and e.title:
            error_embed.title = e.title
        if hasattr(e, "footer") and e.footer:
            error_embed.set_footer(text=e.footer)

        # Print a simple error note to the terminal
        command_name = "/" + i.command.qualified_name
        print(f"{command_name} failed: {e}", file=sys.stderr)
        print("\nWE HAVE AN ISSUE!")
        traceback.print_exception(type(e), e.__traceback__)

        # Write the full traceback to a log file
        with open("logs/app_command_errors.log", "a") as log_file:
            traceback.print_exception(type(e), e, e.__traceback__, file=log_file)

        # Attempt to send the message, if it's already been responded to, followup.
        try:
            return await i.response.send_message(embed=error_embed, delete_after=5)
        except InteractionResponded:
            return await i.followup.send(embed=error_embed)

    # REGULAR COMMAND ERRORS
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        error_embed = ErrorEmbed()
        error_embed.description = e.args[0]
        if hasattr(e, "title") and e.title:
            error_embed.title = e.title
        if hasattr(e, "footer") and e.footer:
            error_embed.set_footer(text=e.footer)

        # Print a simple error note to the terminal
        command_name = ctx.prefix + ctx.command.qualified_name
        print(f"{command_name} failed: {e}", file=sys.stderr)

        if isinstance(e, commands.CommandNotFound):
            error_embed.description = f"I couldn't find that command. Typo?"

        # Write the full traceback to a log file
        with open("logs/command_errors.log", "a") as log_file:
            traceback.print_exception(type(e), e, e.__traceback__, file=log_file)

        # Send a message with error
        return await ctx.send(embed=error_embed, delete_after=5)


async def setup(bot) -> None:
    await bot.add_cog(ErrorHandler(bot))
