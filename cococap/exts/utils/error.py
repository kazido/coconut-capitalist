import traceback
import sys

from discord import Interaction, InteractionResponded
from discord.ext import commands
from discord.app_commands import AppCommandError, CheckFailure
from utils.custom_embeds import ErrorEmbed


class AlreadyInGame(CheckFailure):
    pass  # User is trying to play a game while already in one


class InvalidBet(CheckFailure):
    pass  # User makes an invalid bet


class ButtonCheckFailure(CheckFailure):
    pass  # User tries to click button that isn't theirs


class ErrorHandler(commands.Cog):
    """Handles errors emitted from commands."""

    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_app_command_error
        self.error_embed = ErrorEmbed()

    # APP/SLASH COMMAND ERRORS
    @commands.Cog.listener()
    async def on_app_command_error(self, i: Interaction, e: AppCommandError):
        if isinstance(e, CheckFailure):
            self.error_embed.description = e.args[0]
        else:
            # Send default traceback and have user check logs.
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
        # Attempt to send the message, if it's already been responded to, followup.
        try:
            return await i.response.send_message(embed=self.error_embed)
        except InteractionResponded:
            return await i.followup.send(embed=self.error_embed)

    # REGULAR COMMAND ERRORS
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        if isinstance(e, commands.CommandNotFound):
            self.error_embed.description = f"I couldn't find that command. Typo?"
        else:
            print("Ignoring exception in [PREFIX] command {}:".format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
        return await ctx.send(embed=self.error_embed)


async def setup(bot) -> None:
    await bot.add_cog(ErrorHandler(bot))
