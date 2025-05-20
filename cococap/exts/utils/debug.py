import os
import discord
from discord import app_commands
from discord.ext import commands
from cococap.user import User
from utils.custom_embeds import CustomEmbed, SuccessEmbed
from enum import Enum

ADMIN_ID = 326903703422500866


class ReportTypes(Enum):
    BUG = "bug"
    USER = "user"


class ManualEmbedModal(discord.ui.Modal, title="Embed Creation"):
    embed_title = discord.ui.TextInput(label="Title")
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=self.embed_title,
            description=self.description,
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)


class ReportModal(discord.ui.Modal, title="Report an issue"):
    subject = discord.ui.TextInput(label="Issue")
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)

    def __init__(self, report_type: str, message: discord.Message):
        super().__init__()
        self.report_type: ReportTypes = report_type
        self.message = message
        if report_type == ReportTypes.BUG:
            self.color = discord.Color.red()
        if report_type == ReportTypes.USER:
            self.color = discord.Color.orange()

    async def on_submit(self, interaction: discord.Interaction):
        owner = interaction.guild.get_member(326903703422500866)
        embed = (
            discord.Embed(
                title=f"{self.report_type.value.capitalize()} Report: {self.subject}",
                color=self.color,
            )
            .add_field(name="Description", value=f"*{self.description}*", inline=False)
            .set_footer(text="Submitted on: " + interaction.created_at.strftime("%c"))
        ).set_author(icon_url=interaction.user.display_avatar, name=interaction.user.global_name)

        guild = self.message.guild.id
        channel = self.message.channel.id
        message = self.message.id
        jump_link = f"https://discordapp.com/channels/{guild}/{channel}/{message}"
        embed.add_field(name="Jump to:", value=f"{jump_link}")

        users = f"Submitted: {interaction.user.mention}"
        if self.report_type == ReportTypes.USER:
            # Add the reported user
            users += f"\nReported: {self.message.author.mention}"
        embed.add_field(name="Users:", value=users)

        await owner.send(embed=embed)
        await interaction.response.send_message(
            embed=SuccessEmbed(title="Report submitted!", desc="Thanks for your feedback."),
            ephemeral=True,
        )


class DebuggingCommands(commands.Cog, name="Debugging Commands"):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

        # These are context menu commands which can be used when right clicking a user in discord
        self.report_msg = app_commands.ContextMenu(
            name="report user", callback=self.report_msg_context
        )
        self.report_bug = app_commands.ContextMenu(
            name="report bug", callback=self.report_bug_context
        )

    async def cog_load(self) -> None:
        self.bot.tree.add_command(self.report_msg)
        self.bot.tree.add_command(self.report_bug)

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.report_msg)
        self.bot.tree.remove_command(self.report_bug)

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

    async def report_bug_context(self, interaction: discord.Interaction, message: discord.Message):
        modal = ReportModal(report_type=ReportTypes.BUG, message=message)
        await interaction.response.send_modal(modal)

    async def report_msg_context(self, interaction: discord.Interaction, message: discord.Message):
        modal = ReportModal(report_type=ReportTypes.USER, message=message)
        modal.subject.default = f"{message.author.name}"
        await interaction.response.send_modal(modal)

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
        await interaction.response.send_modal(ManualEmbedModal())


async def setup(bot):
    await bot.add_cog(DebuggingCommands(bot))
