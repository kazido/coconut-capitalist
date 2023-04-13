import asyncio
from datetime import datetime
import os
import json

# discord imports
import discord
from discord.ext import commands

# file imports
import exts
import constants
from utils._extensions import walk_extensions

exts_dir_path = exts.__path__[0]

intents = discord.Intents.all()
intents.message_content = True
intents.presences = False
intents.dm_typing = False
intents.dm_reactions = False
intents.invites = False
intents.webhooks = False
intents.integrations = False

bot = commands.Bot(
    guild_id=constants.PRIMARY_GUILD,
    command_prefix=commands.when_mentioned_or(constants.BOT_PREFIX),
    activity=discord.Game(name=f"Commands: {constants.BOT_PREFIX}help"),
    case_insensitive=True,
    max_messages=10_000,
    allowed_mentions=discord.AllowedMentions(everyone=False),
    intents=intents,
    strip_after_prefix=True
)
bot.remove_command('help')

@commands.is_owner()
@bot.command(hidden=True, aliases=["ch"])
async def cogs(ctx):
    for dirpath, _, files in os.walk(exts_dir_path):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                dirname = dirpath.split(os.path.sep)[-1]
                print(dirname)
                try:
                    if dirname == 'exts':
                        ext_path = f"{dirname}.{file[:-3]}"
                    else:
                        ext_path = f"exts.{dirname}.{file[:-3]}"
                    await bot.load_extension(name=ext_path)
                except commands.ExtensionAlreadyLoaded:
                    await ctx.send(f"{file[:-3]} is currently loaded.")
                except commands.ExtensionNotFound:
                    await ctx.send(f"{file[:-3]} could not be located.")


@commands.is_owner()
@bot.command(hidden=True)
async def sync(ctx):
    # Main guild sync
    treesync = await bot.tree.sync(guild=constants.PRIMARY_GUILD)
    embed = discord.Embed(title="Synced!", description="",
                          color=discord.Color.blurple())
    for command in treesync:
        embed.description += command.name + ", "
    await ctx.send(embed=embed)


@commands.is_owner()
@bot.command(hidden=True, aliases=['r'])
async def reload(ctx):
    extensions = []
    select_options = {}
    for extension in os.listdir(path=exts_dir_path):
        if extension.endswith('.py'):
            if extension.startswith('__init__'):
                pass
            else:
                extensions.append(extension)

    for x in extensions:
        select_options[x] = discord.SelectOption(label=x, value=x)

    class CogSelect(discord.ui.View):
        def __init__(self, *, timeout=180):
            super().__init__(timeout=timeout)

        @discord.ui.select(placeholder="Cog to Reload", options=select_options.values())
        async def selection(self, interaction: discord.Interaction, select: discord.ui.Select):
            if interaction.user != ctx.author:
                return
            await bot.reload_extension(f"exts.{select.values[0][:-3]}")
            await interaction.response.edit_message(
                content=f"{select.values[0][:-3]} has successfully been reloaded.",
                view=None)
            await asyncio.sleep(0.6)
            await ctx.message.delete()
            await select_message.delete()

    select_message = await ctx.send("Which cog would you like to reload?", view=CogSelect())


@commands.is_owner()
@bot.command(hidden=True)
async def unload(ctx, cog):
    try:
        await bot.unload_extension(f"exts.{cog}")
        await ctx.send(f"{cog} has successfully been unloaded.")
    except commands.ExtensionNotFound:
        await ctx.send(f"{cog} could not be located.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"{cog} is already unloaded.")


@commands.is_owner()
@bot.command(hidden=True)
async def load(ctx, cog):
    try:
        await bot.load_extension(f"exts.{cog}")
        await ctx.send(f"{cog} has been successfully loaded.")
    except commands.ExtensionAlreadyLoaded:
        await ctx.send(f"{cog} is already loaded.")
    except commands.ExtensionNotFound:
        await ctx.send(f"{cog} could not be located.")


@bot.event
async def on_ready():
    fmt = "%m-%d-%Y %H:%M:%S"  # Put current date into a format and add to bottom of embed
    print(f"-- BOT RAN --\nRan at: {datetime.strftime(datetime.now(), fmt)}")
    print("Bot is ready.")


async def load_extensions():  # Function for loading cogs upon bot.run
    # if constants.data['DEBUG']:  # REMOVE THIS LINE
    #     return
    for filename in os.listdir(path=exts_dir_path):
        if filename.endswith('.py') and filename != '__init__.py':
            await bot.load_extension(f'exts.{filename[:-3]}')


async def main():
    async with bot:
        await load_extensions()  # Loads cogs on bot startup
        discord.utils.setup_logging()  # 2.1 Logging feature
        # Starts bot using token
        await bot.start(constants.TOKEN, reconnect=True)


if __name__ == '__main__':
    asyncio.run(main())
