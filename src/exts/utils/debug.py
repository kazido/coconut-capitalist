import asyncio
import os
import discord

from discord import app_commands
from discord.ext import commands
from src.classLibrary import RequestUser
from src.constants import DiscordGuilds


class DebuggingCommands(commands.Cog, name="Debugging Commands"):
    def __init__(self, bot):
        self.bot = bot

    # Testing command
    @app_commands.guilds(DiscordGuilds.PRIMARY_GUILD.value, DiscordGuilds.TESTING_GUILD.value)
    @app_commands.command()
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message(asyncio.all_tasks())

    admin_commands = discord.app_commands.Group(
        name="admin",
        description="Admin only commands.",
        guild_ids=[DiscordGuilds.PRIMARY_GUILD.value,
                   DiscordGuilds.TESTING_GUILD.value],
        default_permissions=None
    )

    @admin_commands.command(name="pay")
    async def admin_pay(self, interaction: discord.Interaction, user: discord.User, amount: int):
        user_to_pay = RequestUser(user.id, interaction=interaction)
        paid_embed = discord.Embed(title="Updated balance.",
                                   description=f"Updated {user.name}'s balance by **{amount:,}** bits.",
                                   color=discord.Color.red())
        user_to_pay.update_balance(amount)
        await interaction.response.send_message(embed=paid_embed)

    @commands.command(name='work', aliases=['daily', 'hl'])
    async def using_slash_commands(self, ctx):
        class ThanksButtons(discord.ui.View):
            def __init__(self, *, timeout=180):
                super().__init__(timeout=timeout)

            @discord.ui.button(label="Thanks!", style=discord.ButtonStyle.blurple)
            async def thanks_button(self, thanks_interaction: discord.Interaction, button: discord.Button):
                if thanks_interaction.user != ctx.author:
                    return
                await thanks_interaction.response.send_message("You're welcome!")
                await asyncio.sleep(5)
                await thanks_interaction.delete_original_response()
                await message.delete()
                await ctx.message.delete()

            @discord.ui.button(label="Cool.", style=discord.ButtonStyle.blurple)
            async def cool_button(self, cool_interaction: discord.Interaction, button: discord.Button):
                if cool_interaction.user != ctx.author:
                    return
                await message.delete()
                await ctx.message.delete()

        time_to_switch = discord.Embed(
            title="The Economy Discord Bot now uses slash commands!",
            description="All the Economy Bot commands have been switched over to **slash commands!**\n"
                        "Try using **/** instead of **-** for your commands.\n"
                        "*Let me know what you think!*",
            color=discord.Color.from_str("0xc3f2a7")
        )
        message = await ctx.send(embed=time_to_switch, view=ThanksButtons())

    # Sends the path of the bot. Mainly to check for more than one instance, not sure if this works yet
    @commands.is_owner()
    @commands.command(name='Ping')
    async def ping(self, ctx):
        sync = await self.bot.tree.sync(guild=discord.Object(id=DiscordGuilds.PRIMARY_GUILD.value))
        if sync:
            synced = True
        else:
            synced = False
        embed = discord.Embed(
            title="Ping requested.",
            description=f"**Pong!** {round(self.bot.latency * 1000)}ms\
            \nSynced? {synced}",
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"{os.path.abspath(__file__)}")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount):
        await ctx.channel.purge(limit=int(amount) + 1)

    # A command for sending embeds
    @app_commands.command(name="embed", description="Create an embed.")
    @app_commands.guilds(856915776345866240, 977351545966432306)
    async def embed(self, interaction: discord.Interaction):
        class EmbedModal(discord.ui.Modal, title="Embed Creation"):
            embed_title = discord.ui.TextInput(label="Title")
            description = discord.ui.TextInput(
                label="Description", style=discord.TextStyle.paragraph)

            async def on_submit(self, interaction: discord.Interaction) -> None:
                embed = discord.Embed(
                    title=self.embed_title,
                    description=self.description,
                    color=discord.Color.green()
                )
                await interaction.response.send_message(embed=embed)
        await interaction.response.send_modal(EmbedModal())

    @app_commands.command(name="check", description="Check to see if you're on mobile or desktop!")
    @app_commands.guilds(856915776345866240, 977351545966432306)
    async def check(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(interaction.user.id)
        if member.is_on_mobile():
            await interaction.response.send_message("I'm a mobile user!")
            return
        await interaction.response.send_message("I'm not a mobile user...")

    # A command for sending embeds with images in them
    @commands.is_owner()
    @commands.command()
    async def embedimage(self, ctx):
        # Ask for title of embed and image of embed. Set those to the contents of the embed
        question1 = await ctx.send("What would you like the title of the embed to be.")
        title = await self.bot.wait_for(event="message")
        question2 = await ctx.send("Please send the attachment for the image.")
        file = await self.bot.wait_for('message')
        if file.attachments is None:
            # If there is no image attached, tell them to attach an image.
            await ctx.reply("Please rerun the command and an image.")
            return
        else:
            # Create the embed, set the image to be the url of the first image in attachments.
            embed = discord.Embed(
                title=title.content,
                color=discord.Color.green()
            )
            embed.set_image(url=file.attachments[0].url)
            # delete all of the previously asked questions and commands.
            await question1.delete()
            await question2.delete()
            await title.delete()
            await file.delete()
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(DebuggingCommands(bot))
