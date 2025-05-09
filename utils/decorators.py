from discord import Interaction, app_commands
from cococap.user import User
from functools import wraps

from cococap.exts.utils.error import AlreadyInGame


def load_user(func):
    @wraps(func)
    async def wrapper(self, i: Interaction, *args, **kwargs):
        # PRE FUNCTION OPERATIONS
        # Check if the user is already stored in the 'extras' dictionary
        if "user" not in i.extras:
            i.extras["user"] = await User(i.user.id).load()  # Store user in 'extras'

        # Call the wrapped function
        result = await func(self, i, *args, **kwargs)

        # POST FUNCTION OPERATIONS

        return result

    return wrapper


def start_game(func):
    @wraps(func)
    async def wrapper(self, i: Interaction, *args, **kwargs):
        # PRE FUNC
        user: User = i.extras.get("user")
        print("Setting the user's game status to true. This is cool!")
        await user.update_game(True)

        result = await func(self, i, *args, **kwargs)

        print("Set the user's game to false! We did it!")
        await user.update_game(False)

        return result

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
