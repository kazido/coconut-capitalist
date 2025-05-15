import math
import random
import discord
import randfacts
import time
from typing import List

from random import randint
from discord import app_commands, Interaction
from discord.ext import commands
from game_data.converters.data_converter import fetch
from pymongo import DESCENDING

from utils.utils import timestamp_to_digital
from cococap.user import User, Cooldowns
from utils.custom_embeds import CustomEmbed, ErrorEmbed
from utils.base_cog import BaseCog
from utils.utils import validate_bits
from cococap.models import UserDocument as Udoc

from cococap.constants import (
    TOO_RICH_TITLES,
    BOT_ID,
    FIRST_PLACE_ANSI_PREFIX,
    SECOND_PLACE_ANSI_PREFIX,
    THIRD_PLACE_ANSI_PREFIX,
    OTHER_PLACE_ANSI_PREFIX,
    RESET_POSTFIX,
)
from cococap.constants import LeaderboardCategories as LeaderCats

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
        self.update(user=user)

        rank = fetch("ranks." + str(user.get_field("rank")))

        self.label = f"+{int(rank.wage):,} bits"
        self.emoji = "💸"
        await user.inc_purse(int(rank.wage))
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
        self.update(user)

        # Calculate and add bank interest rate
        interest = 0.003 + 0.027 * (math.e ** (-(user.get_field("bank") / 20_000_000)))
        bonus = round(user.get_field("bank") * interest)
        await user.inc_bank(amount=int(bonus))

        # Update the embed
        embed.add_field(name="Random Fact", value=f"{randfacts.get_fact()}")
        embed.add_field(name="Bank Interest", value=f"🏦 +{bonus:,} bits")

        # Put the command on cooldown!
        self.label = f"+1 tokens"
        self.emoji = "🪙"
        await user.inc_tokens(tokens=1)
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
        self.update(user)

        self.label = f"+7 luckbucks"
        self.emoji = "🍀"
        await user.inc_luckbucks(amount=7)
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
        await user.update_field("name", interaction.user.display_name, save=True)

    embed = CustomEmbed(
        title=f"You are: `{rank.display_name}`",
        color=discord.Color.blue(),
        interaction=interaction,
        activity="profile",
    )

    embed.add_field(
        name="Balances",
        value=f":money_with_wings: **BITS**: {user.get_field('purse'):,}\n"
        f":bank: **BANK**: {user.get_field('bank'):,}\n"
        f":four_leaf_clover: **LUCKBUCKS**: {user.get_field('luckbucks'):,}\n"
        f":coin: **TOKENS**: {user.get_field('tokens'):,}",
    )
    embed.set_thumbnail(url=interaction.user.display_avatar)
    await interaction.response.send_message(embed=embed)


async def process_deposit(interaction: Interaction, amount: int | str = None):
    user: User = interaction.extras.get("user")
    amount = validate_bits(user=user, amount=amount)

    # Perform deposit
    await user.inc_purse(amount=-amount)
    await user.inc_bank(amount=amount)
    embed = CustomEmbed(
        colour=discord.Color.dark_blue(), interaction=interaction, activity="depositing"
    ).add_field(
        name="Deposit made!",
        value=f"You have deposited **{amount:,}** bits",
    )
    return await interaction.response.send_message(embed=embed)


async def process_withdrawal(interaction: Interaction, amount: int | str = None):
    user: User = interaction.extras.get("user")
    amount = validate_bits(user=user, amount=amount, field="bank")

    # Perform withdrawal
    await user.inc_bank(amount=-amount)
    await user.inc_purse(amount=amount)

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

    beg_amount = randint(100, 1000)
    await user.inc_purse(beg_amount)

    embed = CustomEmbed(
        title=f"Someone kind dropped {beg_amount} bits in your cup.",
        desc=f"You now have {user.get_field('purse'):,} bits.",
        color=discord.Color.green(),
        interaction=interaction,
        activity="begging",
    )
    await interaction.response.send_message(embed=embed)


async def process_payment(interaction: Interaction, recipient: discord.Member, amount: int | str):
    user: User = interaction.extras.get("user")

    amount = validate_bits(user=user, amount=amount)
    # If they try to bet more than they have in their account.
    if int(amount) < 100:
        embed = ErrorEmbed(
            title=random.choice(PYRAMID_SCHEME_TITLES),
            desc="To avoid '*beg farming*' tactics, you can only send someone amounts over **100**",
            interaction=interaction,
            activity="paying",
        )
        return await interaction.response.send_message(embed=embed)

    payee = await User(recipient.id).load()
    await user.inc_purse(amount=-amount)
    await payee.inc_purse(amount=amount)

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
        """Display your profile with all your stats."""
        await display_profile(interaction=interaction)

    @app_commands.command(name="beg", description="Beg for some money, poor freak.")
    async def beg(self, interaction: Interaction):
        """Beg for some money! Must have less than 10,000 bits."""
        await process_beg(interaction=interaction)

    async def category_autocomplete(
        self, interaction: Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        categories = [category.display_name for category in list(LeaderCats)]
        return [
            app_commands.Choice(name=category, value=category)
            for category in categories
            if current.lower() in category.lower()
        ]

    # Command for the richest members in the server
    @app_commands.command(name="top", description="See the top 10 players in each category!")
    @app_commands.describe(category="category of leaderboard")
    @app_commands.autocomplete(category=category_autocomplete)
    async def top(self, interaction: Interaction, category: str, advanced: bool | None):
        # Calculate the circulation for the bits leaderboard
        total_purses = await Udoc.find(Udoc.discord_id != BOT_ID).sum(Udoc.purse)
        total_banks = await Udoc.find(Udoc.discord_id != BOT_ID).sum(Udoc.bank)
        circulation = total_purses + total_banks
        bot_purse = 0

        category = LeaderCats.from_name(category)

        async def leaderboard_string(user: Udoc, advanced=False):
            if category == LeaderCats.BITS:
                return f"{user.name} - {user.purse + user.bank:,}"
            if category in [LeaderCats.LUCKBUCKS, LeaderCats.DROPS]:
                return f"{user.name} - {getattr(user, category.column):,}"
            else:
                fields = category.column.split(".")
                result = user
                while len(fields) > 0:
                    result = getattr(result, fields.pop(0))
                if advanced:
                    return f"*{user.name}* - Level {User.xp_to_level(xp=result):,} | {result:,} xp"
                return f"*{user.name}* - Level {User.xp_to_level(xp=result):,}"

        # Yes, I am hardcoding this. I don't see a future where I have multiple leaderboard categories
        # that are based on two fields being summed together like they are here...
        if category == LeaderCats.BITS:
            pipeline = [
                {"$addFields": {"sum_value": {"$add": ["$purse", "$bank"]}}},
                {"$sort": {"sum_value": -1}},
            ]
            query = await Udoc.aggregate(pipeline).to_list()
        else:
            query = await Udoc.find().sort((category.column, DESCENDING)).to_list()

        # START CREATING THE LEADERBOARD DISPLAY ----------------------
        embed = discord.Embed(
            title=f"{category.display_name} Leaderboard",
            description="```ansi\n",
            color=discord.Color.from_str(category.color),
        )

        # We have to use our own index because we use continue when we encounter a bot, and that would mess up enumerate
        index = 1
        for user in query:
            if user.discord_id in [1016054559581413457, 956000805578768425]:
                # Detect if the user is either of the bots
                bot_purse = user.purse
                continue

            rank_string = await leaderboard_string(
                user=user,
                advanced=advanced,
            )

            rank_string = f"[{index}] {rank_string}"

            if user.discord_id == interaction.user.id:
                rank_string += " (YOU)"

            if index == 1:
                embed.description += f"{FIRST_PLACE_ANSI_PREFIX}{rank_string}{RESET_POSTFIX}\n"
            elif index == 2:
                embed.description += f"{SECOND_PLACE_ANSI_PREFIX}{rank_string}{RESET_POSTFIX}\n"
            elif index == 3:
                embed.description += f"{THIRD_PLACE_ANSI_PREFIX}{rank_string}{RESET_POSTFIX}\n"
            elif index <= 10:
                embed.description += f"{OTHER_PLACE_ANSI_PREFIX}{rank_string}{RESET_POSTFIX}\n"

            elif index > 10 and (user.id == interaction.user.id):
                # If user didn't get top 10, add their place to the end
                embed.description += "\n" + "Your rank:" + "\n" + f"{rank_string}"
            index += 1

        embed.description += "\n```"

        if category.value == 0:
            embed.set_footer(text=f"The house has made: {bot_purse:,} bits")
            embed.add_field(
                name="Current Circulation",
                value=f"There are currently **{circulation:,}** bits in the economy.",
            )
        await interaction.response.send_message(embed=embed)

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
