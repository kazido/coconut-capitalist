from discord import Interaction
from cococap.user import User
from functools import wraps

from cococap.exts.utils.error import AlreadyInGame


def load_user(func):
    @wraps(func)
    async def wrapper(self, interaction: Interaction, *args, **kwargs):
        # PRE FUNCTION OPERATIONS
        # Check if the user is already stored in the 'extras' dictionary
        if "user" not in interaction.extras:
            user = await User(interaction.user.id).load()  # Store user in 'extras'
            if user.get_field("name") != interaction.user.display_name:
                user._document.name = interaction.user.display_name
                user.save()
            interaction.extras["user"] = user

        # Call the wrapped function
        result = await func(self, interaction, *args, **kwargs)

        # POST FUNCTION OPERATIONS

        return result

    return wrapper


def start_game(func):
    @wraps(func)
    async def wrapper(self, interaction: Interaction, *args, **kwargs):
        user: User
        if "user" not in interaction.extras:
            interaction.extras["user"] = await User(interaction.user.id).load()
        user = interaction.extras.get("user")
        print("Setting the user's game status to true. This is cool!")
        if user.get_field("in_game"):
            raise AlreadyInGame(
                "You are already in game somewhere!\n Contact bry if you believe this is an error.",
            )
        await user.in_game(in_game=True)
        try:
            result = await func(self, interaction, *args, **kwargs)
        finally:
            print("End of function! Not sure how we could apply something here...")
        return result

    return wrapper
