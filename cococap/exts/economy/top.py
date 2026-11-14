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

    def format(self, value: int) -> str:
        """A score with its unit, so the board says what is being counted: "1,250 bits", "Lv 7 (1,250 xp)"."""
        if self.key.startswith("skill:"):
            from cococap.user import User

            return f"Lv {User.xp_to_level(value)} ({value:,} xp)"
        return f"{value:,} {self.unit}"

    @property
    def unit(self) -> str:
        return {"bits": "bits", "luckbucks": "luckbucks", "stat:drops_claimed": "drops claimed"}.get(self.key, "")


MEDALS = ["🥇", "🥈", "🥉"]


async def leaderboard_view(category: TopCategories, caller_id: int) -> tuple[str, str | None, str | None]:
    """(board text, circulation line, house footer) for a category. The last two are bits-only."""
    # The house account (the bot's own user) is hidden from every board.
    top = await queries.leaderboard(category.key, limit=10, exclude=BOT_ID)
    lines, caller_listed = [], False
    for entry in top:
        medal = MEDALS[entry.rank - 1] if entry.rank <= 3 else f"{entry.rank}."
        if entry.discord_id == caller_id:
            caller_listed = True
            lines.append(f"{medal} **{entry.name} — {category.format(entry.value)} (you)**")
        else:
            lines.append(f"{medal} {entry.name} — {category.format(entry.value)}")
    if not caller_listed:
        mine = await queries.position_of(category.key, caller_id, exclude=BOT_ID)
        if mine:
            lines.append(f"\nYour rank:\n**{mine.rank}. {mine.name} — {category.format(mine.value)} (you)**")
    board = "\n".join(lines) or "Nobody is on this board yet."
    from cococap.user import User

    if category == TopCategories.BITS:  # the casino pays in luckbucks now, so the house has no bits to speak of
        circulation = await queries.bits_in_circulation(exclude=BOT_ID)
        return board, f"There are currently **{circulation:,}** bits in the economy.", None
    if category == TopCategories.LUCKBUCKS:
        house = await User.get(BOT_ID)
        return board, None, f"The house has made: {house.luckbucks:,} luckbucks"
    return board, None, None


async def build_leaderboard_embed(interaction: Interaction, category: TopCategories):
    board, circulation, footer = await leaderboard_view(category, interaction.user.id)
    embed = discord.Embed(
        title=f"{category.emoji} {category.display_name} Leaderboard",
        color=discord.Color.from_str(category.color),
        description=board,
    )
    if circulation:
        embed.add_field(name="Current Circulation", value=circulation, inline=False)
    if footer:
        embed.set_footer(text=footer)
    return embed


class LeaderboardCog(commands.Cog):
    @app_commands.command(name="top", description="See the top 10 players in a category!")
    @app_commands.describe(category="the leaderboard category to view")
    async def top(self, interaction: Interaction, category: TopCategories = TopCategories.BITS):
        from cococap.screens import open_screen

        await open_screen(interaction, "top", category=category)


async def setup(bot):
    await bot.add_cog(LeaderboardCog())
