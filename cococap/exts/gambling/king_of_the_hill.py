import discord

from cococap.constants import DiscordGuilds
from cococap.bot import Bot
from cococap.user import User

from discord.ext import commands
from discord import utils



# King of the Hill related IDs
KOTH_CHANNEL_ID = 859262125390168074
KOTH_ROLE_ID = 895078616063430666


class KingOfTheHill(commands.Cog, name="King of the Hill"):
    """Be the last to send a message in the King of the Hill channel to be the King!"""

    def __init__(self, bot):
        self.bot = bot
    

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return await self.bot.process_commands(message)

        async def update_king():
            koth_role = utils.get(message.guild.roles, id=KOTH_ROLE_ID)
            # Retrieve the guild so we can check everyone's roles
            guild = self.bot.get_guild(DiscordGuilds.PRIMARY_GUILD.value)
            for member in guild.members:
                member: discord.Member
                if member == message.author:
                    return await member.add_roles(koth_role)
                if koth_role in member.roles:
                    await member.remove_roles(koth_role)
                    # TODO: Make the user get bits based on how long they've been the king!
                    # user = User(member.id)
                    # await user.load()
                    # user.inc_purse(amount=message.created_at - message.channel.last_message)
                    

        if message.channel.id == KOTH_CHANNEL_ID:
            await update_king()
            return
        
        
async def setup(bot: Bot):
    await bot.add_cog(KingOfTheHill(bot))
