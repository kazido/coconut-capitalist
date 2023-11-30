
import discord
from discord.ext.commands import Cog

from cococap.constants import ModerationChannels
from cococap.bot import Bot


class MemberUpdates(Cog):
    """User update handling."""

    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Give new members the default role and a welcome message."""
        WELCOME_CHANNEL_ID = 856921703145144331

        welcome_channel = await self.bot.get_channel(WELCOME_CHANNEL_ID)
        await welcome_channel.send(f"{member.name} has joined the server!")
        # Retrieve default role and give to new user
        default_role = discord.utils.get(member.guild.roles, name='Unranked')
        await member.add_roles(default_role)

    @Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle when a user leaves the guild"""
        channel = self.bot.get_channel(ModerationChannels.DATABASE_LOGS.value)

        left_embed = discord.Embed(color=discord.Color.red())
        left_embed.title = "Member left"
        left_embed.description = f"*Name:* {member.name}\n \
                                   *ID:* {member.id}"
        await channel.send(embed=left_embed)
        
    @Cog.listener()
    async def on_user_update(self, before, after):
        """Handle when a user updates something about their profile"""
        channel = self.bot.get_channel(ModerationChannels.DATABASE_LOGS.value)

        update_embed = discord.Embed(color=discord.Color.blurple())
        update_embed.title = "Member updated"
        update_embed.description = f"*Before:* {before}\n \
                                     *After:* {after}"
        await channel.send(embed=update_embed)


async def setup(bot: Bot) -> None:
    """Load the MemberUpdates cog."""
    await bot.add_cog(MemberUpdates(bot))