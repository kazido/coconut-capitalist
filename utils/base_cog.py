import discord
from discord.ext import commands
from cococap.user import User


class BaseCog(commands.Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction):
        """Globally load the user and attach to interaction.extras for all cogs inheriting BaseCog.
        This allows us to load a user once and access it anywhere within our command lifecycle."""
        user = await User(interaction.user.id).load()
        interaction.extras.update(user=user)
        return super().interaction_check(interaction)
