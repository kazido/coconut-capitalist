import discord
import random

from discord import app_commands
from discord.ext import commands
from random import randint
from logging import getLogger
from discord.interactions import Interaction

from cococap.constants import RED_X_URL, DiscordGuilds
from cococap.user import User
from cococap.utils.messages import Cembed
from cococap.item_models import Master

log = getLogger(__name__)
log.setLevel(10)


class Tree:
    # Different possibilities in tree height
    HEIGHTS = [randint(20, 40), randint(40, 50), randint(50, 60), randint(90, 100)]
    HEIGHTS_PROBABILITY = [0.499, 0.300, 0.200, 0.001]

    def __init__(self, area_difficulty: int):
        # Get a random weighted height for the tree
        base_height = random.choices(self.HEIGHTS, self.HEIGHTS_PROBABILITY)[0]
        self.height = base_height * area_difficulty
        self.hitpoints = self.height
        self.item_pool = Master.select().where(
            Master.skill == "foraging", Master.drop_rate
        )


class JoinTreeView(discord.ui.View):
    def __init__(self, interaction, user_id):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.user = get_user_data(user_id, backrefs=True)
        # Generate a tree based on the user
        area = self.user['area_id']
        difficulty = area['difficulty']
        self.tree = Tree(difficulty)
        # Add the join button
        self.add_item(JoinTreeButton())

    async def on_timeout(self) -> None:
        embed = discord.Embed(
            title="Nobody else wanted to chop this tree.",
            description="Maybe a friendly bear will help you! :bear:",
            color=discord.Color.dark_grey(),
        )
        await self.interaction.edit_original_response(embed=embed, view=None)


class JoinTreeButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.blurple, label="Join")

    async def callback(self, join_interaction: Interaction):
        view: JoinTreeView = self.view
        if join_interaction.user == view.interaction.user:
            return
        user_2 = get_user_data(join_interaction.user.id, backrefs=True)
        user_2['tool'] = get_user_tool(join_interaction.user.id, 'foraging')
        # Ensure that the second user has a tool
        if user_2['tool'] is None:
            embed = discord.Embed(
                title="You don't have an axe!",
                description="You need an axe to chop trees. Get one at the shop.",
                color=discord.Color.red(),
            )
            await join_interaction.response.send_message(embed=embed, ephemeral=True)
            return
        new_view = TreeView(view.tree, view.user, user_2, view.interaction)
        embed = new_view.refresh_embed()
        await join_interaction.response.edit_message(embed=embed, view=new_view)
        view.stop()


# The view for the tree
class TreeView(discord.ui.View):
    # Initialize view with tree and players
    def __init__(self, tree, p1, p2, interaction):
        super().__init__(timeout=1800)
        self.tree: Tree = tree
        self.interaction: discord.Interaction = interaction
        # Users and area data
        self.users = [p1, p2]
        self.current_user = self.users[0]
        # Add the buttons
        self.button_1 = ChopButton1()
        self.button_2 = ChopButton2()
        self.add_item(self.button_1)
        self.add_item(self.button_2)

    # If the user's don't interact with the tree, disable the view
    async def on_timeout(self):
        expired = discord.Embed(
            title="The half-chopped tree was left alone!",
            description="Don't start chopping a tree and forget about it! \
                \n:warning: That's a safety hazard!",
            color=discord.Color.dark_red(),
        )
        await self.interaction.edit_original_response(embed=expired, view=None)

    def refresh_embed(self):
        tree_emoji = "🌳"
        tree_visual = tree_emoji * int((self.tree.hitpoints / self.tree.height) * 10)
        embed = discord.Embed(
            title=f"{get_user_name(self.current_user['user_id'])} is chopping the tree...",
            description=f"Tree remaining HP: {self.tree.hitpoints}\n{tree_visual}",
            color=0x039410,
        )
        return embed

    async def handle_chop(self, interaction: discord.Interaction, next_user):
        if interaction.user.id != self.current_user['user_id']:
            return
        user_tool_power = self.current_user['tool']['total_power']
        self.tree.hitpoints -= user_tool_power
        if self.tree.hitpoints <= 0:
            await self.handle_tree_down(interaction)
            return
        self.current_user = next_user
        # Update buttons and embed
        user_1_turn = self.current_user == self.users[0]
        user_2_turn = self.current_user == self.users[1]
        self.button_1.disabled = user_2_turn
        self.button_2.disabled = user_1_turn
        self.button_1.style = (
            discord.ButtonStyle.green if user_1_turn else discord.ButtonStyle.grey
        )
        self.button_2.style = (
            discord.ButtonStyle.green if user_2_turn else discord.ButtonStyle.grey
        )
        embed = self.refresh_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def handle_tree_down(self, interaction):
        embed = discord.Embed(
            title="TIMBER! :evergreen_tree:",
            description=f"{str(self.users[0])} and {str(self.users[1])} successfully chopped down a **{self.tree.height}ft** tree!",
            color=0x573A26,
        )
        for user in self.users:
            reward_string = ""
            drops, bits = distribute_drops(user, self.tree.item_pool, self.tree.height)
            for item in drops:
                reward_string += f"**{item['quantity']}x** {str(item['item'])}\n"
            reward_string += f"**{bits:,}** bits"
            embed.add_field(name=f"{str(user)}'s Drops", value=reward_string)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
        return


# Defines a custom button that contains logic for 'chopping' a tree
class ChopButton1(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.green, label="Heave!")

    async def callback(self, interaction: discord.Interaction):
        view: TreeView = self.view
        await view.handle_chop(interaction, view.users[1])


# Defines a custom button for the
class ChopButton2(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.grey, label="Ho!", disabled=True)

    async def callback(self, interaction: discord.Interaction):
        view: TreeView = self.view
        await view.handle_chop(interaction, view.users[0])


class ForagingCog(commands.Cog, name="Foraging"):
    """Earn foraging xp by cutting down trees. Don't forget to replant!"""

    def __init__(self, bot):
        self.bot = bot

    # Foraging command group
    primary_guild = DiscordGuilds.PRIMARY_GUILD.value
    foraging = app_commands.Group(
        name="foraging",
        description="Commands related to the foraging skill.",
        guild_ids=[primary_guild],
    )

    @foraging.command(name="foraging")
    async def foraging(self, interaction: discord.Interaction):
        """Grab a buddy and chop down a tree."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()
        foraging = user.get_field('foraging')
        
        skill_xp = foraging['xp']
        skill_level = user.xp_to_level(skill_xp)
        embed = Cembed(
            title=f"Foraging level: {skill_level}",
            color=discord.Color.blue(),
            interaction=interaction,
            activity="foraging",
        )
    
        tool_data = Master.get_by_id(foraging['equipped_tool'])

        # If the user does not own an axe
        if not tool:
            embed = discord.Embed(
                description="You need an axe to chop trees!", color=discord.Color.red()
            )
            embed.set_author(name="Slow down, lumberjack.", icon_url=RED_X_URL)
            embed.set_footer(text="Get items from /shop")
            await interaction.response.send_message(embed=embed)
            return

        # Create the view
        view = JoinTreeView(interaction, interaction.user.id)
        # Create an embed to attach the view to
        embed = discord.Embed(
            title=f"Here's a **{view.tree.height}ft** tree :evergreen_tree:",
            description="Find someone to help you!\nUsers: (1/2)",
            color=0x034509,
        )
        embed.set_footer(text="Hint: try chopping trees in a party")
        # Send the response to the command
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(ForagingCog(bot))
