import discord
import traceback
import sys
from discord.ext import commands
from discord.utils import get
from ClassLibrary import *

import datetime


class InGameError(commands.errors.CommandError):
    pass


class Unregistered(commands.errors.CommandError):
    pass


class WrongChannelError(commands.errors.CommandError):
    pass


class PerkNotUnlockedYet(commands.errors.CommandError):
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
        result = (await ctx.bot.dbpets.find_one({"owner_id": ctx.author.id}))
        if result is None:
            return PetNotOwned("You don't own a pet!")
        return True

    return commands.check(predicate)


def in_game():
    async def predicate(ctx):
        try:
            result = (await ctx.bot.db.find_one({"_id": ctx.author.id}))["in_game"]
            if result:
                raise InGameError("Already in a game!")
            return True
        except TypeError:
            await ctx.send("You might not be registered. Use **-register** to get started.")

    return commands.check(predicate)


def registered():
    async def predicate(ctx):
        result = await ctx.bot.db.find_one({"_id": ctx.author.id})
        if result is None:
            raise Unregistered("Not registered!")
        return True

    return commands.check(predicate)


def missing_perks(role_name):
    async def predicate(ctx):
        roles = ["Peasant", "Farmer", "Citizen", "Educated", "Cultured", "Wise", "Expert"]
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        index = roles.index(role_name)
        user_roles = ctx.author.roles
        for x in user_roles:
            if x.name in roles:
                if roles.index(x.name) < index:
                    raise PerkNotUnlockedYet("Doesn't have this perk unlocked!")
        return True

    return commands.check(predicate)


class CommandErrorHandler(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

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
        if payload.message_id == 958549934800511006:
            if str(payload.emoji) == "✅":
                result = await self.bot.db.find_one({"_id": payload.member.id})
                if result is not None:
                    pass
                else:
                    await self.bot.db.insert_one(
                        {"_id": payload.member.id, "money": 0,
                         "in_game": False, "bank": 0, "avatar": "None"})
                    await self.bot.dbfarms.insert_one({"_id": payload.member.id, "almond_seeds": 25, "almonds": 0,
                                                       "cacao_seeds": 3, "cacaos": 0, "coconut_seeds": 5, "coconuts": 0,
                                                       "has_open_farm": False, "plot1": "Empty!", "plot2": "Empty!",
                                                       "plot3": "Empty!"})
                    await self.dbcooldowns.insert_one({"_id": payload.member.id, "daily_used_last": 0.0,
                                                       "worked_last": 0.0})
                    role = discord.utils.get(payload.member.guild.roles, name="Peasant")
                    role_to_remove = discord.utils.get(payload.member.guild.roles, name="Unregistered")
                    await payload.member.remove_roles(role_to_remove)
                    await payload.member.add_roles(role)
                    print(f"{payload.member.name} added into database!")
        elif payload.message_id == 966558439880945745:
            if str(payload.emoji) == "📢":
                role = discord.utils.get(payload.member.guild.roles, id=966557572544995428)
                await payload.member.add_roles(role)
        else:
            pass

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

        elif isinstance(error, InGameError):
            await ctx.send("You're already in a game.")

        elif isinstance(error, WrongChannelError):
            channel = self.bot.get_channel(958198989201764373)
            await ctx.reply(f"This command is only available in {channel.mention}")

        elif isinstance(error, Unregistered):
            channel = self.bot.get_channel(858552463236923432)
            await ctx.send(f"You must be registered to use this command. Register in {channel.mention}")

        elif isinstance(error, PerkNotUnlockedYet):
            embed = discord.Embed(
                title="Permission denied.",
                description="You have not unlocked this perk yet!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

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
