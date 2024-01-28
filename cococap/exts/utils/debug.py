import asyncio
import os
import discord
import datetime

from discord import app_commands
from discord.ext import commands, tasks
from discord.ext.commands import Cog
from cococap.classLibrary import RequestUser

from cococap.user import User

from cococap.utils.tasks import get_time_until, est_tz
from cococap.constants import DiscordGuilds

from cococap.pagination import LinePaginator


class DebuggingCommands(commands.Cog, name="Debugging Commands"):
    def __init__(self, bot):
        self.bot = bot
        
        # starts the loop when the cog is loaded
        self.debugging_loop.start()

    # 1:07 pm EST
    time = datetime.time(hour=13, minute=7, tzinfo=est_tz)
    
    # function should run at 1:07 PM EST
    @tasks.loop(time=time)
    async def debugging_loop(self):
        print("Loop ran.")

    @app_commands.command()
    async def next_loop(self, interaction: discord.Interaction):
        next_loop = get_time_until(self.debugging_loop.next_iteration)
        await interaction.response.send_message(
            "The loop will run next in: " + str(next_loop).split(".")[0]
        )

    # If the cog unloads, cancel the loop
    def cog_unload(self):
        self.debugging_loop.cancel()

    # Testing command
    @app_commands.guilds(
        DiscordGuilds.PRIMARY_GUILD.value, DiscordGuilds.TESTING_GUILD.value
    )
    @app_commands.command()
    async def test(self, interaction: discord.Interaction):
        
        user = User(interaction.user.id)
        await user.load()
        
        user.document.pets["active"] = {
            "pet_id": "bee_pet",
            "level": 1,
            "xp": 0,
            "name": "Arlo"
        }
        await user.save()
        # Interaction has finished
        await interaction.response.send_message("Done.")

    linked_messages = {}

    @app_commands.command()
    async def test_echo_message(self, interaction: discord.Interaction):
        content = "Hello"
        embed = discord.Embed(description="What is up!!!")
        other_channel = discord.utils.get(
            interaction.guild.channels, id=894664255666802759
        )
        echo_message = await other_channel.send(content=content, embed=embed)
        await interaction.response.send_message(content=content, embed=embed)
        original_response = await interaction.original_response()
        DebuggingCommands.linked_messages[original_response] = [echo_message, False]
        await asyncio.sleep(1)
        await interaction.edit_original_response(content="Huh?!?!")

    @Cog.listener()
    async def on_message_edit(self, before, after):
        if (
            before in DebuggingCommands.linked_messages.keys()
            and not DebuggingCommands.linked_messages[before][1]
        ):
            await DebuggingCommands.linked_messages[before][0].edit(
                content=after.content
            )
            DebuggingCommands.linked_messages[before][1] = True
            return
        inverted_map = {v: k for k, v in DebuggingCommands.linked_messages.items()}
        if before in inverted_map.keys() and not inverted_map[before][1]:
            await inverted_map[before][0].edit(content=after.content)
            inverted_map[before][1] = True
            return

    admin_commands = discord.app_commands.Group(
        name="admin",
        description="Admin only commands.",
        guild_ids=[
            DiscordGuilds.PRIMARY_GUILD.value,
            DiscordGuilds.TESTING_GUILD.value,
        ],
        default_permissions=None,
    )

    @admin_commands.command(name="pay")
    async def admin_pay(
        self, interaction: discord.Interaction, user: discord.User, amount: int
    ):
        user_to_pay = RequestUser(user.id, interaction=interaction)
        paid_embed = discord.Embed(
            title="Updated balance.",
            description=f"Updated {user.name}'s balance by **{amount:,}** bits.",
            color=discord.Color.red(),
        )
        user_to_pay.update_balance(amount)
        await interaction.response.send_message(embed=paid_embed)

    @admin_commands.command(name="edit")
    async def edit(
        self, interaction: discord.Interaction, message_id: str, new_content: str
    ):
        message: discord.Message = await interaction.channel.fetch_message(
            int(message_id)
        )
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
    @commands.is_owner()
    @commands.command(name="Ping")
    async def ping(self, ctx):
        sync = await self.bot.tree.sync(
            guild=discord.Object(id=DiscordGuilds.PRIMARY_GUILD.value)
        )
        if sync:
            synced = True
        else:
            synced = False
        embed = discord.Embed(
            title="Ping requested.",
            description=f"**Pong!** {round(self.bot.latency * 1000)}ms\
            \nSynced? {synced}",
            color=discord.Color.purple(),
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

    @app_commands.command(
        name="check", description="Check to see if you're on mobile or desktop!"
    )
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
        file = await self.bot.wait_for("message")
        if file.attachments is None:
            # If there is no image attached, tell them to attach an image.
            await ctx.reply("Please rerun the command and an image.")
            return
        else:
            # Create the embed, set the image to be the url of the first image in attachments.
            embed = discord.Embed(title=title.content, color=discord.Color.green())
            embed.set_image(url=file.attachments[0].url)
            # delete all of the previously asked questions and commands.
            await question1.delete()
            await question2.delete()
            await title.delete()
            await file.delete()
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(DebuggingCommands(bot))
