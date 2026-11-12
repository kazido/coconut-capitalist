import logging
import traceback

from discord import Interaction
from discord.app_commands import AppCommandError
from discord.ext import commands

from cococap.errors import (  # noqa: F401  (re-exported: cogs import these from here)
    AlreadyInGame,
    ButtonCheckFailure,
    CustomError,
    InvalidAmount,
)
from cococap.user import InsufficientFunds
from utils.custom_embeds import ErrorEmbed

log = logging.getLogger(__name__)

GENERIC_MESSAGE = "Something went wrong on my end. It has been logged."


def build_error_embed(error: Exception) -> ErrorEmbed:
    """Build the embed shown to a user for `error`.

    Only errors we raised on purpose (CustomError, InsufficientFunds, command usage errors) have
    their text shown; anything else gets a generic message so internals never leak into chat.
    """
    embed = ErrorEmbed()
    if isinstance(error, CustomError):
        embed.description = str(error) or GENERIC_MESSAGE
        if error.title:
            embed.title = error.title
        if error.footer:
            embed.set_footer(text=error.footer)
    elif isinstance(error, InsufficientFunds):
        embed.description = "You don't have enough bits for that."
    elif isinstance(error, commands.CommandNotFound):
        embed.description = "I couldn't find that command. Typo?"
    elif isinstance(error, (commands.UserInputError, commands.CheckFailure)):
        embed.description = str(error) or GENERIC_MESSAGE
    else:
        embed.description = GENERIC_MESSAGE
    return embed


def _is_expected(error: Exception) -> bool:
    """Errors that are user mistakes rather than bugs; no traceback needed."""
    return isinstance(
        error,
        (
            CustomError,
            InsufficientFunds,
            commands.CommandNotFound,
            commands.UserInputError,
            commands.CheckFailure,
        ),
    )


class ErrorHandler(commands.Cog):
    """Handles errors emitted from commands."""

    def __init__(self, bot):
        self.bot = bot
        self._original_tree_on_error = bot.tree.on_error
        bot.tree.on_error = self.on_app_command_error

    async def cog_unload(self) -> None:
        self.bot.tree.on_error = self._original_tree_on_error

    async def on_app_command_error(self, i: Interaction, e: AppCommandError):
        original = getattr(e, "original", e)
        name = i.command.qualified_name if i.command else "<unknown>"
        if _is_expected(original):
            log.info("/%s rejected: %s", name, original)
        else:
            log.error("/%s failed", name, exc_info=(type(e), e, e.__traceback__))

        embed = build_error_embed(original)
        try:
            if i.response.is_done():
                await i.followup.send(embed=embed, ephemeral=True)
            else:
                await i.response.send_message(embed=embed, ephemeral=True)
        except Exception:
            log.exception("Could not report an error to the user")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        if getattr(e, "handled", False):  # a cog's own cog_command_error already dealt with it
            return
        original = getattr(e, "original", e)
        if _is_expected(original):
            log.info("%s rejected: %s", ctx.message.content, original)
        else:
            log.error(
                "Prefix command %r failed\n%s",
                ctx.command.qualified_name if ctx.command else ctx.message.content,
                "".join(traceback.format_exception(type(e), e, e.__traceback__)),
            )
        await ctx.send(embed=build_error_embed(original), delete_after=10)


async def setup(bot) -> None:
    await bot.add_cog(ErrorHandler(bot))
