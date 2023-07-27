import discord
import numpy

from discord import app_commands
from discord.ext import commands
from random import randint
from logging import getLogger
from src.utils.managers import UserManager
from src.constants import GREEN_CHECK_MARK_URL, RED_X_URL
from src.resources.unused_code.data import get_attribute

log = getLogger(__name__)
log.setLevel(10)

TREE_CHOP_TIMEOUT = 1800

NEW_TREE_FOOTER = "[Placeholder footer]"

class Tree:
    # Different possibilities in tree height
    tree_heights = [randint(20, 40), randint(40, 50), randint(50, 60), randint(90, 100)]
    height_odds = [0.499, 0.300, 0.200, 0.001]

    def __init__(self, user):
        self.height = numpy.random.choice(Tree.tree_heights, p=Tree.height_odds)
        self.hitpoints = round(self.height / 2)
        self.embed = None
        self.user = user
        self.user_2 = None
        
    @property
    def hitpoints(self):
        return self._hitpoints

    @hitpoints.setter
    def hitpoints(self, new_hitpoints):
        if new_hitpoints <= 0:
            self._hitpoints = 0
            self.embed = self.on_chopped_down()
        else:
            self._hitpoints = new_hitpoints

    def on_chopped_down(self):
        chopped_embed = discord.Embed(
            title="Tree chopped! :evergreen_tree:",
            description=f"{self.user1.instance.name} and {self.user2.instance.name} "
                        f"successfully chopped down a **{self.height}ft** tree!",
            color=0x573a26
        )
        return chopped_embed


class ForagingCog(commands.Cog, name='Foraging'):
    """Earn foraging xp by cutting down trees. Don't forget to replant!"""

    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name='chop', description="Grab a buddy and chop down a tree.")
    @app_commands.describe(member="Another member you wish to chop a tree with")
    async def chop(self, interaction: discord.Interaction, member: discord.Member=None):
        user = UserManager(interaction.user.id, interaction=interaction)
        user_tool = user.get_data("tool_id")
        
        # If the user does not own an axe
        if not user_tool:
            need_axe_embed = discord.Embed(
                description="You need an axe to chop trees",
                color=discord.Color.red())
            need_axe_embed.set_author(name="You need an axe", icon_url=RED_X_URL)
            need_axe_embed.set_footer(text="Get items from /shop")
            await interaction.response.send_message(embed=need_axe_embed)
            return
        
        # Initialize a tree
        tree = Tree(user=user)
        
        if not member:
            # Find someone to join the user
            invite_embed = discord.Embed(
                title=f"Here's a **{tree.height}ft** tree :evergreen_tree:",
                description="Find someone to help you!\nUsers: (1/2)",
                color=0x034509
            )
            invite_embed.set_footer(text="Hint: try chopping trees in a party")
            
        class HeaveHoButtons(discord.ui.View):
            async def on_timeout(self) -> None:
                tree_expired_embed = discord.Embed(
                    title="The injured tree was left alone",
                    description="Don't start chopping a tree and forget about it! That's a safety hazard!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=tree_expired_embed, view=None)

            def __init__(self, *, timeout=TREE_CHOP_TIMEOUT):
                super().__init__(timeout=timeout)

            @discord.ui.button(label=f"Heave!", style=discord.ButtonStyle.green, disabled=False)
            async def heave_button(self, heave_interaction: discord.Interaction, button: discord.Button):
                if heave_interaction.user.id != tree.user.get_data('user_id'):
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
                if ho_interaction.user.id != tree.user_2.get_data('user_id'):
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

        await interaction.response.send_message(embed=invite_embed, view=JoinTreeButton())


async def setup(bot):
    await bot.add_cog(ForagingCog(bot))
from src.classLibrary import RequestUser
import discord
from discord import app_commands
from discord.ext import commands

import json

class ForagingCog(commands.Cog, name='Foraging'):
    """Earn foraging xp by cutting down trees. Don't forget to replant!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    # 
    # @app_commands.guilds(856915776345866240, 977351545966432306)
    # @app_commands.command(name='chop', description="Grab a buddy and chop down a tree.")
    # async def chop(self, interaction: discord.Interaction):
    #     user1 = RequestUser(interaction.user.id, interaction=interaction)
    #     if user1.instance.axe == "None":
    #         need_axe_embed = discord.Embed(
    #             title="You don't have an axe!",
    #             description="You need an axe to chop trees. Get one at the shop.",
    #             color=discord.Color.red())
    #         await interaction.response.send_message(embed=need_axe_embed)
    #         return
    #     tree = Tree(user1=user1)
    #     needs_join_embed = discord.Embed(
    #         title=f"You come across a **{tree.height}ft** tree. :evergreen_tree:",
    #         description="You need someone else to join you to chop down this tree!\nUsers: (1/2)",
    #         color=0x034509
    #     )
    #     tree.interaction = interaction

    #     class HeaveHoButtons(discord.ui.View):
    #         async def on_timeout(self) -> None:
    #             tree_expired_embed = discord.Embed(
    #                 title="This tree sat for too long :(",
    #                 description="Don't start chopping a tree and forget about it! That's a hazard!",
    #                 color=discord.Color.red()
    #             )
    #             await interaction.response.edit_message(embed=tree_expired_embed, view=None)

    #         def __init__(self, *, timeout=1800):
    #             super().__init__(timeout=timeout)

    #         @discord.ui.button(label=f"Heave!", style=discord.ButtonStyle.green, disabled=False)
    #         async def heave_button(self, heave_interaction: discord.Interaction, button: discord.Button):
    #             if heave_interaction.user.id != tree.user1.instance.id:
    #                 return
    #             tree.hitpoints -= tools[tree.user1_axe]['power']
    #             if tree.hitpoints <= 0:
    #                 await heave_interaction.response.edit_message(embed=tree.embed, view=None)
    #             else:
    #                 chop_embed = discord.Embed(
    #                     title=f"{tree.user1.instance.name} and {tree.user2.instance.name} are chopping a **{tree.height}ft** tree...",
    #                     description=f"*{tree.user2.instance.name} must ho! :arrow_left:*\n**Tree Health: {tree.hitpoints}**",
    #                     color=0x039410
    #                 )
    #                 self.heave_button.disabled = True
    #                 self.heave_button.style = discord.ButtonStyle.grey
    #                 self.ho_button.disabled = False
    #                 self.ho_button.style = discord.ButtonStyle.green
    #                 await heave_interaction.response.edit_message(embed=chop_embed, view=self)

    #         @discord.ui.button(label=f"Ho!", style=discord.ButtonStyle.grey, disabled=True)
    #         async def ho_button(self, ho_interaction: discord.Interaction, button: discord.Button):
    #             if ho_interaction.user.id != tree.user2.instance.id:
    #                 return
    #             tree.hitpoints -= tools[tree.user2_axe]['power']
    #             if tree.hitpoints <= 0:
    #                 await ho_interaction.response.edit_message(embed=tree.embed, view=None)
    #             else:
    #                 chop_embed = discord.Embed(
    #                     title=f"{tree.user1.instance.name} and {tree.user2.instance.name} are chopping a **{tree.height}ft** tree...",
    #                     description=f"*:arrow_right: {tree.user1.instance.name} must heave!*\n**Tree Health: {tree.hitpoints}**",
    #                     color=0x039410
    #                 )
    #                 self.ho_button.disabled = True
    #                 self.ho_button.style = discord.ButtonStyle.grey
    #                 self.heave_button.disabled = False
    #                 self.heave_button.style = discord.ButtonStyle.green
    #                 await ho_interaction.response.edit_message(embed=chop_embed, view=self)

    #     class JoinTreeButton(discord.ui.View):
    #         async def on_timeout(self) -> None:
    #             nobody_joined_embed = discord.Embed(
    #                 title="Nobody else wanted to chop this tree.",
    #                 description="Maybe a friendly bear will help you! JK.",
    #                 color=discord.Color.red()
    #             )
    #             await interaction.edit_original_response(embed=nobody_joined_embed, view=None)

    #         def __init__(self, *, timeout=1800):
    #             super().__init__(timeout=timeout)

    #         @discord.ui.button(label=f"Join {tree.user1.instance.name}", style=discord.ButtonStyle.green)
    #         async def join_button(self, join_interaction: discord.Interaction, button: discord.ui.Button):
    #             if join_interaction.user == interaction.user:
    #                 return
    #             user2 = RequestUser(join_interaction.user.id, interaction=join_interaction)
    #             if user2.instance.axe == 'None':
    #                 need_axe_embed = discord.Embed(
    #                     title="You don't have an axe!",
    #                     description="You need an axe to chop trees. Get one at the shop.",
    #                     color=discord.Color.red())
    #                 await join_interaction.response.send_message(embed=need_axe_embed, ephemeral=True)
    #                 return
    #             tree.user2 = user2
    #             tree.user2_axe = tree.user2.instance.axe
    #             chop_embed = discord.Embed(
    #                 title=f"{tree.user1.instance.name} and {tree.user2.instance.name} are chopping a **{tree.height}ft** tree.",
    #                 description=f"*:arrow_right: {tree.user1.instance.name} must heave!*\n**Tree Health: {tree.hitpoints}**",
    #                 color=0x039410
    #             )
    #             await join_interaction.response.edit_message(embed=chop_embed, view=HeaveHoButtons())

    #     await interaction.response.send_message(embed=needs_join_embed, view=JoinTreeButton())


async def setup(bot):
    await bot.add_cog(ForagingCog(bot))
