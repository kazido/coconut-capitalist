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
    # Remove bot user(s) if present (use a set of known bot IDs if needed)
    bot_id = 1016054559581413457
    query = [u for u in query if get_id(u) != bot_id]
    medals = ["🥇", "🥈", "🥉"]
    embed = discord.Embed(
        title=f"{category.emoji} {category.display_name} Leaderboard",
        color=discord.Color.from_str(category.color),
        description="",
    )
    user_found = False
    lines = []
    for idx, user in enumerate(query[:10], start=1):
        value = get_value(user)
        medal = medals[idx - 1] if idx <= 3 else f"{idx}."
        if get_id(user) == interaction.user.id:
            line = f"{medal} **{get_name(user)} — {value:,} (you)**"
            user_found = True
        else:
            line = f"{medal} {get_name(user)} — {value:,}"
        lines.append(line)
    if not user_found:
        for idx, user in enumerate(query, start=1):
            if get_id(user) == interaction.user.id:
                value = get_value(user)
                line = f"**{idx}. {get_name(user)} — {value:,} (you)**"
                lines.append("\nYour rank:\n" + line)
                break
    embed.description = "\n".join(lines)

    # Add circulation and bot profit for BITS leaderboard
    if category == TopCategories.BITS:
        # Get all users (including bot) for totals
        all_users, _, _, _ = get_leaderboard_query_and_accessors(category)
        all_users = await all_users
        total_purse = sum(u["purse"] for u in all_users)
        total_bank = sum(u["bank"] for u in all_users)
        circulation = total_purse + total_bank
        bot_user = next((u for u in all_users if u["discord_id"] == bot_id), None)
        bot_purse = bot_user["purse"] if bot_user else 0
        embed.add_field(
            name="Current Circulation",
            value=f"There are currently **{circulation - bot_purse:,}** bits in the economy.",
            inline=False,
        )
        embed.set_footer(text=f"The house has made: {bot_purse:,} bits")
    return embed


class LeaderboardCog(commands.Cog):
    @app_commands.command(name="top", description="See the top 10 players in a category!")
    @app_commands.describe(category="The leaderboard category to view")
    async def top(self, interaction: Interaction, category: TopCategories = TopCategories.BITS):
        embed = await build_leaderboard_embed(interaction, category)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(LeaderboardCog())
