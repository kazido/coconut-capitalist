from src.constants import DiscordGuilds
from src.bot import Bot

from discord.ext.commands import Cog
from discord import utils



# King of the Hill related IDs
KOTH_CHANNEL_ID = 859262125390168074
KOTH_ROLE_ID = 895078616063430666


class KingOfTheHill(Cog, name="King of the Hill"):
    """Be the last to send a message in the King of the Hill channel to be the King!"""

    def __init__(self, bot):
        self.bot = bot


    @Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return await self.bot.process_commands(message)

        async def update_king():
            koth_role = utils.get(message.guild.roles, id=KOTH_ROLE_ID)
            # Retrieve the guild so we can check everyone's roles
            guild = self.bot.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
            for user in guild.members:
                if user == message.author:
                    await user.add_roles(koth_role)
                else:
                    if koth_role in user.roles:
                        await user.remove_roles(koth_role)

        if message.channel.id == KOTH_CHANNEL_ID:
            await update_king()
            return
        
        
async def setup(bot: Bot):
    await bot.add_cog(KingOfTheHill(bot))
