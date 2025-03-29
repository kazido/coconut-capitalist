import discord

from cococap.bot import Bot
from cococap.user import User
from discord.ext import commands


# King of the Hill related IDs
KOTH_CHANNEL_ID = 859262125390168074
KOTH_ROLE_ID = 895078616063430666


class KingOfTheHill(commands.Cog, name="King of the Hill"):
    """Be the last to send a message in the King of the Hill channel to be the King!"""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def update_king(message: discord.Message):
        koth_role = message.guild.get_role(KOTH_ROLE_ID)

        # Retrieve the guild so we can check everyone's roles
        guild = message.guild
        for member in guild.members:
            if member == message.author:
                await member.add_roles(koth_role)
            elif koth_role in member.roles:
                await member.remove_roles(koth_role)
            

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.bot.process_commands(message)
        if message.channel.id == KOTH_CHANNEL_ID:
            await self.update_king(message)


async def setup(bot: Bot):
    await bot.add_cog(KingOfTheHill(bot))
