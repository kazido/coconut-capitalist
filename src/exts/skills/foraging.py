from typing import Any
import discord
from discord.interactions import Interaction
import numpy

from discord import app_commands
from discord.ext import commands
from random import randint
from logging import getLogger
from src.utils.managers import UserManager, ItemManager, DataManager, ToolManager
from src.models import DataAreas
from src.constants import GREEN_CHECK_MARK_URL, RED_X_URL, DiscordGuilds
from utils.managers import UserManager

log = getLogger(__name__)
log.setLevel(10)

TREE_TITLE = "%s and %s are chopping a **%sft** tree..."


# Defines a custom button that contains logic for 'chopping' a tree
class ChopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.green, label="Chop!")

    async def callback(self, interaction: discord.Interaction):
        view: TreeChop = self.view

    @discord.ui.button(label=f"Heave!", style=discord.ButtonStyle.green, disabled=False)
    async def heave_button(
        self, heave_interaction: discord.Interaction, button: discord.Button
    ):
        if heave_interaction.user.id != tree.user.get_field("user_id"):
            return

        tree.hitpoints -= tree.user_tool.total_power
        if tree.hitpoints <= 0:
            await heave_interaction.response.edit_message(embed=tree.embed, view=None)
        else:
            chop_embed = discord.Embed(
                title=f"{tree.user.get_field('name')} and {tree.user_2.get_field('name')} are chopping a **{tree.height}ft** tree...",
                description=f"*{tree.user_2.get_field('name')} must ho! :arrow_left:*\n**Tree Health: {tree.hitpoints}**",
                color=0x039410,
            )
            self.heave_button.disabled = True
            self.heave_button.style = discord.ButtonStyle.grey
            self.ho_button.disabled = False
            self.ho_button.style = discord.ButtonStyle.green
            await heave_interaction.response.edit_message(embed=chop_embed, view=self)

    @discord.ui.button(label=f"Ho!", style=discord.ButtonStyle.grey, disabled=True)
    async def ho_button(
        self, ho_interaction: discord.Interaction, button: discord.Button
    ):
        if ho_interaction.user.id != tree.user_2.get_field("user_id"):
            return

        tree.hitpoints -= tree.user_2_tool.total_power
        if tree.hitpoints <= 0:
            await ho_interaction.response.edit_message(embed=tree.embed, view=None)
        else:
            chop_embed = discord.Embed(
                title=f"{tree.user.get_field('name')} and {tree.user_2.get_field('name')} are chopping a **{tree.height}ft** tree...",
                description=f"*:arrow_right: {tree.user.get_field('name')} must heave!*\n**Tree Health: {tree.hitpoints}**",
                color=0x039410,
            )
            self.ho_button.disabled = True
            self.ho_button.style = discord.ButtonStyle.grey
            self.heave_button.disabled = False
            self.heave_button.style = discord.ButtonStyle.green
            await ho_interaction.response.edit_message(embed=chop_embed, view=self)


# The view for the tree
class TreeChop(discord.ui.View):
    # Initialize view with tree and players
    def __init__(self, P1, P2, interaction):
        super().__init__(timeout=1800)
        self.tree = Tree()
        self.interaction: discord.Interaction = interaction
        self.current_user = self.P1

    # If the user's don't interact with the tree, disable the view
    async def on_timeout(self):
        expired = discord.Embed(
            title="The half-chopped tree was left alone...",
            description="Don't start chopping a tree and forget about it! That's a safety hazard!",
            color=discord.Color.red(),
        )
        await self.interaction.followup.edit_message(embed=expired, view=None)


class Tree:
    # Different possibilities in tree height
    heights = [randint(20, 40), randint(40, 50), randint(50, 60), randint(90, 100)]
    p = [0.499, 0.300, 0.200, 0.001]

    def __init__(self, P1: UserManager, P2: UserManager):
        # Get a random weighted height for the tree
        self.height = int(numpy.random.choice(Tree.heights, p=Tree.p))
        # Get data for the area from player who found tree
        self.area: DataAreas = DataManager("areas", P1.get_field("area_id"))
        self.difficulty = self.area.get_field("difficulty")
        # Adjust the height of the tree according to the difficulty of the area
        self.height = self.height * self.difficulty
        self._hitpoints = self.height

    def heave(self):
        self.hitpoints -= self.user_tool.total_power
        if self.hitpoints <= 0:
            return
        tree_embed = discord.Embed(
            title=TREE_TITLE % (str(self.user), str(self.user_2), self.height),
            description=f"*{self.user_2} must ho! :arrow_left:*",
            color=0xB3EB60,
        )
        tree_embed.add_field(name="Tree Health", value=self.hitpoints)
        self.heave_button.disabled = True
        self.heave_button.style = discord.ButtonStyle.grey
        self.ho_button.disabled = False
        self.ho_button.style = discord.ButtonStyle.green

    @property
    def hitpoints(self):
        return self._hitpoints

    @hitpoints.setter
    def hitpoints(self, new_hitpoints):
        if new_hitpoints <= 0:
            self._hitpoints = 0
            self.embed = self.on_chopped_down()
            return
        self._hitpoints = new_hitpoints

    def on_chopped_down(self):
        chopped_embed = discord.Embed(
            title="Tree chopped! :evergreen_tree:",
            description=f"{self.user.get_field('name')} and {self.user_2.get_field('name')} "
            f"successfully chopped down a **{self.height}ft** tree!",
            color=0x573A26,
        )
        return chopped_embed


class ForagingCog(commands.Cog, name="Foraging"):
    """Earn foraging xp by cutting down trees. Don't forget to replant!"""

    def __init__(self, bot):
        self.bot = bot

    # Foraging command group
    primary_guild = DiscordGuilds.PRIMARY_GUILD.value
    foraging = app_commands.Group(name="foraging", guild_ids=[primary_guild])

    @foraging.command(name="chop", description="Grab a buddy and chop down a tree.")
    async def chop(self, interaction: discord.Interaction):
        user = UserManager(interaction.user.id, interaction=interaction)

        user_tool = ToolManager(
            user.get_field("user_id"), user.get_field("tool_id", "foraging")
        )

        # If the user does not own an axe
        if not user_tool.instance:
            embed = discord.Embed(
                description="You need an axe to chop trees!", color=discord.Color.red()
            )
            embed.set_author(name="Slow down, lumberjack.", icon_url=RED_X_URL)
            embed.set_footer(text="Get items from /shop")
            await interaction.response.send_message(embed=embed)
            return

        # Initialize a tree
        tree = Tree(user)
        tree.user_tool = user_tool

        tree.embed = discord.Embed(
            title=f"Here's a **{tree.height}ft** tree :evergreen_tree:",
            description="Find someone to help you!\nUsers: (1/2)",
            color=0x034509,
        ).set_footer(text="Hint: try chopping trees in a party")

        class JoinTreeButton(discord.ui.View):
            async def on_timeout(self) -> None:
                nobody_joined_embed = discord.Embed(
                    title="Nobody else wanted to chop this tree.",
                    description="Maybe a friendly bear will help you! JK.",
                    color=discord.Color.red(),
                )
                await interaction.edit_original_response(
                    embed=nobody_joined_embed, view=None
                )

            def __init__(self, *, timeout=1800):
                super().__init__(timeout=timeout)

            @discord.ui.button(
                label=f"Join {tree.user.get_field('name')}",
                style=discord.ButtonStyle.green,
            )
            async def join_button(
                self, join_interaction: discord.Interaction, button: discord.ui.Button
            ):
                if join_interaction.user == interaction.user:
                    return
                user_2 = UserManager(
                    join_interaction.user.id, interaction=join_interaction
                )
                user_2_tool = ToolManager(
                    user_2.get_field("user_id"), user_2.get_field("tool_id", "foraging")
                )

                if user_2_tool.instance is None:
                    need_axe_embed = discord.Embed(
                        title="You don't have an axe!",
                        description="You need an axe to chop trees. Get one at the shop.",
                        color=discord.Color.red(),
                    )
                    await join_interaction.response.send_message(
                        embed=need_axe_embed, ephemeral=True
                    )
                    return

                tree.user_2 = user_2
                tree.user_2_tool = user_2_tool
                log.debug(f"User joined with axe power: {user_2_tool.total_power}")

                chop_embed = discord.Embed(
                    title=f"{tree.user.get_field('name')} and {tree.user_2.get_field('name')} are chopping a **{tree.height}ft** tree.",
                    description=f"*:arrow_right: {tree.user.get_field('name')} must heave!*\n**Tree Health: {tree.hitpoints}**",
                    color=0x039410,
                )
                await join_interaction.response.edit_message(
                    embed=chop_embed, view=TreeChop()
                )

        await interaction.response.send_message(embed=tree_embed, view=JoinTreeButton())


async def setup(bot):
    await bot.add_cog(ForagingCog(bot))
