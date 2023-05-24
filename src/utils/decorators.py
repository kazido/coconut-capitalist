
from discord.ext import commands
from discord.ext.commands import Cog, Context
from discord.ext.commands.errors import CommandError

from src.constants import GamblingChannels
import src.models as models


class OwnsPetCheckFailure(CommandError):
    """Raised when a user attempts to use a command that requires ownership of at least 1 pet"""


def owns_a_pet():

    async def predicate(ctx: Context):
        owns_pet = (models.Pets.get(owner_id=ctx.author.id))

        success = owns_pet

        if not success:
            raise OwnsPetCheckFailure("You don't own a pet!")

        return success

    return commands.check(predicate)


class RegisteredCheckFailure(CommandError):
    """Raised when a user tries to use a command, but is not registered in the bot database"""


def registered():

    async def predicate(ctx: Context):
        result = models.Users.get(id=ctx.author.id)

        if result is None:
            raise RegisteredCheckFailure("Not registered!")

        return True

    return commands.check(predicate)
