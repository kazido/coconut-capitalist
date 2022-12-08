from classLibrary import Tree, RequestUser
import discord
from discord import app_commands
from discord.ext import commands
from cogs.ErrorHandler import registered
import json
from classLibrary import tools

class ForagingCog(commands.Cog, name='Foraging'):
    """Earn foraging xp by cutting down trees. Don't forget to replant!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name='chop', description="Grab a buddy and chop down a tree.")
    async def chop(self, interaction: discord.Interaction):
        user1 = RequestUser(interaction.user.id, interaction=interaction)
        if user1.instance.axe == "None":
            need_axe_embed = discord.Embed(
                title="You don't have an axe!",
                description="You need an axe to chop trees. Get one at the shop.",
                color=discord.Color.red())
            await interaction.response.send_message(embed=need_axe_embed)
            return
        tree = Tree(user1=user1)
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

            def __init__(self, *, timeout=1800):
                super().__init__(timeout=timeout)

            @discord.ui.button(label=f"Heave!", style=discord.ButtonStyle.green, disabled=False)
            async def heave_button(self, heave_interaction: discord.Interaction, button: discord.Button):
                if heave_interaction.user.id != tree.user1.instance.id:
                    return
                tree.hitpoints -= tools[tree.user1_axe]['power']
                if tree.hitpoints <= 0:
                    await heave_interaction.response.edit_message(embed=tree.embed, view=None)
                else:
                    chop_embed = discord.Embed(
                        title=f"{tree.user1.instance.name} and {tree.user2.instance.name} are chopping a **{tree.height}ft** tree...",
                        description=f"*{tree.user2.instance.name} must ho! :arrow_left:*\n**Tree Health: {tree.hitpoints}**",
                        color=0x039410
                    )
                    self.heave_button.disabled = True
                    self.heave_button.style = discord.ButtonStyle.grey
                    self.ho_button.disabled = False
                    self.ho_button.style = discord.ButtonStyle.green
                    await heave_interaction.response.edit_message(embed=chop_embed, view=self)

            @discord.ui.button(label=f"Ho!", style=discord.ButtonStyle.grey, disabled=True)
            async def ho_button(self, ho_interaction: discord.Interaction, button: discord.Button):
                if ho_interaction.user.id != tree.user2.instance.id:
                    return
                tree.hitpoints -= tools[tree.user2_axe]['power']
                if tree.hitpoints <= 0:
                    await ho_interaction.response.edit_message(embed=tree.embed, view=None)
                else:
                    chop_embed = discord.Embed(
                        title=f"{tree.user1.instance.name} and {tree.user2.instance.name} are chopping a **{tree.height}ft** tree...",
                        description=f"*:arrow_right: {tree.user1.instance.name} must heave!*\n**Tree Health: {tree.hitpoints}**",
                        color=0x039410
                    )
                    self.ho_button.disabled = True
                    self.ho_button.style = discord.ButtonStyle.grey
                    self.heave_button.disabled = False
                    self.heave_button.style = discord.ButtonStyle.green
                    await ho_interaction.response.edit_message(embed=chop_embed, view=self)

        class JoinTreeButton(discord.ui.View):
            async def on_timeout(self) -> None:
                nobody_joined_embed = discord.Embed(
                    title="Nobody else wanted to chop this tree.",
                    description="Maybe a friendly bear will help you! JK.",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=nobody_joined_embed, view=None)

            def __init__(self, *, timeout=1800):
                super().__init__(timeout=timeout)

            @discord.ui.button(label=f"Join {tree.user1.instance.name}", style=discord.ButtonStyle.green)
            async def join_button(self, join_interaction: discord.Interaction, button: discord.ui.Button):
                if join_interaction.user == interaction.user:
                    return
                user2 = RequestUser(join_interaction.user.id, interaction=join_interaction)
                if user2.instance.axe == 'None':
                    need_axe_embed = discord.Embed(
                        title="You don't have an axe!",
                        description="You need an axe to chop trees. Get one at the shop.",
                        color=discord.Color.red())
                    await join_interaction.response.send_message(embed=need_axe_embed, ephemeral=True)
                    return
                tree.user2 = user2
                tree.user2_axe = tree.user2.instance.axe
                chop_embed = discord.Embed(
                    title=f"{tree.user1.instance.name} and {tree.user2.instance.name} are chopping a **{tree.height}ft** tree.",
                    description=f"*:arrow_right: {tree.user1.instance.name} must heave!*\n**Tree Health: {tree.hitpoints}**",
                    color=0x039410
                )
                await join_interaction.response.edit_message(embed=chop_embed, view=HeaveHoButtons())

        await interaction.response.send_message(embed=needs_join_embed, view=JoinTreeButton())


async def setup(bot):
    await bot.add_cog(ForagingCog(bot))
