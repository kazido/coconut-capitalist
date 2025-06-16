import functools
import typing as t
import discord
import os
import sys
import importlib
import ast
from enum import Enum

from discord import Colour, Embed
from discord.ext import commands
from discord.ext.commands import Context, group
from logging import getLogger
from discord.ext.commands import Bot

from cococap import exts
from cococap.constants import Emojis, MODERATION_ROLES
from utils.converters import Extension
from utils.pagination import LinePaginator


log = getLogger(__name__)


UNLOAD_BLACKLIST = {f"{exts.__name__}.utils.extensions", f"{exts.__name__}.moderation.modlog"}
BASE_PATH_LEN = len(exts.__name__.split("."))


class Action(Enum):
    """Represents an action to perform on an extension."""

    # Need to be partial otherwise they are considered to be function definitions.
    LOAD = functools.partial(Bot.load_extension)
    UNLOAD = functools.partial(Bot.unload_extension)
    RELOAD = functools.partial(Bot.reload_extension)


class Extensions(commands.Cog):
    """Extension management commands."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.action_in_progress = False
        self.last_reloaded: Extension = None

    @commands.is_owner()
    @commands.command(name="restart", aliases=("rs",))
    async def restart(self, ctx: Context) -> None:
        await ctx.send("Restarting bot...")
        await self.bot.change_presence(status=discord.Status.dnd)
        python = sys.executable
        os.execl(python, python, "-m", "cococap")

    @commands.is_owner()
    @commands.command(name="close")
    async def close(self, ctx: Context) -> None:
        await ctx.send("Bye bye!")
        await self.bot.close()

    @group(
        name="extensions", aliases=("ext", "exts", "c", "cog", "cogs"), invoke_without_command=True
    )
    async def extensions_group(self, ctx: Context) -> None:
        """Load, unload, reload, and list loaded extensions."""
        await ctx.send_help(ctx.command)

    @commands.is_owner()
    @extensions_group.command(name="load", aliases=("l",))
    async def load_command(self, ctx: Context, *extensions: Extension) -> None:
        r"""
        Load extensions given their fully qualified or unqualified names.

        If '\*' or '\*\*' is given as the name, all unloaded extensions will be loaded.
        """  # noqa: W605
        if not extensions:
            await ctx.send_help(ctx.command)
            return

        if "*" in extensions or "**" in extensions:
            extensions = set(self.bot.all_extensions) - set(self.bot.extensions.keys())

        await self.batch_manage(Action.LOAD, ctx, *extensions)

    @commands.is_owner()
    @extensions_group.command(name="unload", aliases=("ul",))
    async def unload_command(self, ctx: Context, *extensions: Extension) -> None:
        r"""
        Unload currently loaded extensions given their fully qualified or unqualified names.

        If '\*' or '\*\*' is given as the name, all loaded extensions will be unloaded.
        """  # noqa: W605
        if not extensions:
            await ctx.send_help(ctx.command)
            return

        blacklisted = "\n".join(UNLOAD_BLACKLIST & set(extensions))

        if blacklisted:
            await ctx.send(
                f":x: The following extension(s) may not be unloaded:```\n{blacklisted}```"
            )
        else:
            if "*" in extensions or "**" in extensions:
                extensions = set(self.bot.extensions.keys()) - UNLOAD_BLACKLIST

            await self.batch_manage(Action.UNLOAD, ctx, *extensions)

    @commands.is_owner()
    @extensions_group.command(name="reload", aliases=("r",), root_aliases=("reload",))
    async def reload_command(self, ctx: Context, *extensions: Extension) -> None:
        r"""
        Reload extensions given their fully qualified or unqualified names.

        If an extension fails to be reloaded, it will be rolled-back to the prior working state.

        If '\*' is given as the name, all currently loaded extensions will be reloaded.
        If '\*\*' is given as the name, all extensions, including unloaded ones, will be reloaded.
        """  # noqa: W605
        if not extensions:
            if self.last_reloaded:
                await self.batch_manage(Action.RELOAD, ctx, *self.last_reloaded)
            else:
                return await ctx.send_help(ctx.command)

        if "**" in extensions:
            extensions = self.bot.all_extensions
        elif "*" in extensions:
            extensions = set(self.bot.extensions.keys()) | set(extensions)
            extensions.remove("*")
        self.last_reloaded = extensions
        await self.batch_manage(Action.RELOAD, ctx, *extensions)

    @commands.is_owner()
    @extensions_group.command(name="list", aliases=("all",))
    async def list_command(self, ctx: Context) -> None:
        """
        Get a list of all extensions, including their loaded status.

        Grey indicates that the extension is unloaded.
        Green indicates that the extension is currently loaded.
        """
        embed = Embed(colour=Colour.og_blurple())
        embed.set_author(name="Extensions List")
        lines = []
        categories = self.group_extension_statuses()
        for category, extensions in sorted(categories.items()):
            # Treat each category as a single line by concatenating everything.
            # This ensures the paginator will not cut off a page in the middle of a category.
            category = category.replace("_", " ").title()
            extensions = "\n".join(sorted(extensions))
            lines.append(f"**{category}**\n{extensions}\n")

        log.debug(f"{ctx.author} requested a list of all cogs. Returning a paginated list.")
        await LinePaginator.paginate_ctx(lines, ctx, embed, scale_to_size=700, empty=False)

    def group_extension_statuses(self) -> t.Mapping[str, str]:
        """Return a mapping of extension names and statuses to their categories."""
        categories = {}
        for ext in self.bot.all_extensions:
            if ext in self.bot.extensions:
                status = Emojis.STATUS_ONLINE.value
            else:
                status = Emojis.STATUS_OFFLINE.value

            path = ext.split(".")
            if len(path) > BASE_PATH_LEN + 1:
                category = " - ".join(path[BASE_PATH_LEN:-1])
            else:
                category = "uncategorised"

            categories.setdefault(category, []).append(f"{status}  {path[-1]}")

        return categories

    async def batch_manage(self, action: Action, ctx: Context, *extensions: str) -> None:
        """
        Apply an action to multiple extensions, giving feedback to the invoker while doing so.

        If only one extension is given, it is deferred to `manage()`.
        """
        if self.action_in_progress:
            await ctx.send(":x: Another action is in progress, please try again later.")
            return

        verb = action.name.lower()

        self.action_in_progress = True
        loading_message = await ctx.send(
            f":hourglass_flowing_sand: {verb} in progress, please wait..."
        )

        if len(extensions) == 1:
            msg, _ = await self.manage(action, extensions[0])
            await loading_message.edit(content=msg)
            self.action_in_progress = False
            return

        failures = {}

        for extension in extensions:
            _, error = await self.manage(action, extension)
            if error:
                failures[extension] = error

        emoji = ":x:" if failures else ":ok_hand:"
        msg = f"{emoji} {len(extensions) - len(failures)} / {len(extensions)} extensions {verb}ed."

        if failures:
            failures = "\n".join(f"{ext}\n    {err}" for ext, err in failures.items())
            msg += f"\nFailures:```\n{failures}```"

        log.debug(f"Batch {verb}ed extensions.")

        await loading_message.edit(content=msg)
        self.action_in_progress = False

    async def manage(self, action: Action, ext: str) -> t.Tuple[str, t.Optional[str]]:
        """Apply an action to an extension and return the status message and any error message."""
        verb = action.name.lower()
        error_msg = None

        try:
            await action.value(self.bot, ext)
        except (commands.ExtensionAlreadyLoaded, commands.ExtensionNotLoaded):
            if action is Action.RELOAD:
                # When reloading, just load the extension if it was not loaded.
                return await self.manage(Action.LOAD, ext)

            msg = f":x: Extension `{ext}` is already {verb}ed."
            log.debug(msg[4:])
        except Exception as e:
            if hasattr(e, "original"):
                e = e.original

            log.exception(f"Extension '{ext}' failed to {verb}.")

            error_msg = f"{e.__class__.__name__}: {e}"
            msg = f":x: Failed to {verb} extension `{ext}`:\n```\n{error_msg}```"
        else:
            msg = f":ok_hand: Extension successfully {verb}ed: `{ext}`."
            log.debug(msg[10:])

        return msg, error_msg

    # This cannot be static (must have a __func__ attribute).
    async def cog_check(self, ctx: Context) -> bool:
        """Only allow moderators and core developers to invoke the commands in this cog."""
        return True
        return await commands.has_any_role(*MODERATION_ROLES).predicate(ctx)

    # This cannot be static (must have a __func__ attribute).
    async def cog_command_error(self, ctx: Context, error: Exception) -> None:
        """Handle errors locally to prevent the error handler cog from interfering when not wanted."""
        # Safely clear the flag on unexpected errors to avoid deadlocks.
        self.action_in_progress = False

        # Handle BadArgument errors locally to prevent the help command from showing.
        if isinstance(error, commands.BadArgument):
            error.handled = True


async def setup(bot: Bot) -> None:
    """Load the Extensions cog."""
    await bot.add_cog(Extensions(bot))
