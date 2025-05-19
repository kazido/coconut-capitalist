import os
import discord
from discord import app_commands
from discord.ext import commands
from cococap.user import User
from utils.custom_embeds import CustomEmbed, SuccessEmbed

ADMIN_ID = 326903703422500866


class DebuggingCommands(commands.Cog, name="Debugging Commands"):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    async def cog_check(self, ctx: commands.Context):
        # Only admin can use prefixed commands in here
        return ctx.author.id == ADMIN_ID

    async def interaction_check(self, interaction):
        # Only admins can use slash commands in here
        return interaction.user.id == ADMIN_ID

    @app_commands.command(name="admin_pay", description="Admin: Pay any user bits.")
    @app_commands.checks.has_permissions(administrator=True)  # Only admins see it
    async def admin_pay(self, interaction: discord.Interaction, user: discord.User, amount: int):
        payee = await User.get(user.id)
        await payee.add_bits(amount)
        paid_embed = discord.Embed(
            title="Updated balance.",
            description=f"Updated {user.name}'s ({user.display_name}) balance by **{amount:,}** bits.",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=paid_embed)

    @commands.command(name="Ping")
    async def ping(self, ctx):
        embed = discord.Embed(
            title="Ping requested.",
            description=f"**Pong!** {round(self.bot.latency * 1000)}ms",
            color=discord.Color.purple(),
        )
        embed.set_footer(text=f"Ran from {os.path.abspath(__file__)}")
        await ctx.send(embed=embed)

    @commands.command(name="Reset")
    async def reset(self, ctx):
        user = await User.get(ctx.author.id)
        await user.set_field("cooldowns.work", 0)
        await user.set_field("cooldowns.daily", 0)
        await user.set_field("cooldowns.weekly", 0)
        embed = CustomEmbed(desc="RESET! RESET! RESET!")
        await ctx.send(embed=embed)

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
            title = "Syncing locally..."
            embed = SuccessEmbed(title=title, desc=f"Synced commands: {sync}")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount):
        await ctx.channel.purge(limit=int(amount) + 1)

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
