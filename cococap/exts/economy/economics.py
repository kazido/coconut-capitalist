import math
import random
import discord
import randfacts
import time

from random import randint
from discord import app_commands, Interaction
from game_data.converters.data_converter import fetch

from utils.utils import timestamp_to_digital
from cococap.user import User, Cooldowns
from utils.custom_embeds import CustomEmbed, ErrorEmbed
from utils.base_cog import BaseCog
from utils.utils import validate_bits

from cococap.constants import TOO_RICH_TITLES

MAX_BALANCE = 10_000

PYRAMID_SCHEME_TITLES = [
    "Pyramid schemes are not allowed",
    "Trying to break the system, are we?",
    "This is what we call pulling a *Botski*",
]


def get_button_arguments(user: User, cooldown: Cooldowns):
    last_used = user.get_cooldown(cooldown)
    now = time.time()

    ready = ((now - last_used) / 3600) >= cooldown.value

    cooldown_timestamp = timestamp_to_digital((last_used + float(cooldown.value * 3600)) - now)

    label = cooldown.name.capitalize() if ready else cooldown_timestamp
    disabled = False if ready else True
    style = discord.ButtonStyle.blurple if ready else discord.ButtonStyle.gray
    emoji = "✅" if ready else "❌"
    return {"label": label, "style": style, "disabled": disabled, "emoji": emoji}


class WorkButton(discord.ui.Button):
    def __init__(self, user: User):
        super().__init__()
        self.update(user)

    def update(self, user: User):
        args = get_button_arguments(user=user, cooldown=Cooldowns.WORK)
        self.label = args.get("label")
        self.style = args.get("style")
        self.disabled = args.get("disabled")
        self.emoji = args.get("emoji")

    async def callback(self, interaction):
        user: User = self.view.user
        # Put the command on cooldown!
        await user.set_cooldown(Cooldowns.WORK)
        await user.inc_stat("claimed_work")
        self.update(user)

        rank = fetch("ranks." + str(user.get_field("rank")))

        self.label = f"+{int(rank.wage):,} bits"
        self.emoji = "💸"
        await user.add_bits(int(rank.wage))
        return await interaction.response.edit_message(view=self.view)


class DailyButton(discord.ui.Button):
    def __init__(self, user: User):
        super().__init__()
        self.update(user)

    def update(self, user: User):
        args = get_button_arguments(user=user, cooldown=Cooldowns.DAILY)
        self.label = args.get("label")
        self.style = args.get("style")
        self.disabled = args.get("disabled")
        self.emoji = args.get("emoji")

    async def callback(self, interaction):
        user: User = self.view.user
        embed = self.view.embed
        await user.set_cooldown(Cooldowns.DAILY)
        await user.inc_stat("claimed_daily")
        self.update(user)

        # Calculate and add bank interest rate
        interest = 0.003 + 0.027 * (math.e ** (-(user.get_field("bank") / 20_000_000)))
        bonus = round(user.get_field("bank") * interest)
        await user.add_bank(amount=int(bonus))

        # Update the embed
        embed.add_field(name="Random Fact", value=f"{randfacts.get_fact()}")
        embed.add_field(name="Bank Interest", value=f"🏦 +{bonus:,} bits")

        # Put the command on cooldown!
        self.label = f"+1 tokens"
        self.emoji = "🪙"
        await user.add_tokens(amount=1)
        await interaction.response.edit_message(embed=embed, view=self.view)
        return await super().callback(interaction)


class WeeklyButton(discord.ui.Button):
    def __init__(self, user: User):
        super().__init__()
        self.update(user)

    def update(self, user: User):
        args = get_button_arguments(user=user, cooldown=Cooldowns.WEEKLY)
        self.label = args.get("label")
        self.style = args.get("style")
        self.disabled = args.get("disabled")
        self.emoji = args.get("emoji")

    async def callback(self, interaction):
        user: User = self.view.user
        await user.set_cooldown(Cooldowns.WEEKLY)
        await user.inc_stat("claimed_weekly")
        self.update(user)

        self.label = f"+7 luckbucks"
        self.emoji = "🍀"
        await user.add_luckbucks(amount=7)
        await interaction.response.edit_message(view=self.view)
        return await super().callback(interaction)


class CheckInMenu(discord.ui.View):
    def __init__(self, interaction: Interaction, *, timeout: float | None = 180):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.user: User = interaction.extras.get("user")
        self.embed: CustomEmbed = CustomEmbed(
            title="Check-ins",
            desc="Come back often to claim your rewards.",
            color=discord.Color.dark_blue(),
            interaction=interaction,
            activity="checking in",
        )

        self.add_item(WorkButton(user=self.user))
        self.add_item(DailyButton(user=self.user))
        self.add_item(WeeklyButton(user=self.user))

    async def interaction_check(self, interaction):
        """Checks to see if a command is currently on cooldown. Returns boolean result and cooldown, if any"""
        return interaction.user == self.interaction.user


async def display_profile(interaction: Interaction):
    user: User = interaction.extras.get("user")
    rank = fetch("ranks." + str(user.get_field("rank")))
    if user.get_field("name") != interaction.user.display_name:
        await user.set_field("name", interaction.user.display_name)

    embed = CustomEmbed(
        title=f"You are: `{rank.display_name}`",
        color=discord.Color.blue(),
        interaction=interaction,
        activity="profile",
    )

    embed.add_field(
        name="Balances",
        value=f":money_with_wings: **BITS**: {await user.get_bits():,}\n"
        f":bank: **BANK**: {user.get_field('bank'):,}\n"
        f":four_leaf_clover: **LUCKBUCKS**: {user.get_field('luckbucks'):,}\n"
        f":coin: **TOKENS**: {user.get_field('tokens'):,}",
    )
    embed.set_thumbnail(url=interaction.user.display_avatar)
    await interaction.response.send_message(embed=embed)


async def display_stats(interaction: Interaction):
    user: User = interaction.extras.get("user")
    stats = user.get_field("statistics")
    farming = user.get_field("farming")
    foraging = user.get_field("foraging")
    fishing = user.get_field("fishing")
    mining = user.get_field("mining")
    combat = user.get_field("combat")

    embed = CustomEmbed(
        title=f"{user.name}'s Stats",
        color=discord.Color.dark_purple(),
        interaction=interaction,
        activity="stats",
    )

    # Group statistics for display
    general_stats = [
        f"Drops Claimed: {stats.get('drops_claimed', 0):,}",
        f"Bits Earned: {stats.get('bits_earned', 0):,}",
        f"Bits Lost: {stats.get('bits_lost', 0):,}",
        f"Tokens Earned: {stats.get('tokens_earned', 0):,}",
        f"Luckbucks Earned: {stats.get('luckbucks_earned', 0):,}",
        f"Times Begged: {stats.get('times_begged', 0):,}",
        f"Withdraws: {stats.get('withdraws', 0):,}",
        f"Deposits: {stats.get('deposits', 0):,}",
        f"Claimed Work: {stats.get('claimed_work', 0):,}",
        f"Claimed Daily: {stats.get('claimed_daily', 0):,}",
        f"Claimed Weekly: {stats.get('claimed_weekly', 0):,}",
    ]
    gambling_stats = [
        f"Gambles Done: {stats.get('gambles_done', 0):,}",
        f"Longest HL Streak: {stats.get('longest_hl_streak', 0):,}",
        f"HL Win Streak: {stats.get('hl_win_streak', 0):,}",
        f"HL Wins: {stats.get('hl_wins', 0):,}",
        f"Longest HL Loss Streak: {stats.get('longest_hl_loss_streak', 0):,}",
        f"HL Loss Streak: {stats.get('hl_loss_streak', 0):,}",
        f"Biggest HL Win: {stats.get('biggest_hl_win', 0):,}",
        f"Biggest HL Loss: {stats.get('biggest_hl_loss', 0):,}",
        f"Blackjack Hits: {stats.get('blackjack_hits', 0):,}",
        f"Blackjack Stands: {stats.get('blackjack_stands', 0):,}",
        f"Blackjack Busts: {stats.get('blackjack_busts', 0):,}",
        f"Blackjack Folds: {stats.get('blackjack_folds', 0):,}",
        f"Blackjack Wins: {stats.get('blackjack_wins', 0):,}",
    ]
    minigame_stats = [
        f"Longest SQ Streak: {stats.get('longest_sq_streak', 0):,}",
        f"Unscramble Streak: {stats.get('unscramble_streak', 0):,}",
        f"Longest Unscramble Streak: {stats.get('longest_unscramble_streak', 0):,}",
        f"Flashcard Streak: {stats.get('flashcard_streak', 0):,}",
        f"Longest Flashcard Streak: {stats.get('longest_flashcard_streak', 0):,}",
    ]

    embed.add_field(
        name="General Stats 🔢",
        value="\n".join(general_stats),
        inline=False,
    )
    embed.add_field(
        name="Gambling Stats 🎲",
        value="\n".join(gambling_stats),
        inline=False,
    )
    embed.add_field(
        name="Minigame Stats 🎮",
        value="\n".join(minigame_stats),
        inline=False,
    )
    embed.add_field(
        name="Farming 🌽",
        value=f"XP: {farming.get('xp', 0):,}\nCrops Grown: {farming.get('crops_grown', 0):,}",
        inline=True,
    )
    embed.add_field(
        name="Foraging 🌳",
        value=f"XP: {foraging.get('xp', 0):,}\nTrees Chopped: {foraging.get('trees_chopped', 0):,}",
        inline=True,
    )
    embed.add_field(
        name="Fishing 🐟",
        value=f"XP: {fishing.get('xp', 0):,}\nFish Caught: {fishing.get('fish_caught', 0):,}",
        inline=True,
    )
    embed.add_field(
        name="Mining ⛏️",
        value=f"XP: {mining.get('xp', 0):,}\nLodes Mined: {mining.get('lodes_mined', 0):,}",
        inline=True,
    )
    embed.add_field(
        name="Combat ⚔️",
        value=f"XP: {combat.get('xp', 0):,}\nMonsters Slain: {combat.get('monsters_slain', 0):,}",
        inline=True,
    )
    embed.set_thumbnail(url=interaction.user.display_avatar)
    await interaction.response.send_message(embed=embed)


async def process_deposit(interaction: Interaction, amount: int | str = None):
    user: User = interaction.extras.get("user")
    amount = await validate_bits(user=user, amount=amount)

    # Perform deposit
    await user.remove_bits(amount=amount)
    await user.add_bank(amount=amount)
    await user.inc_stat("deposits")
    embed = CustomEmbed(
        colour=discord.Color.dark_blue(), interaction=interaction, activity="depositing"
    ).add_field(
        name="Deposit made!",
        value=f"You have deposited **{amount:,}** bits",
    )
    return await interaction.response.send_message(embed=embed)


async def process_withdrawal(interaction: Interaction, amount: int | str = None):
    user: User = interaction.extras.get("user")
    amount = await validate_bits(user=user, amount=amount, field="bank")

    # Perform withdrawal
    await user.add_bank(amount=-amount)
    await user.add_bits(amount=amount)
    await user.inc_stat("withdraws")

    embed = CustomEmbed(
        colour=discord.Color.dark_blue(), interaction=interaction, activity="withdrawing"
    ).add_field(
        name="Withdrawal made!",
        value=f"You withdrew **{amount:,}** bits",
    )
    return await interaction.response.send_message(embed=embed)


async def process_beg(interaction: Interaction):
    user: User = interaction.extras.get("user")
    total_balance = user.get_field("purse") + user.get_field("bank")

    # If user has 10,000 bits or more in their purse or bank
    if total_balance >= MAX_BALANCE:
        embed = ErrorEmbed(
            title=random.choice(TOO_RICH_TITLES),
            desc=f"You cannot beg if you have more than 10,000 bits\n"
            f"You have **{total_balance:,}** bits",
            interaction=interaction,
            activity="begging",
        )
        return await interaction.response.send_message(embed=embed)

    await user.inc_stat("times_begged")
    beg_amount = randint(100, 1000)
    await user.add_bits(beg_amount)

    embed = CustomEmbed(
        title=f"Someone kind dropped {beg_amount} bits in your cup.",
        desc=f"You now have {await user.get_bits():,} bits.",
        color=discord.Color.green(),
        interaction=interaction,
        activity="begging",
    )
    await interaction.response.send_message(embed=embed)


async def process_payment(interaction: Interaction, recipient: discord.Member, amount: int | str):
    user: User = interaction.extras.get("user")

    amount = await validate_bits(user=user, amount=amount)
    # If they try to bet more than they have in their account.
    if int(amount) < 100:
        embed = ErrorEmbed(
            title=random.choice(PYRAMID_SCHEME_TITLES),
            desc="To avoid '*beg farming*' tactics, you can only send someone amounts over **100**",
            interaction=interaction,
            activity="paying",
        )
        return await interaction.response.send_message(embed=embed)

    payee = await User.get(recipient.id)
    await user.add_bits(amount=-amount)
    await payee.add_bits(amount=amount)

    embed = CustomEmbed(colour=discord.Color.purple())
    embed.add_field(
        name="Payment sent!",
        value=f"You have sent {recipient.mention} **{int(amount):,}** bits",
    )
    return await interaction.response.send_message(embed=embed)


class EconomyCog(BaseCog, name="Economy"):
    """Your primary stop for handling your bits!"""

    @app_commands.command(name="profile", description="Check your profile, pets, etc.")
    async def bits(self, interaction: Interaction):
        """Display your profile with all your balances."""
        await display_profile(interaction=interaction)

    @app_commands.command(name="stats", description="Number go up man happy.")
    async def stats(self, interaction: Interaction):
        """Display your various metrics."""
        await display_stats(interaction=interaction)

    @app_commands.command(name="beg", description="Beg for some money, poor freak.")
    async def beg(self, interaction: Interaction):
        """Beg for some money! Must have less than 10,000 bits."""
        await process_beg(interaction=interaction)

    @app_commands.command(name="check-in", description="Get your daily rewards!")
    async def check_in(self, interaction: Interaction):
        """Claim your work, daily, and weekly!"""
        menu = CheckInMenu(interaction=interaction)
        return await interaction.response.send_message(embed=menu.embed, view=menu)

    @app_commands.command(name="deposit", description="Deposit bits into your bank.")
    @app_commands.describe(amount="amount of bits to deposit")
    async def deposit(self, interaction: Interaction, amount: str | None):
        """Deposit some money into the bank for safekeeping."""
        await process_deposit(interaction=interaction, amount=amount)

    @app_commands.command(name="withdraw", description="Withdraw bits from your bank.")
    @app_commands.describe(amount="amount of bits you want to withdraw")
    async def withdraw(self, interaction: Interaction, amount: str):
        """Withdraw money from your bank."""
        await process_withdrawal(interaction=interaction, amount=amount)

    @app_commands.command(name="pay", description="Pay another player.")
    @app_commands.describe(recipient="discord user you want to pay", amount="amount")
    async def pay(self, interaction: Interaction, recipient: discord.Member, amount: str):
        """Pay someone else some bits, if you're feeling nice!"""
        await process_payment(interaction=interaction, recipient=recipient, amount=amount)


async def setup(bot):
    # Necessary for the bot.py file to auto load cogs
    await bot.add_cog(EconomyCog())
