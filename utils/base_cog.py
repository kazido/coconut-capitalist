from discord.ext import commands
from cococap.user import User


class BaseCog(commands.Cog):
    async def interaction_check(self, interaction):
        """Globally load the user and attach to interaction.extras for all cogs inheriting BaseCog."""
        user = await User(interaction.user.id).load()
        interaction.extras.update(user=user)
        return await super().interaction_check(interaction)
