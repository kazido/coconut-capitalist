import asyncio
from datetime import datetime
import os
from pprint import pprint

# discord imports
import discord
from discord.ext import commands
from discord import app_commands
from pydis_core import StartupError

# file imports
import src
from src import exts, constants
from src._bot import Bot
from src.utils.extensions import walk_extensions


async def main():
    intents = discord.Intents.all()
    intents.message_content = True
    intents.presences = False
    intents.dm_typing = False
    intents.dm_reactions = False
    intents.invites = False
    intents.webhooks = False
    intents.integrations = False

    src.instance = commands.Bot(
        guild_id=constants.DiscordGuilds.PRIMARY_GUILD,
        command_prefix=commands.when_mentioned_or(constants.BOT_PREFIX),
        activity=discord.Game(name=f"Commands: {constants.BOT_PREFIX}help"),
        case_insensitive=True,
        max_messages=10_000,
        allowed_mentions=discord.AllowedMentions(everyone=False),
        intents=intents,
        strip_after_prefix=True
    )
    src.instance.remove_command('help')

    async with src.instance as _bot:
        discord.utils.setup_logging()  # 2.1 Logging feature
        await _bot.start(constants.TOKEN, reconnect=True)

asyncio.run(main())
# try:
#     asyncio.run(main())
# except StartupError as e:
#     message = "Unknown Startup Error Occurred."

@commands.is_owner()
@src.instance.command(hidden=True, aliases=["ch"])
async def check_cogs(ctx):
    extensions = walk_extensions(exts)
    for extension in extensions:
        print(extension)
        try:
            await src.load_extension(extension)
        except commands.ExtensionAlreadyLoaded:
            await ctx.send(f"{extension} is already loaded.")
        except commands.ExtensionNotFound:
            await ctx.send(f"{extension} could not be located.")


@commands.is_owner()
@src.command(hidden=True)
async def sync(ctx):
    # Main guild sync
    treesync = await src.tree.sync(guild=constants.PRIMARY_GUILD)
    embed = discord.Embed(title="Synced!", description="",
                          color=discord.Color.blurple())
    for command in treesync:
        embed.description += command.name + ", "
    await ctx.send(embed=embed)


@commands.is_owner()
@src.command(hidden=True, aliases=['r', 'rl'])
async def reload(ctx):
    extensions = []
    select_options = {}

    extensions = walk_extensions(exts)

    for extension_name in extensions:
        select_options[extension_name] = discord.SelectOption(label=extension_name, value=extension_name)

    class CogSelect(discord.ui.View):
        def __init__(self, *, timeout=180):
            super().__init__(timeout=timeout)

        @discord.ui.select(placeholder="Cog to Reload", options=select_options.values())
        async def selection(self, interaction: discord.Interaction, select: discord.ui.Select):
            if interaction.user != ctx.author:
                return
            await src.reload_extension(select.values[0])
            await interaction.response.edit_message(
                content=f"{select.values[0]} has successfully been reloaded.",
                view=None)

    await ctx.send("Which cog would you like to reload?", view=CogSelect())


@commands.is_owner()
@src.command(hidden=True)
async def unload(ctx, cog):
    try:
        await src.unload_extension(f"exts.{cog}")
        await ctx.send(f"{cog} has successfully been unloaded.")
    except commands.ExtensionNotFound:
        await ctx.send(f"{cog} could not be located.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"{cog} is already unloaded.")


@commands.is_owner()
@src.command(hidden=True)
async def load(ctx, extension: str):
    """
    Load a bot extension
    Args:
        name: The module name to unqualify.
    Returns:
        The unqualified module name.
    """
    try:
        await src.load_extension(extension)
        await ctx.send(f"{extension} has been successfully loaded.")
    except commands.ExtensionAlreadyLoaded:
        await ctx.send(f"{extension} is already loaded.")
    except commands.ExtensionNotFound:
        await ctx.send(f"{extension} could not be located.")


@src.event
async def on_ready():
    fmt = "%m-%d-%Y %H:%M:%S"
    print(f"-- BOT READY --\nRan at: {datetime.strftime(datetime.now(), fmt)}")

if __name__ == '__main__':
    asyncio.run(main())
