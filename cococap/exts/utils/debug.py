import asyncio
import os
import discord

from discord import app_commands
from discord.ext import commands

from cococap.user import User

from utils.messages import Cembed

# from utils.items.items import item_autocomplete
from cococap.constants import URI

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId


class DebuggingCommands(commands.Cog, name="Debugging Commands"):
    def __init__(self, bot):
        self.bot = bot

    # Testing command
    @app_commands.command()
    async def test(self, interaction: discord.Interaction):
        client = AsyncIOMotorClient(URI)
        collection = client.discordbot.special_entities

        print(await collection.find_one({"_id": ObjectId("65b76d73ee9f83c970604935")}))
        # Interaction has finished
        await interaction.response.send_message("Done.")

    admin_commands = discord.app_commands.Group(name="admin", description="Admin only commands.")

    @admin_commands.command(name="pay")
    async def admin_pay(self, interaction: discord.Interaction, user: discord.User, amount: int):
        if interaction.user.id != 326903703422500866:
            return await interaction.response.send_message("No.", ephemeral=True)
        payee = User(user.id)
        await payee.load()

        paid_embed = discord.Embed(
            title="Updated balance.",
            description=f"Updated {user.name}'s balance by **{amount:,}** bits.",
            color=discord.Color.red(),
        )
        await payee.inc_purse(amount)
        await interaction.response.send_message(embed=paid_embed)

    @admin_commands.command(name="item")
    # @app_commands.autocomplete(item_id=item_autocomplete)
    @app_commands.choices(
        mode=[app_commands.Choice(name="add", value=0), app_commands.Choice(name="delete", value=1)]
    )
    async def admin_item(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        mode: app_commands.Choice[int],
        item_id: str,
        quantity: int = None,
    ):
        if interaction.user.id != 326903703422500866:
            return await interaction.response.send_message("No.", ephemeral=True)
        recipient = User(user.id)
        await recipient.load()
        if mode.value == 0:
            if quantity:
                success, message = await recipient.create_item(item_id=item_id, quantity=quantity)
            else:
                success, message = await recipient.create_item(item_id=item_id)
        else:
            if quantity:
                success, message = await recipient.delete_item(item_id=item_id, quantity=quantity)
            else:
                success, message = await recipient.delete_item(item_id=item_id)
        embed = Cembed(
            title="Success" if success else "Failed",
            desc=f"**{message}**",
            color=discord.Color.green() if success else discord.Color.red(),
            interaction=interaction,
        )
        await interaction.response.send_message(embed=embed)
        return

    @admin_commands.command(name="edit")
    async def edit(self, interaction: discord.Interaction, message_id: str, new_content: str):
        message: discord.Message = await interaction.channel.fetch_message(int(message_id))
        await message.edit(content=new_content)
        await interaction.response.send_message(
            content="Successfully edited message.", ephemeral=True
        )

    @commands.command(name="work", aliases=["daily", "hl"])
    async def using_slash_commands(self, ctx):
        class ThanksButtons(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)

            @discord.ui.button(label="Thanks!", style=discord.ButtonStyle.blurple)
            async def thanks_button(
                self, thanks_interaction: discord.Interaction, button: discord.Button
            ):
                if thanks_interaction.user != ctx.author:
                    return
                await thanks_interaction.response.send_message("You're welcome!")
                await asyncio.sleep(5)
                await thanks_interaction.delete_original_response()
                await message.delete()
                await ctx.message.delete()

            @discord.ui.button(label="Cool.", style=discord.ButtonStyle.blurple)
            async def cool_button(
                self, cool_interaction: discord.Interaction, button: discord.Button
            ):
                if cool_interaction.user != ctx.author:
                    return
                await message.delete()
                await ctx.message.delete()

        time_to_switch = discord.Embed(
            title="The Economy Discord Bot now uses slash commands!",
            description="All the Economy Bot commands have been switched over to **slash commands!**\n"
            "Try using **/** instead of **-** for your commands.\n"
            "*Let me know what you think!*",
            color=discord.Color.from_str("0xc3f2a7"),
        )
        message = await ctx.send(embed=time_to_switch, view=ThanksButtons())

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

    @commands.command(name="check")
    async def check(self, ctx):
        member = ctx.guild.get_member(ctx.user.id)
        if member.is_on_mobile():
            await ctx.send("I'm a mobile user!")
            return
        await ctx.send("I'm not a mobile user...")

    # Syncs the bot's commands to the app globally. New commands won't appear for an hour. Use sparingly to not get rate limited.
    @commands.is_owner()
    @commands.command(name="sync")
    async def sync(self, ctx):
        sync = await self.bot.tree.sync()
        embed = discord.Embed(
            title="Syncing...",
            description=f"Job: {'SUCCESS' if sync else 'FAILED'}",
            color=discord.Color.green() if sync else discord.Color.red(),
        )
        await ctx.send(embed=embed)

    # Syncs the bot's commands to the app globally. New commands won't appear for an hour. Use sparingly to not get rate limited.
    @commands.is_owner()
    @commands.command(name="localsync")
    async def localsync(self, ctx):
        # Copy the global commands over to my guild TODO: This will need to be changed when global
        guild = discord.Object(id=856915776345866240)
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
    async def clear(self, ctx, amount):
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
