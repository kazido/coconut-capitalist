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
from src import instance

from logging import getLogger

log = getLogger(__name__)
log.setLevel(10)


map_1 = [
    [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 5, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
]

map_2 = [
    [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 5, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 2, 2, 2, 2, 6, 2, 2, 2, 2, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2],
    [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2],
]


class Player:
    def __init__(self, action_points, movement_power=1) -> None:
        self.action_points = action_points
        self.movement_power = movement_power
        self.pos = []


class Dungeon:
    mapping_values = {
        0: str(instance.get_emoji(1160332976924663879)),  # out of bounds
        1: str(instance.get_emoji(1160322480532103288)),  # dungeon tile
        2: str(instance.get_emoji(1160329891129065532)),  # dungeon wall
        3: str(instance.get_emoji(1160449921992900618)),  # player icon
        4: str(instance.get_emoji(1160449902069960805)),  # ally icon
        5: str(instance.get_emoji(1160440231233859604)),  # enemy icon
        6: str(instance.get_emoji(1160439007726010461)),  # boss door
    }

    def __init__(self, level_map, spawn_point=None, vision_level: int = 5):
        self.level_map = level_map
        self.row_size = len(self.level_map)
        self.col_size = len(self.level_map[0])
        self.view_x = self.view_y = vision_level
        self.spawn_x = self.row_size // 2
        self.spawn_y = self.col_size // 2
        if spawn_point:
            self.spawn_x = spawn_point[0]
            self.spawn_y = spawn_point[1]
        self.players = []

    def add_player(self, player: Player):
        player.pos = [self.spawn_x + len(self.players), self.spawn_y]
        self.players.append(player)

    def render_map_around_player(self, player: Player):
        map_string = ""

        for other_player in self.players:
            if other_player != player:
                self.level_map[other_player.pos[1]][other_player.pos[0]] = 4
        
        for i in range(-self.view_y, self.view_y):
            row = ""
            for j in range(-self.view_x, self.view_x):
                x, y = player.pos[0] + i, player.pos[1] + j
                # render everything within the size of the 2d array
                if 0 <= x < self.col_size and 0 <= y < self.row_size:
                    row += self.mapping_values[self.level_map[x][y]]
                # everything outside of the 'map' should render blank
                else:
                    row += self.mapping_values[0]
            row += "\n"
            map_string += row

        return map_string

    def display(self, player: Player):
        map_string = self.render_map_around_player(player)
        return map_string


class CombatView(View):
    def __init__(self, interaction, user_id):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.user = get_user_data(user_id, backrefs=True)

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
            title="Dungeon Title Sample",
            description=self.dungeon.display(),
            color=discord.Color.light_grey(),
        )
        return embed


class DungeonView(GridView):
    def __init__(self, level_map):
        super().__init__(level_map)
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
                emoji=emoji, style=discord.ButtonStyle.blurple, row=index // 3
            )
            button.callback = self.create_move_callback(row_diff, col_diff)
            self.add_item(button)

    def create_move_callback(self, player: Player, row_diff, col_diff):
        async def callback(interaction: discord.Interaction):
            # If the user is out of action points, our turn is over
            if player.action_points <= 0:
                await interaction.response.send_message(
                    "No movement points left!", ephemeral=True
                )
                return
            # If the row and column are the confirm button's coordinates
            if row_diff == 0 and col_diff == 0:
                # TODO: handle confirm button interaction
                await interaction.response.edit_message(
                    view=AttackView(player_pos=0)
                )
                return

            new_row = player.pos[0] + row_diff
            new_col = player.pos[1] + col_diff

            # Validate new position
            if (
                1 <= new_row < self.dungeon.row_size - 1
                and 1 <= new_col < self.dungeon.col_size - 1
            ):
                self.dungeon.player_pos = (new_row, new_col)
                self.action_points -= 1
                await interaction.response.edit_message(embed=self.create_embed())
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
        view: GridView = DungeonView(map_2)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(CombatCog(bot))
