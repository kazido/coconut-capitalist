import discord

from enum import Enum
from discord import app_commands, Interaction
from discord.ext import commands

from cococap.constants import BOT_ID
from cococap.db import queries


class TopCategories(Enum):
    # value, emoji, display name, leaderboard key (see cococap.db.queries.leaderboard), color
    BITS = ("💸", "Bits", "bits", "0xbbd6ed")
    LUCKBUCKS = ("🍀", "Luckbucks", "luckbucks", "0x47d858")
    FARMING = ("🌽", "Farming", "skill:farming", "0x2f919e")
    FORAGING = ("🌳", "Foraging", "skill:foraging", "0x2f9e47")
    FISHING = ("🐟", "Fishing", "skill:fishing", "0x2f3a9e")
    MINING = ("⛏️", "Mining", "skill:mining", "0x9e492f")
    COMBAT = ("⚔️", "Combat", "skill:combat", "0x9e2f2f")
    # SHEPHERDING = ("🐑", "Shepherding", "skill:shepherding", "0x5f2f9e")  # TO BE ADDED
    DROPS = ("📦", "Drops", "stat:drops_claimed", "0x8b9a9e")

    def __new__(cls, emoji, name, key: str, color):
        obj = object.__new__(cls)
        obj._value_ = name.lower()
        obj.emoji = emoji
        obj.display_name = name
        obj.key = key
        obj.color = color
        return obj

    @classmethod
    def from_name(cls, name: str):
        return cls(name.lower())


MEDALS = ["🥇", "🥈", "🥉"]


async def build_leaderboard_embed(interaction: Interaction, category: TopCategories):
    # The house account (the bot's own user) is hidden from every board.
    top = await queries.leaderboard(category.key, limit=10, exclude=BOT_ID)
    embed = discord.Embed(
        title=f"{category.emoji} {category.display_name} Leaderboard",
        color=discord.Color.from_str(category.color),
    )
    lines = []
    caller_listed = False
    for entry in top:
        medal = MEDALS[entry.rank - 1] if entry.rank <= 3 else f"{entry.rank}."
        if entry.discord_id == interaction.user.id:
            caller_listed = True
            lines.append(f"{medal} **{entry.name} — {entry.value:,} (you)**")
        else:
            lines.append(f"{medal} {entry.name} — {entry.value:,}")
    if not caller_listed:
        mine = await queries.position_of(category.key, interaction.user.id, exclude=BOT_ID)
        if mine:
            lines.append(f"\nYour rank:\n**{mine.rank}. {mine.name} — {mine.value:,} (you)**")
    embed.description = "\n".join(lines) or "Nobody is on this board yet."

    if category == TopCategories.BITS:
        circulation = await queries.bits_in_circulation(exclude=BOT_ID)
        embed.add_field(
            name="Current Circulation",
            value=f"There are currently **{circulation:,}** bits in the economy.",
            inline=False,
        )
        from cococap.user import User

        house = await User.get(BOT_ID)
        embed.set_footer(text=f"The house has made: {house.purse:,} bits")
    return embed


class LeaderboardCog(commands.Cog):
    @app_commands.command(name="top", description="See the top 10 players in a category!")
    @app_commands.describe(category="the leaderboard category to view")
    async def top(self, interaction: Interaction, category: TopCategories = TopCategories.BITS):
        embed = await build_leaderboard_embed(interaction, category)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(LeaderboardCog())
