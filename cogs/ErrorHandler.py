import asyncio
import traceback
import sys
import discord
from discord.ext import commands
from discord import app_commands
import mymodels as mm
from discord.utils import get
from ClassLibrary2 import RequestUser

import datetime


class Unregistered(commands.errors.CommandError):
    pass


class WrongChannelError(commands.errors.CommandError):
    pass


class PetNotOwned(commands.errors.CommandError):
    pass


def in_wrong_channel():
    async def predicate(ctx):
        if ctx.channel.id != 958198989201764373:
            raise WrongChannelError("Not in the right channel!")

    return commands.check(predicate)


def own_pet():
    async def predicate(ctx):
        result = (mm.Pets.get(owner_id=ctx.author.id))
        if result is None:
            return PetNotOwned("You don't own a pet!")
        return True

    return commands.check(predicate)


def registered():
    async def predicate(ctx):
        result = mm.Users.get(id=ctx.author.id)
        if result is None:
            raise Unregistered("Not registered!")
        return True

    return commands.check(predicate)


class CommandErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.on_error = self.on_app_command_error

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        owner = self.bot.get_user(326903703422500866)
        channel = await owner.create_dm()
        await channel.send(f"{member.name} has left the guild and could cause issues in database.\n"
                           f"Their id: {member.id}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return await self.bot.process_commands(message)

        async def king_of_the_hill():
            role = get(message.guild.roles, id=895078616063430666)
            guild = self.bot.get_guild(856915776345866240)
            for user in guild.members:
                if user == message.author:
                    await user.add_roles(role)
                else:
                    if role in user.roles:
                        await user.remove_roles(role)

        if message.channel.id == 859262125390168074:
            await king_of_the_hill()
            return

        if message.content.lower() == 'yey':
            await message.channel.send(":balloon:")

    # When a reaction is added to the message in #assign-roles, it adds the user to the database
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.message_id == 966558439880945745:
            if str(payload.emoji) == "📢":
                role = discord.utils.get(payload.member.guild.roles, id=966557572544995428)
                await payload.member.add_roles(role)
        else:
            pass

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            error_embed = discord.Embed(
                title=error,
                color=discord.Color.red())
            await interaction.response.send_message(embed=error_embed)
            await asyncio.sleep(2)
            await interaction.delete_original_response()

        else:  # If it's a regular error, send the normal traceback
            print('Ignoring exception in command {}:'.format(interaction.command.name), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.DisabledCommand):
            await ctx.send(f'{ctx.command} has been disabled.')

        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title=ctx.command.name,
                description=ctx.command.description,
                colour=discord.Color.greyple())
            embed.add_field(name="How to use this command", value=ctx.command.brief)
            embed.set_footer(text="For more help, use the -help command")
            await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandOnCooldown):
            cool_down = str(datetime.timedelta(seconds=round(error.retry_after)))
            embed = discord.Embed(title=f"This command is still on cool down: {cool_down}!",
                                  color=discord.Colour.dark_red())
            await ctx.send(embed=embed)

        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send("*Oops!*")

        elif isinstance(error, commands.BadArgument):
            if ctx.command.qualified_name == 'tag list':
                await ctx.send('I could not find that member. Please try again.')

        elif isinstance(error, WrongChannelError):
            channel = self.bot.get_channel(958198989201764373)
            await ctx.reply(f"This command is only available in {channel.mention}")

        elif isinstance(error, Unregistered):
            channel = self.bot.get_channel(858552463236923432)
            await ctx.send(f"You must be registered to use this command. Register in {channel.mention}")

        elif isinstance(error, discord.ext.commands.errors.CheckFailure):
            print(f"User {ctx.author.name} brought up {error} with the command {ctx.command}.")

        else:
            print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

    @commands.command(name='repeat', aliases=['mimic', 'copy'])
    async def do_repeat(self, ctx, *, inp: str):
        """A simple command which repeats your input!
        Parameters
        ------------
        inp: str
            The input you wish to repeat.
        """
        await ctx.send(inp)

    @do_repeat.error
    async def do_repeat_handler(self, ctx, error):
        """A local Error Handler for our command do_repeat.
        This will only listen for errors in do_repeat.
        The global on_command_error will still be invoked after.
        """

        if isinstance(error, commands.MissingRequiredArgument):
            if error.param.name == 'inp':
                await ctx.send("You forgot to give me input to repeat!")


async def setup(bot):
    await bot.add_cog(CommandErrorHandler(bot))
