import discord
from PIL import Image, ImageFont, ImageDraw
from io import BytesIO
import pathlib
from discord.ext import commands
from Cogs.ErrorHandler import registered
from ClassLibrary import *
import asyncio


class ForagingCog(commands.Cog, name='Foraging'):
    """Earn foraging xp by cutting down trees. Don't forget to replant!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    foraging_commands = discord.app_commands.Group(name='foraging',
                                                   description="Commands related to the foraging skill.",
                                                   guild_ids=[856915776345866240, 977351545966432306])

    @foraging_commands.command(name='chop', description="Grab a buddy and chop down a tree.")
    async def chop(self, interaction: discord.Interaction):
        CHOPPING_POWER = 1
        tree = Tree(user1=interaction.user)
        needs_join_embed = discord.Embed(
            title=f"You come across a **{tree.height}ft** tree. :evergreen_tree:",
            description="You need someone else to join you to chop down this tree!\nUsers: (1/2)",
            color=0x034509
        )
        tree.interaction = interaction

        class HeaveHoButtons(discord.ui.View):
            async def on_timeout(self) -> None:
                tree_expired_embed = discord.Embed(
                    title="This tree sat for too long :(",
                    description="Don't start chopping a tree and forget about it! That's a hazard!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=tree_expired_embed, view=None)

            bot = self.bot

            def __init__(self, *, timeout=1800):
                super().__init__(timeout=timeout)

            @discord.ui.button(label=f"Heave!", style=discord.ButtonStyle.green, disabled=False)
            async def heave_button(self, heave_interaction: discord.Interaction, button: discord.Button):
                if heave_interaction.user != tree.user1:
                    return
                tree.hitpoints -= CHOPPING_POWER
                if tree.hitpoints <= 0:
                    await heave_interaction.response.edit_message(embed=tree.embed, view=None)
                else:
                    chop_embed = discord.Embed(
                        title=f"{tree.user1.display_name} and {tree.user2.display_name} are chopping a **{tree.height}ft** tree...",
                        description=f"*{tree.user2.display_name} must ho! :arrow_left:*\n**Tree Health: {tree.hitpoints}**",
                        color=0x039410
                    )
                    self.heave_button.disabled = True
                    self.heave_button.style = discord.ButtonStyle.grey
                    self.ho_button.disabled = False
                    self.ho_button.style = discord.ButtonStyle.green
                    await heave_interaction.response.edit_message(embed=chop_embed, view=self)

            @discord.ui.button(label=f"Ho!", style=discord.ButtonStyle.grey, disabled=True)
            async def ho_button(self, ho_interaction: discord.Interaction, button: discord.Button):
                if ho_interaction.user != tree.user2:
                    return
                tree.hitpoints -= CHOPPING_POWER
                if tree.hitpoints <= 0:
                    await ho_interaction.response.edit_message(embed=tree.embed, view=None)
                else:
                    chop_embed = discord.Embed(
                        title=f"{tree.user1.display_name} and {tree.user2.display_name} are chopping a **{tree.height}ft** tree...",
                        description=f"*:arrow_right: {tree.user1.display_name} must heave!*\n**Tree Health: {tree.hitpoints}**",
                        color=0x039410
                    )
                    self.ho_button.disabled = True
                    self.ho_button.style = discord.ButtonStyle.grey
                    self.heave_button.disabled = False
                    self.heave_button.style = discord.ButtonStyle.green
                    await ho_interaction.response.edit_message(embed=chop_embed, view=self)

        class JoinTreeButton(discord.ui.View):
            async def on_timeout(self) -> None:
                await interaction.delete_original_message()

            bot = self.bot

            def __init__(self, *, timeout=1800):
                super().__init__(timeout=timeout)

            @discord.ui.button(label=f"Join {tree.user1.display_name}", style=discord.ButtonStyle.green)
            async def join_button(self, join_interaction: discord.Interaction, button: discord.ui.Button):
                if join_interaction.user == interaction.user:
                    return
                tree.user2 = join_interaction.user
                chop_embed = discord.Embed(
                    title=f"{tree.user1.display_name} and {tree.user2.display_name} are chopping a **{tree.height}ft** tree.",
                    description=f"*:arrow_right: {tree.user1.display_name} must heave!*\n**Tree Health: {tree.hitpoints}**",
                    color=0x039410
                )
                await join_interaction.response.edit_message(embed=chop_embed, view=HeaveHoButtons())

        await interaction.response.send_message(embed=needs_join_embed, view=JoinTreeButton())


async def setup(bot):
    await bot.add_cog(ForagingCog(bot))
