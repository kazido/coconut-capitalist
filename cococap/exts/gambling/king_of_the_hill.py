import discord

from cococap.bot import Bot
from cococap.user import User
from discord.ext import commands

from cococap.utils.utils import timestamp_to_english


# King of the Hill related IDs
KOTH_CHANNEL_ID = 859262125390168074
KOTH_ROLE_ID = 895078616063430666


class KingOfTheHill(commands.Cog, name="King of the Hill"):
    """Be the last to send a message in the King of the Hill channel to be the King!"""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def update_king(message: discord.Message, last_message: discord.Message):
        koth_role = message.guild.get_role(KOTH_ROLE_ID)

        # Retrieve the guild so we can check everyone's roles
        guild = message.guild
        for member in guild.members:
            if member == message.author:
                await member.add_roles(koth_role)
            elif koth_role in member.roles:
                await member.remove_roles(koth_role)

        now = message.created_at.timestamp()
        then = last_message.created_at.timestamp()

        difference = round(now - then)

        if difference > 60:
            bit_reward = difference * 10

            # Load the user and update their purse
            user = User(last_message.author.id)
            await user.load()
            await user.inc_purse(bit_reward)

            await last_message.reply(
                f"You earned *+{bit_reward:,} bits* for holding the position for {timestamp_to_english(now - then)}."
            )
        return

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id == KOTH_CHANNEL_ID:
            history = [item async for item in message.channel.history(limit=2)]
            last = history[1]
            if not message.author.bot and (last.author != message.author):
                await self.update_king(message, last)


async def setup(bot: Bot):
    await bot.add_cog(KingOfTheHill(bot))
