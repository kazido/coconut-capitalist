from discord import Interaction, app_commands
from cococap.user import User


class AlreadyInGame(app_commands.CheckFailure):
    pass


def not_in_game_check():
    async def predicate(interaction: Interaction):
        user = await User(interaction.user.id).load()
        if user.get_field("in_game"):
            return False
        return True  # Pass the check

    return app_commands.check(predicate)
