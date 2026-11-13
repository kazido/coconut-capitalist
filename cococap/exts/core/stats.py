import discord
from discord import Interaction, app_commands
from utils.base_cog import BaseCog
from cococap.user import User
from utils.custom_embeds import CustomEmbed
from utils.menus import PaginationMenu, MenuHandler, DirectMenu


async def display_stats(interaction: Interaction):
    user: User = interaction.extras.get("user")
    stats = await user.stats()  # {name: value}; anything never recorded reads as 0
    farming = await user.skill("farming")
    foraging = await user.skill("foraging")
    fishing = await user.skill("fishing")
    mining = await user.skill("mining")
    combat = await user.skill("combat")

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

    # Minigame Stats
    embed3 = CustomEmbed(
        title=f"{user.name}'s Minigame Stats",
        color=discord.Color.blurple(),
        interaction=interaction,
        activity="stats",
    )
    embed3.add_field(
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
    ).add_field(
        name="Other 🎛️",
        value="\n".join(
            [
                f"Longest Streak: `{stats.get('longest_sq_streak', 0):,}`",
                f"Trivia Wins: `{stats.get('trivia_wins', 0):,}`",
                f"Trivia Games: `{stats.get('trivia_games', 0):,}`",
            ]
        ),
    )

    # Skill Stats
    embed4 = CustomEmbed(
        title=f"{user.name}'s Skill Stats",
        color=discord.Color.orange(),
        interaction=interaction,
        activity="stats",
    )
    embed4.add_field(
        name="Farming 🌽",
        value=f"XP: {farming.xp:,}\nCrops Grown: {farming.stats.crops_grown:,}",
        inline=True,
    )
    embed4.add_field(
        name="Foraging 🌳",
        value=f"XP: {foraging.xp:,}\nTrees Chopped: {foraging.stats.trees_chopped:,}",
        inline=True,
    )
    embed4.add_field(
        name="Fishing 🐟",
        value=f"XP: {fishing.xp:,}\nFish Caught: {fishing.stats.fish_caught:,}",
        inline=True,
    )
    embed4.add_field(
        name="Mining ⛏️",
        value=f"XP: {mining.xp:,}\nLodes Mined: {mining.stats.lodes_mined:,}",
        inline=True,
    )
    embed4.add_field(
        name="Combat ⚔️",
        value=f"XP: {combat.xp:,}\nMonsters Slain: {combat.stats.monsters_slain:,}",
        inline=True,
    )

    handler = MenuHandler(interaction)
    for embed in (embed1, embed2, embed3, embed4):
        handler.add_menu(PaginationMenu(embed))
    menu = handler.get_current()
    await interaction.response.send_message(embed=menu.embed, view=menu)


class Stats(BaseCog):
    """Check out those stats!"""

    @app_commands.command(name="stats", description="Number go up man happy.")
    async def stats(self, interaction: Interaction):
        """Display your various metrics."""
        await display_stats(interaction=interaction)


async def setup(bot):
    # Necessary for the bot.py file to auto load cogs
    await bot.add_cog(Stats())
