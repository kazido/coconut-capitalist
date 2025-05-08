from discord import Interaction, app_commands
from cococap.user import User
from functools import wraps

from cococap.exts.utils.error import AlreadyInGame


def load_user(func):
    @wraps(func)
    async def wrapper(self, i: Interaction, *args, **kwargs):
        # Check if the user is already stored in the 'extras' dictionary
        if "user" not in i.extras:
            i.extras["user"] = await User(i.user.id).load()  # Store user in 'extras'

        # Call the wrapped function
        return await func(self, i, *args, **kwargs)

    return wrapper


def not_in_game_check():
    async def predicate(i: Interaction):
        if "user" not in i.extras:
            i.extras["user"] = await User(i.user.id).load()

        user = i.extras["user"]
        if user.get_field("in_game"):
            raise AlreadyInGame(
                "You are already in game somewhere!\n"
                "Contact admin if you believe this is an error."
            )
        return True

    return app_commands.check(predicate)
