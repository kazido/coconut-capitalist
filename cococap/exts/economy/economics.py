import math
import random
import discord
import randfacts
import time

from random import randint
from discord import app_commands, Interaction
from cococap.screens import open_screen

from utils.utils import timestamp_to_digital
from cococap.user import User, Cooldowns
from utils.custom_embeds import CustomEmbed, ErrorEmbed
from utils.base_cog import BaseCog
from utils.utils import validate_bits

from cococap.constants import TOO_RICH_TITLES
from cococap.errors import CustomError

MAX_BALANCE = 10_000

PYRAMID_SCHEME_TITLES = [
    "Pyramid schemes are not allowed",
    "Trying to break the system, are we?",
    "This is what we call pulling a *Botski*",
]


async def process_beg(interaction: Interaction):
    user: User = interaction.extras.get("user")
    total_balance = user.purse

    # If user has 10,000 bits or more
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

    if recipient.bot or recipient.id == interaction.user.id:
        raise CustomError("You can only pay other (human) players.")

    payee = await User.get(recipient.id)
    await user.pay(payee, amount)  # atomic balance check + debit, then credit

    embed = CustomEmbed(colour=discord.Color.purple())
    embed.add_field(
        name="Payment sent!",
        value=f"You have sent {recipient.mention} **{int(amount):,}** bits",
    )
    return await interaction.response.send_message(embed=embed)


class EconomyCog(BaseCog, name="Economy"):
    """Your primary stop for handling your bits!"""

    @app_commands.command(name="profile", description="Check your profile and balances.")
    async def bits(self, interaction: Interaction):
        """Display your profile with all your balances."""
        await open_screen(interaction, "profile")

    @app_commands.command(name="beg", description="Beg for some money, poor freak.")
    async def beg(self, interaction: Interaction):
        """Beg for some money! Must have less than 10,000 bits."""
        await process_beg(interaction=interaction)

    @app_commands.command(name="check-in", description="Get your daily rewards!")
    async def check_in(self, interaction: Interaction):
        """Claim your work, daily, and weekly!"""
        await open_screen(interaction, "checkin")

    @app_commands.command(name="pay", description="Pay another player.")
    @app_commands.describe(recipient="discord user you want to pay", amount="amount")
    async def pay(self, interaction: Interaction, recipient: discord.Member, amount: str):
        """Pay someone else some bits, if you're feeling nice!"""
        await process_payment(interaction=interaction, recipient=recipient, amount=amount)


async def setup(bot):
    # Necessary for the bot.py file to auto load cogs
    await bot.add_cog(EconomyCog())
