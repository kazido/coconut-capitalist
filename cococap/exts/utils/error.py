import traceback
import sys

from discord import Interaction
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

    def __init__(self):
        self.bot.tree.on_error = self.on_app_command_error
        self.embed = ErrorEmbed()

    # APP/SLASH COMMAND ERRORS
    @commands.Cog.listener()
    async def on_app_command_error(self, i: Interaction, e: AppCommandError):
        if isinstance(e, CheckFailure):
            self.embed.description = e.args[0]
        else:
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
            self.embed.description = "Error! Check logs!"
        return await i.response.send_message(embed=self.embed)

    # REGULAR COMMAND ERRORS
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        if isinstance(e, commands.CommandNotFound):
            self.embed.description = f"I couldn't find that command. Typo?"
            return await ctx.send(embed=self.embed)
        else:
            print("Ignoring exception in [PREFIX] command {}:".format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)


async def setup(bot) -> None:
    await bot.add_cog(ErrorHandler(bot))
