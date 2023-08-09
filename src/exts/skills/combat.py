import discord
import random
import datetime

from random import randint

from discord import app_commands, ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
from discord.interactions import Interaction

from src.constants import RED_X_URL, DiscordGuilds
from src.utils.members import *
from src.utils.items import *
from src.utils.utils import distribute_drops

from logging import getLogger

log = getLogger(__name__)
log.setLevel(10)


map_1 = [
  [2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
  [2, 0, 0, 0, 0, 0, 0, 0, 0, 2],
  [2, 0, 3, 0, 0, 0, 0, 3, 0, 2],
  [2, 0, 0, 0, 0, 0, 0, 0, 0, 2],
  [2, 0, 0, 0, 0, 0, 0, 0, 0, 2],
  [2, 0, 0, 0, 0, 0, 0, 0, 0, 2],
  [2, 0, 0, 0, 0, 0, 0, 0, 0, 2],
  [2, 0, 3, 0, 0, 0, 0, 3, 0, 2],
  [2, 0, 0, 0, 0, 0, 0, 0, 0, 2],
  [2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
]

class Dungeon:
    
    values = {
        0: "➕",
        1: "🧙",
        2: "✖️",
        3: "🧟",
        4: "🌟",
    }

    def __init__(self, level_map):
        # Assuming player starts at the center of the dungeon.
        self.level_map = level_map
        self.row_size = len(self.level_map)
        self.col_size = len(self.level_map[0])
        self.player_pos = [self.row_size // 2, self.col_size // 2]

    def move(self, dx, dy):
        new_x = self.player_pos[0] + dx
        new_y = self.player_pos[1] + dy

        # Check if the new position is within the boundaries and isn't a wall.
        if (0 <= new_x < self.col_size and
            0 <= new_y < self.row_size and
            self.level_map[new_x][new_y] == 0):
            self.player_pos = [new_x, new_y]
        else:
            log.info("Player tried to move out of bounds")

    def render_grid_around_player(self):
        grid = ""

        for i in range(-3, 4):
            row = ""
            for j in range(-3, 4):
                x, y = self.player_pos[0] + i, self.player_pos[1] + j
                if 0 <= x < self.col_size and 0 <= y < self.row_size:
                    if i == 0 and j == 0:
                        row += self.values[1]
                    else:
                        row += self.values[self.level_map[x][y]]
                else:
                    row += self.values[0]
            row += "\n"
            grid += row

        return grid

    def display(self):
        grid = self.render_grid_around_player()
        return grid



class CombatView(View):
    def __init__(self, interaction, user_id):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.user = get_user_data(user_id, backrefs=True)
        # Generate a tree based on the user
        area = self.user["area_id"]
        difficulty = area["difficulty"]

    async def on_timeout(self) -> None:
        embed = discord.Embed(
            title="Really?",
            description="The enemies found you asleep on the floor... :zzz:",
            color=discord.Color.dark_grey(),
        )
        await self.interaction.edit_original_response(embed=embed, view=None)


class GridView(View):
    def __init__(self, level_map):
        super().__init__()
        self.dungeon = Dungeon(level_map=level_map)

    def create_embed(self):
        embed = discord.Embed(
            title="Sample Combat Embed Title",
            description=self.dungeon.display(),
            color=discord.Color.light_grey(),
        )
        return embed


class DungeonView(GridView):
    def __init__(self, level_map):
        super().__init__(level_map)
        self.action_points = 5
        self.embed = self.create_embed()
        self.create_buttons()

    def create_buttons(self):
        directions = [
            ("↖️", -1, -1),
            ("⬆️", -1, 0),
            ("↗️", -1, 1),
            ("⬅️", 0, -1),
            ("✅", 0, 0),
            ("➡️", 0, 1),
            ("↙️", 1, -1),
            ("⬇️", 1, 0),
            ("↘️", 1, 1),
        ]

        for index, (emoji, row_diff, col_diff) in enumerate(directions):
            button = discord.ui.Button(
                emoji=emoji, style=discord.ButtonStyle.gray, row=index // 3
            )
            button.callback = self.create_move_callback(row_diff, col_diff)
            self.add_item(button)

    def create_move_callback(self, row_diff, col_diff):
        async def callback(interaction: discord.Interaction):
            # If the user is out of action points, our turn is over
            if self.action_points <= 0:
                await interaction.response.send_message(
                    "No movement points left!", ephemeral=True
                )
                return
            # If the row and column are the confirm button's coordinates
            if row_diff == 0 and col_diff == 0:
                await interaction.response.edit_message(
                    view=AttackView(player_pos=self.dungeon.player_pos)
                )
                return
            

            new_row = self.dungeon.player_pos[0] + row_diff
            new_col = self.dungeon.player_pos[1] + col_diff

            # Validate new position
            if 0 <= new_row < self.dungeon.row_size and 0 <= new_col < self.dungeon.col_size:
                self.dungeon.player_pos = (new_row, new_col)
                self.action_points -= 1
                await interaction.response.edit_message(
                    embed=self.create_embed()
                )
            else:
                await interaction.response.send_message("Invalid move!", ephemeral=True)

            if self.action_points <= 0:
                for button in self.children:
                    button.disabled = True

        return callback


class AttackView(GridView):
    def __init__(self, player_pos, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attack_grid = self.render_grid()
        self.embed = self.create_embed()
        self.player_pos = player_pos

    @discord.ui.button(label="Light Attack", style=ButtonStyle.gray)
    async def light_attack(self, button: Button, interaction: Interaction):
        self.perform_attack([self.player_pos])
        await self.update_embed(interaction)

    @discord.ui.button(label="Medium Attack", style=ButtonStyle.gray)
    async def medium_attack(self, button: Button, interaction: Interaction):
        self.perform_attack(self.get_adjacent_squares(self.player_pos))
        await self.update_embed(interaction)

    @discord.ui.button(label="Heavy Attack", style=ButtonStyle.gray)
    async def heavy_attack(self, button: Button, interaction: Interaction):
        self.perform_attack(self.get_all_squares())
        await self.update_embed(interaction)

    def get_adjacent_squares(self, position):
        x, y = position
        adjacent = []
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                if 0 <= x + dx < self.grid_size and 0 <= y + dy < self.grid_size:
                    adjacent.append((x + dx, y + dy))
        return adjacent

    def get_all_squares(self):
        return [(x, y) for x in range(self.grid_size) for y in range(self.grid_size)]

    def perform_attack(self, attack_positions):
        attack_emoji = "💥"
        for pos in attack_positions:
            print(self.attack_grid)
            self.attack_grid[pos[0]][pos[1]] = attack_emoji

    def render_attack(self):
        return "\n".join("".join(row) for row in self.attack_grid)

    def create_embed(self):
        embed = discord.Embed(
            title="Choose your attack!",
            description=self.render_attack(),
            timestamp=datetime.datetime.now(),
        )
        return embed

    async def update_embed(self, interaction: Interaction):
        self.embed.description = self.render_attack()
        await interaction.response.edit_message(embed=self.embed)


class CombatCog(commands.Cog, name="Combat"):
    """Fight, fight, fight!"""

    def __init__(self, bot):
        self.bot = bot

    # Combat command group
    primary_guild = DiscordGuilds.PRIMARY_GUILD.value
    combat = app_commands.Group(
        name="combat",
        description="Commands related to the combat skill.",
        guild_ids=[primary_guild],
    )

    @combat.command(name="fight", description="Fight, fight, fight!")
    async def fight(self, interaction: discord.Interaction):
        view: GridView = DungeonView(map_1)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(CombatCog(bot))
