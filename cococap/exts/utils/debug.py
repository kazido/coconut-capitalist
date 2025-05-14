import os
import discord

from discord import app_commands
from discord.ext import commands

from cococap.user import User
from utils.custom_embeds import CustomEmbed, SuccessEmbed, ErrorEmbed


class DebuggingCommands(commands.Cog, name="Debugging Commands"):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.bot.tree.add_command(self.AdminCommands())

    class AdminCommands(discord.app_commands.Group):
        def __init__(self):
            super().__init__(name="admin", description="Admin only commands.")

        async def interaction_check(self, interaction):
            if interaction.user.id != 326903703422500866:
                return False
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
        embed = CustomEmbed(desc="Unstuck now!")
        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command(name="sync")
    async def sync(self, ctx, scope: str = None):
        if scope == "global":
            sync = await self.bot.tree.sync()
            embed = discord.Embed(
                title="Syncing...",
                description=f"Job: {'SUCCESS' if sync else 'FAILED'}",
                color=discord.Color.green() if sync else discord.Color.red(),
            )
        else:
            guild = discord.Object(id=1310808494299156482)
            self.bot.tree.clear_commands(guild=guild)
            sync = await self.bot.tree.sync(guild=guild)
            print(sync)
            title = "Syncing locally..."
            embed = SuccessEmbed(title=title, desc=f"Synced commands: {sync}")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount):
        await ctx.channel.purge(limit=int(amount) + 1)

    # A command for sending embeds
    @app_commands.command(name="embed", description="Create an embed.")
    async def embed(self, interaction: discord.Interaction):
        class EmbedModal(discord.ui.Modal, title="Embed Creation"):
            embed_title = discord.ui.TextInput(label="Title")
            description = discord.ui.TextInput(
                label="Description", style=discord.TextStyle.paragraph
            )

            async def on_submit(self, interaction: discord.Interaction) -> None:
                embed = discord.Embed(
                    title=self.embed_title,
                    description=self.description,
                    color=discord.Color.green(),
                )
                await interaction.response.send_message(embed=embed)

        await interaction.response.send_modal(EmbedModal())


async def setup(bot):
    await bot.add_cog(DebuggingCommands(bot))
