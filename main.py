import asyncio
from datetime import datetime
import random
from random import randint
import os
import json
import discord
from discord.ext import commands, tasks
from pytz import timezone

intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix='-', intents=intents, case_insensitive=True, strip_after_prefix=True)
primary_guild = discord.Object(id=856915776345866240)
testing_guild = discord.Object(id=977351545966432306)

with open('./config.json', 'r') as f:
    data = json.load(f)


def owner_perms_check(ctx):
    authorized = [326903703422500866, 730955069201317999]
    return ctx.message.author.id in authorized


@commands.is_owner()
@bot.command(hidden=True)
async def cogcheck(ctx):
    for cog in os.listdir('cogs'):
        if cog.endswith('.py'):
            try:
                await bot.load_extension(f"cogs.{cog[:-3]}")
            except commands.ExtensionAlreadyLoaded:
                await ctx.send(f"{cog} is currently loaded.")
            except commands.ExtensionNotFound:
                await ctx.send(f"{cog} could not be located.")


@commands.is_owner()
@bot.command(hidden=True)
async def sync(ctx):
    synced_commands = []
    treesync = await bot.tree.sync(guild=primary_guild)  # Main guild sync
    for command in treesync:
        synced_commands.append(command.name)
    await ctx.send("synced!\n" + str(synced_commands))


@commands.check(owner_perms_check)
@bot.command(hidden=True, aliases=['rl'])
async def reload(ctx):
    cogs = []
    options = {}
    for cog in os.listdir('cogs'):
        if cog.endswith('.py'):
            if cog.startswith('__init__'):
                pass
            else:
                cogs.append(cog)

    for x in cogs:
        options[x] = discord.SelectOption(label=x, value=x)
    select_options = []
    for x in options.values():
        select_options.append(x)

    class CogSelect(discord.ui.View):
        def __init__(self, *, timeout=180):
            super().__init__(timeout=timeout)

        @discord.ui.select(placeholder="Cog to reload", options=select_options)
        async def selection(self, interaction: discord.Interaction, select: discord.ui.Select):
            if interaction.user != ctx.author:
                return
            await bot.reload_extension(f"cogs.{select.values[0][:-3]}")
            last_cog_name = select.values[0][:-3]
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
        await bot.unload_extension(f"cogs.{cog}")
        await ctx.send(f"{cog} has successfully been unloaded.")
    except commands.ExtensionNotFound:
        await ctx.send(f"{cog} could not be located.")
    except commands.ExtensionNotLoaded:
        await ctx.send(f"{cog} is already unloaded.")


@commands.is_owner()
@bot.command(hidden=True)
async def load(ctx, cog):
    try:
        await bot.load_extension(f"cogs.{cog}")
        await ctx.send(f"{cog} has been successfully loaded.")
    except commands.ExtensionAlreadyLoaded:
        await ctx.send(f"{cog} is already loaded.")
    except commands.ExtensionNotFound:
        await ctx.send(f"{cog} could not be located.")


@bot.event
async def on_ready():
    print("Bot is ready.")
    activity = discord.Game("-help")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    fmt = "%m-%d-%Y %H:%M:%S"  # Put current date into a format and add to bottom of embed
    now_time = datetime.now(timezone('US/Eastern'))
    print(f"-- BOT RAN --\nRan at: {datetime.strftime(now_time, fmt)}")


async def main():
    async def load_extensions():  # Function for loading cogs upon bot.run
        for filename in os.listdir('cogs'):
            if filename.endswith('.py'):
                await bot.load_extension(f'cogs.{filename[:-3]}')

    async with bot:
        await load_extensions()
        discord.utils.setup_logging()
        await bot.start(data["token"])


asyncio.run(main())
