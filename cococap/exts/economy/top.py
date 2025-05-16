import discord

from enum import Enum
from discord import app_commands, Interaction
from discord.ext import commands
from cococap.models import UserDocument

FIRST_PLACE_ANSI_PREFIX = "\u001b[0;37m"
SECOND_PLACE_ANSI_PREFIX = "\u001b[0;33m"
THIRD_PLACE_ANSI_PREFIX = "\u001b[0;31m"
OTHER_PLACE_ANSI_PREFIX = "\u001b[0;30m"
RESET_POSTFIX = "\u001b[0m"


class TopCategories(Enum):
    BITS = ("💸", "Bits", "purse", "0xbbd6ed")
    LUCKBUCKS = ("🍀", "Luckbucks", "luckbucks", "0x47d858")
    FARMING = ("🌽", "Farming", "farming.xp", "0x2f919e")
    FORAGING = ("🌳", "Foraging", "foraging.xp", "0x2f9e47")
    FISHING = ("🐟", "Fishing", "fishing.xp", "0x2f3a9e")
    MINING = ("⛏️", "Mining", "mining.xp", "0x9e492f")
    COMBAT = ("⚔️", "Combat", "combat.xp", "0x9e2f2f")
    # SHEPHERDING = ("🐑", "Shepherding", ['shepherding'], "0x5f2f9e")  # TO BE ADDED
    DROPS = ("📦", "Drops", "drops_claimed", "0x8b9a9e")

    def __new__(cls, emoji, name, column: str, color):
        obj = object.__new__(cls)
        obj._value_ = name.lower()
        obj.emoji = emoji
        obj.display_name = name
        obj.column = column
        obj.color = color
        return obj

    @classmethod
    def from_name(cls, name: str):
        return cls(name.lower())


LEADERBOARD_CATEGORIES = [
    TopCategories.BITS,
    TopCategories.LUCKBUCKS,
    TopCategories.DROPS,
    # Add more categories as needed
]


class LeaderboardView(discord.ui.View):
    def __init__(self, author_id, current_category, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.author_id = author_id
        self.current_category = current_category
        self.category_index = LEADERBOARD_CATEGORIES.index(current_category)
        self.add_item(PrevBoardButton(self))
        self.add_item(NextBoardButton(self))

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author_id


class PrevBoardButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label="<", style=discord.ButtonStyle.blurple)
        self.view_ref = view

    async def callback(self, interaction: Interaction):
        view = self.view_ref
        idx = (view.category_index - 1) % len(LEADERBOARD_CATEGORIES)
        new_category = LEADERBOARD_CATEGORIES[idx]
        view.category_index = idx
        view.current_category = new_category
        await update_leaderboard_message(interaction, new_category, view)


class NextBoardButton(discord.ui.Button):
    def __init__(self, view):
        super().__init__(label=">", style=discord.ButtonStyle.blurple)
        self.view_ref = view

    async def callback(self, interaction: Interaction):
        view = self.view_ref
        idx = (view.category_index + 1) % len(LEADERBOARD_CATEGORIES)
        new_category = LEADERBOARD_CATEGORIES[idx]
        view.category_index = idx
        view.current_category = new_category
        await update_leaderboard_message(interaction, new_category, view)


async def update_leaderboard_message(
    interaction: Interaction, category: TopCategories, view: LeaderboardView
):
    embed = await build_leaderboard_embed(interaction, category)
    await interaction.response.edit_message(embed=embed, view=view)


def get_leaderboard_query_and_accessors(category: TopCategories):
    if category == TopCategories.BITS:
        pipeline = [
            {"$addFields": {"sum_value": {"$add": ["$purse", "$bank"]}}},
            {"$sort": {"sum_value": -1}},
        ]
        return (
            UserDocument.aggregate(pipeline).to_list(),
            lambda u: u["purse"] + u["bank"],
            lambda u: u["discord_id"],
            lambda u: u["name"],
        )
    else:
        return (
            UserDocument.find().sort((category.column, -1)).to_list(),
            lambda u: getattr(u, category.column),
            lambda u: u.discord_id,
            lambda u: u.name,
        )


async def build_leaderboard_embed(interaction: Interaction, category: TopCategories):
    query, get_value, get_id, get_name = get_leaderboard_query_and_accessors(category)
    query = await query
    for user in query:
        if get_id(user) == 1016054559581413457:
            query.remove(user)
            break
    embed = discord.Embed(
        title=f"{category.display_name} Leaderboard",
        color=discord.Color.from_str(category.color),
        description="",
    )
    user_found = False
    lines = []
    for idx, user in enumerate(query[:10], start=1):
        value = get_value(user)
        line = f"`{idx}.` {get_name(user)} - `{value:,}`"
        if get_id(user) == interaction.user.id:
            line = f"`{idx}.` **{get_name(user)}** - `{value:,}` [YOU]"
            user_found = True
        lines.append(line)
    if not user_found:
        for idx, user in enumerate(query, start=1):
            if get_id(user) == interaction.user.id:
                value = get_value(user)
                line = f"**{idx}. {get_name(user)} - {value:,}**"
                lines.append("\nYour rank:\n" + line)
                break
    embed.description = "\n".join(lines)
    return embed


async def send_leaderboard(interaction: Interaction, category: TopCategories):
    embed = await build_leaderboard_embed(interaction, category)
    view = LeaderboardView(interaction.user.id, category)
    await interaction.response.send_message(embed=embed, view=view)


class LeaderboardCog(commands.Cog):
    @app_commands.command(name="top", description="See the top 10 players in each category!")
    @app_commands.describe(category="category of leaderboard")
    async def top(self, interaction: Interaction, category: TopCategories = TopCategories.BITS):
        await send_leaderboard(interaction, category)


async def setup(bot):
    await bot.add_cog(LeaderboardCog())
