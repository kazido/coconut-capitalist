import os
import discord

from discord import app_commands
from discord.ext import commands

from cococap.user import User
from utils.custom_embeds import Cembed


class DebuggingCommands(commands.Cog, name="Debugging Commands"):
    def __init__(self, bot):
        self.bot = bot
        self.bot.tree.add_command(self.AdminCommands())

    class AdminCommands(discord.app_commands.Group):
        def __init__(self):
            super().__init__(name="admin", description="Admin only commands.")

        async def interaction_check(self, interaction):
            if interaction.user.id != 326903703422500866:
                await interaction.response.send_message("No.", ephemeral=True)
            return super().interaction_check(interaction)

        @app_commands.command(name="pay")
        async def admin_pay(self, i: discord.Interaction, user: discord.User, amount: int):
            payee = await User(user.id).load()
            await payee.inc_purse(amount)

            paid_embed = discord.Embed(
                title="Updated balance.",
                description=f"Updated {user.name}'s ({user.display_name}) balance by **{amount:,}** bits.",
                color=discord.Color.red(),
            )
            await i.response.send_message(embed=paid_embed)

    # Sends the path of the bot. Mainly to check for more than one instance, not sure if this works yet
    @commands.command(name="Ping")
    async def ping(self, ctx):
        embed = discord.Embed(
            title="Ping requested.",
            description=f"**Pong!** {round(self.bot.latency * 1000)}ms",
            color=discord.Color.purple(),
        )
        embed.set_footer(text=f"Ran from {os.path.abspath(__file__)}")
        await ctx.send(embed=embed)

    # Sets users in-game status to false
    @commands.command(name="Stuck")
    async def stuck(self, ctx):
        user = await User(ctx.author.id).load()
        await user.in_game(in_game=False)
        embed = Cembed(desc="Unstuck now!")
        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command(name="sync")
    async def sync(self, ctx, scope: str = None):
        # Copy the global commands over to my guild TODO: This will need to be changed when global
        if scope == "global":
            sync = await self.bot.tree.sync()
            embed = discord.Embed(
                title="Syncing...",
                description=f"Job: {'SUCCESS' if sync else 'FAILED'}",
                color=discord.Color.green() if sync else discord.Color.red(),
            )
        else:
            guild = discord.Object(id=1310808494299156482)
            self.bot.tree.copy_global_to(guild=guild)
            sync = await self.bot.tree.sync(guild=guild)
            embed = discord.Embed(
                title="Syncing locally...",
                description=f"Job: {'SUCCESS' if sync else 'FAILED'}",
                color=discord.Color.green() if sync else discord.Color.red(),
            )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount):
        await ctx.channel.purge(limit=int(amount) + 1)


async def setup(bot):
    await bot.add_cog(DebuggingCommands(bot))
