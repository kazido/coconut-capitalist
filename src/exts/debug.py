import asyncio
import random

from discord import app_commands
import discord
from discord.ext import commands
import os
import pathlib
from classLibrary import RequestUser
from src import models


class EmbedModal(discord.ui.Modal, title="Embed Creation"):
    embed_title = discord.ui.TextInput(label="Title")
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title=self.embed_title,
            description=self.description,
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


class DebuggingCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Testing command
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command()
    async def test(self, interaction: discord.Interaction):
        pass

    admin_commands = discord.app_commands.Group(
        name="admin",
        description="Admin only commands.",
        guild_ids=[856915776345866240, 977351545966432306],
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
        path = pathlib.Path('main.py').parent.resolve()
        await ctx.send(f"`{os.path.abspath(__file__)}`")
        await ctx.send(f'Pong! {round(self.bot.latency * 1000)}ms')
        sync = await self.bot.tree.sync(guild=discord.Object(id=856915776345866240))

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        await member.kick(reason=reason)
        await ctx.send(f'Kicked {member.mention}.')

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        await member.ban(reason=reason)
        await ctx.send(f'Banned {member.mention}.')

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, *, member):
        banned_users = await ctx.guild.bans()
        member_name, member_discriminator = member.split('#')

        for ban_entry in banned_users:
            user = ban_entry.user

            if (user.name, user.discriminator) == (member_name, member_discriminator):
                await ctx.guild.unban(user)
                await ctx.send(f'User {user.mention} has been unbanned.')
                return


    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount):
        await ctx.channel.purge(limit=int(amount) + 1)

    # # A command for evaluating python code in discord
    # @commands.command()
    # async def eval(self, ctx, *, args):
    #     client = PystonClient()
    #     if str(args.startswith('`')):
    #         args = str(args.strip('`'))
    #     else:
    #         await ctx.send("Please format your code with ``` at the beginning and end.")
    #     output = await client.execute("python", [File(args)])
    #     embed = discord.Embed(
    #         title=f"Evaluation for: {ctx.author.name}",
    #         description=f"```{args}\n\nResults in:\n{output}```",
    #         color=discord.Color.purple()
    #     )
    #     await ctx.send(embed=embed)

    # A command for sending embeds
    @app_commands.command(name="embed", description="Create an embed.")
    @app_commands.guilds(856915776345866240, 977351545966432306)
    async def embed(self, interaction: discord.Interaction):
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
