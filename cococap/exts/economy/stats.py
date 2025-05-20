import discord
from discord import Interaction, app_commands
from utils.base_cog import BaseCog
from cococap.user import User
from utils.custom_embeds import CustomEmbed


class StatsPaginator(discord.ui.View):
    def __init__(
        self, interaction: Interaction, pages: list[discord.Embed], *, timeout: float = 60
    ):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.pages = pages
        self.current = 0
        self.message: discord.Message = None
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        if len(self.pages) > 1:
            self.add_item(PrevButton(self))
            self.add_item(NextButton(self))

    async def show_page(self, interaction: Interaction = None):
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)


class PrevButton(discord.ui.Button):
    def __init__(self, paginator: StatsPaginator):
        super().__init__(style=discord.ButtonStyle.secondary, label="Previous", emoji="⬅️")
        self.paginator = paginator

    async def callback(self, interaction: Interaction):
        self.paginator.current = (self.paginator.current - 1) % len(self.paginator.pages)
        await self.paginator.show_page(interaction)


class NextButton(discord.ui.Button):
    def __init__(self, paginator: StatsPaginator):
        super().__init__(style=discord.ButtonStyle.secondary, label="Next", emoji="➡️")
        self.paginator = paginator

    async def callback(self, interaction: Interaction):
        self.paginator.current = (self.paginator.current + 1) % len(self.paginator.pages)
        await self.paginator.show_page(interaction)


async def display_stats(interaction: Interaction):
    user: User = interaction.extras.get("user")
    stats = user.get_field("statistics")
    farming = user.get_field("farming")
    foraging = user.get_field("foraging")
    fishing = user.get_field("fishing")
    mining = user.get_field("mining")
    combat = user.get_field("combat")

    pages = []
    # General Stats
    embed1 = CustomEmbed(
        title=f"{user.name}'s General Stats",
        color=discord.Color.dark_purple(),
        interaction=interaction,
        activity="stats",
    )
    embed1.add_field(
        name="General Stats 🔢",
        value="\n".join(
            [
                f"Drops Claimed: `{stats.get('drops_claimed', 0):,}`",
                f"Bits Earned: `{stats.get('bits_earned', 0):,}`",
                f"Bits Lost: `{stats.get('bits_lost', 0):,}`",
                f"Tokens Earned: `{stats.get('tokens_earned', 0):,}`",
                f"Luckbucks Earned: `{stats.get('luckbucks_earned', 0):,}`",
                f"Times Begged: `{stats.get('times_begged', 0):,}`",
                f"Withdraws: `{stats.get('withdraws', 0):,}`",
                f"Deposits: `{stats.get('deposits', 0):,}`",
                f"Claimed Work: `{stats.get('claimed_work', 0):,}`",
                f"Claimed Daily: `{stats.get('claimed_daily', 0):,}`",
                f"Claimed Weekly: `{stats.get('claimed_weekly', 0):,}`",
            ]
        ),
        inline=False,
    )
    pages.append(embed1)

    # Gambling Stats
    embed2 = CustomEmbed(
        title=f"{user.name}'s Gambling Stats",
        color=discord.Color.green(),
        interaction=interaction,
        activity="stats",
    )
    embed2.add_field(
        name="Highlow 🪙",
        value="\n".join(
            [
                f"Wins: `{stats.get('hl_wins', 0):,}`",
                f"Longest Streak: `{stats.get('longest_hl_streak', 0):,}`",
                f"Longest Loss Streak: `{stats.get('longest_hl_loss_streak', 0):,}`",
                f"Biggest Win: `{stats.get('biggest_hl_win', 0):,}`",
                f"Biggest Loss: `{stats.get('biggest_hl_loss', 0):,}`",
            ]
        ),
    ).add_field(
        name="Blackjack 🃏",
        value="\n".join(
            [
                f"Wins: `{stats.get('blackjack_wins', 0):,}`",
                f"Hits: `{stats.get('blackjack_hits', 0):,}`",
                f"Stands: `{stats.get('blackjack_stands', 0):,}`",
                f"Busts: `{stats.get('blackjack_busts', 0):,}`",
                f"Folds: `{stats.get('blackjack_folds', 0):,}`",
            ]
        ),
    )
    pages.append(embed2)

    # Minigame Stats
    embed3 = CustomEmbed(
        title=f"{user.name}'s Minigame Stats",
        color=discord.Color.blurple(),
        interaction=interaction,
        activity="stats",
    )
    embed3.add_field(
        name="Sequence 🟥",
        value="\n".join(
            [
                f"Longest Streak: `{stats.get('longest_sq_streak', 0):,}`",
            ]
        ),
    ).add_field(
        name="Unscramble 📄",
        value="\n".join(
            [
                f"Current Streak: `{stats.get('unscramble_streak', 0):,}`",
                f"Longest Streak: `{stats.get('longest_unscramble_streak', 0):,}`",
            ]
        ),
    ).add_field(
        name="Flashcard 🔢",
        value="\n".join(
            [
                f"Current Streak: `{stats.get('flashcard_streak', 0):,}`",
                f"Longest Streak: `{stats.get('longest_flashcard_streak', 0):,}`",
            ]
        ),
    )
    pages.append(embed3)

    # Skill Stats
    embed4 = CustomEmbed(
        title=f"{user.name}'s Skill Stats",
        color=discord.Color.orange(),
        interaction=interaction,
        activity="stats",
    )
    embed4.add_field(
        name="Farming 🌽",
        value=f"XP: {farming.get('xp', 0):,}\nCrops Grown: {farming.get('crops_grown', 0):,}",
        inline=True,
    )
    embed4.add_field(
        name="Foraging 🌳",
        value=f"XP: {foraging.get('xp', 0):,}\nTrees Chopped: {foraging.get('trees_chopped', 0):,}",
        inline=True,
    )
    embed4.add_field(
        name="Fishing 🐟",
        value=f"XP: {fishing.get('xp', 0):,}\nFish Caught: {fishing.get('fish_caught', 0):,}",
        inline=True,
    )
    embed4.add_field(
        name="Mining ⛏️",
        value=f"XP: {mining.get('xp', 0):,}\nLodes Mined: {mining.get('lodes_mined', 0):,}",
        inline=True,
    )
    embed4.add_field(
        name="Combat ⚔️",
        value=f"XP: {combat.get('xp', 0):,}\nMonsters Slain: {combat.get('monsters_slain', 0):,}",
        inline=True,
    )
    pages.append(embed4)

    view = StatsPaginator(interaction, pages)
    await interaction.response.send_message(embed=view.pages[view.current], view=view)


class Stats(BaseCog):
    """Check out those stats!"""

    @app_commands.command(name="stats", description="Number go up man happy.")
    async def stats(self, interaction: Interaction):
        """Display your various metrics."""
        await display_stats(interaction=interaction)


async def setup(bot):
    # Necessary for the bot.py file to auto load cogs
    await bot.add_cog(Stats())
