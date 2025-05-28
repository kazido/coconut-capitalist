import discord
import random
from discord.ext import commands
from discord import app_commands, Interaction

from utils.base_cog import BaseCog
from cococap.user import User

# Example skill emojis and skill names (customize as needed)
skills_emojis = {
    "farming": "🌽",
    "foraging": "🌳",
    "fishing": "🐟",
    "mining": "⛏️",
    "combat": "⚔️",
}
skill_list = list(skills_emojis.keys())


class Map:
    grid_size: int = 10

    def __init__(self, user_skill_levels=None):
        self.user_skill_levels = user_skill_levels or {k: 1 for k in skill_list}
        self.map = self._generate_map()

    def _generate_map(self):
        grid = []
        for y in range(self.grid_size):
            row = [
                self._generate_node(skill=random.choice(skill_list)) for _ in range(self.grid_size)
            ]
            grid.append(row)
        return grid

    def _generate_node(self, skill):
        # Higher skill level = higher chance for higher tier
        level = self.user_skill_levels.get(skill, 1)
        # Example: weight tiers by skill level (customize as needed)
        weights = [max(1, 5 - level), max(1, 4 - level), max(1, 3 - level), level]
        tiers = [1, 2, 3, 4]
        tier = random.choices(tiers, weights=weights, k=1)[0]
        emoji = skills_emojis[skill]
        return f"{emoji}{tier}"

    def __str__(self):
        grid_display = "\n".join([" ".join(row) for row in self.map])
        return grid_display


class MapView(discord.ui.View):
    def __init__(self, user, map_obj, x=0, y=0, timeout=180):
        super().__init__(timeout=timeout)
        self.user = user
        self.map_obj = map_obj
        self.x = x
        self.y = y
        self.grid_size = map_obj.grid_size
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if self.y > 0:
            self.add_item(MoveButton("⬆️", self, dx=0, dy=-1))
        if self.y < self.grid_size - 1:
            self.add_item(MoveButton("⬇️", self, dx=0, dy=1))
        if self.x > 0:
            self.add_item(MoveButton("⬅️", self, dx=-1, dy=0))
        if self.x < self.grid_size - 1:
            self.add_item(MoveButton("➡️", self, dx=1, dy=0))

    def get_map_display(self):
        display = []
        for y, row in enumerate(self.map_obj.map):
            row_display = []
            for x, cell in enumerate(row):
                if x == self.x and y == self.y:
                    row_display.append(f"[**{cell}**]")
                else:
                    row_display.append(cell)
            display.append(" ".join(row_display))
        return "\n".join(display)


class MoveButton(discord.ui.Button):
    def __init__(self, label, view, dx, dy):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.dx = dx
        self.dy = dy
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        view = self.view_ref
        if interaction.user.id != view.user.id:
            await interaction.response.send_message("This is not your map!", ephemeral=True)
            return
        view.x += self.dx
        view.y += self.dy
        view.x = max(0, min(view.x, view.grid_size - 1))
        view.y = max(0, min(view.y, view.grid_size - 1))
        view.update_buttons()
        embed = discord.Embed(
            title="Explore the World!",
            description=f"Here's what you found:\n\n{view.get_map_display()}",
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=view)


class Explore(BaseCog):
    """Explore the game world! Level up your skills and discover new areas."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="explore")
    async def explore(self, interaction: Interaction):
        user: User = interaction.extras.get("user")
        # Example: get user skill levels (customize as needed)
        user_skill_levels = getattr(user, "skills", {k: 1 for k in skill_list})
        map_obj = Map(user_skill_levels=user_skill_levels)
        view = MapView(user, map_obj)
        embed = discord.Embed(
            title="Explore the World!",
            description=f"Here's what you found:\n\n{view.get_map_display()}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, view=view)


# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(Explore(bot))
