import math
import asyncio
import random
import discord
import randfacts
from typing import List

from random import randint
from discord import app_commands, Interaction
from discord.ext import commands
from pymongo import DESCENDING

from cococap.user import User
from utils.messages import Cembed
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


class EconomyCog(commands.Cog, name="Economy"):
    """Your primary stop for making and losing bits!"""

    def __init__(self, bot):
        """Standard cog initialiser"""
        self.bot = bot
        self.tree = self.bot.tree

    @app_commands.command(name="profile", description="Check your profile, pets, etc.")
    async def bits(self, interaction: discord.Interaction):
        user = User(interaction.user.id)
        await user.load()

        # TODO: Fix ranks
        # rank = await user.get_user_rank()

        embed = Cembed(
            # title=f"You are: `{rank.display_name}`",
            title="TEST!",
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

    @app_commands.command(name="beg")
    async def beg(self, interaction: Interaction):
        """Beg for some money! Must have less than 10,000 bits."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        max_balance = 10_000
        total_balance = user.get_field("purse") + user.get_field("bank")

        # If user has 10,000 bits or more in their purse or bank
        if total_balance >= max_balance:
            embed = Cembed(
                title=random.choice(TOO_RICH_TITLES),
                desc=f"You cannot beg if you have more than 10,000 bits\n"
                f"You have **{total_balance:,}** bits",
                color=discord.Color.red(),
                interaction=interaction,
                activity="begging",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            beg_amount = randint(100, 500)
            await user.inc_purse(beg_amount)

            embed = Cembed(
                title=f"Someone kind dropped {beg_amount} bits in your cup.",
                desc=f"You now have {user.get_field('purse')} bits.",
                color=discord.Color.green(),
                interaction=interaction,
                activity="begging",
            )
            await interaction.response.send_message(embed=embed)

    async def category_autocomplete(
        self, interaction: discord.Interaction, current: str
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

    @app_commands.command(name="check-in")
    async def check_in(self, interaction: discord.Interaction):
        """Claim your work, daily, and weekly!"""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        class CheckInMenu(discord.ui.View):
            def __init__(self, *, timeout: float | None = 180):
                super().__init__(timeout=timeout)
                self.embed = Cembed(
                    title="Check-ins",
                    desc="Come back often to claim your rewards.",
                    color=discord.Color.dark_blue(),
                    interaction=interaction,
                    activity="checking in",
                )
                self.commands = {
                    "work": self.work_button,
                    "daily": self.daily_button,
                    "weekly": self.weekly_button,
                }
                for command_type in self.commands.keys():
                    ready, cooldown = user.check_cooldown(command_type)
                    self.embed.add_field(
                        name=command_type.capitalize(),
                        value="*Ready!*" if ready else f"{cooldown}",
                    )
                self.prepare_buttons()

            def prepare_buttons(self):
                # Check the readiness of each command and add it to the embed
                for command_type, command in self.commands.items():
                    # TEMPORARILY DISABLE WEEKLY
                    if command_type == "weekly":
                        continue
                    ready, _ = user.check_cooldown(command_type)
                    command.disabled = False if ready else True
                    command.style = (
                        discord.ButtonStyle.blurple if ready else discord.ButtonStyle.gray
                    )
                    command.emoji = "✅" if ready else "❌"

            @discord.ui.button(label="Work")
            async def work_button(self, interaction: Interaction, button: discord.ui.Button):
                rank = await user.get_user_rank()
                wage = rank.wage
                description = f":money_with_wings: **+{wage:,} bits**"

                # If the user has a pet, we need to apply the bits multiplier
                active_pet, pet_data = user.get_active_pet()
                if active_pet is None:
                    await user.inc_purse(wage)
                else:
                    pet_bonus = pet_data.work_bonus
                    pet_emoji = pet_data.emoji
                    description += f"\n{pet_emoji} **+{int(pet_bonus):,} bits**"
                    await user.inc_purse(wage + pet_bonus)

                self.embed.set_field_at(0, name="Work", value=description)
                # Put the command on cooldown!
                await user.set_cooldown("work")
                self.prepare_buttons()
                await interaction.response.edit_message(embed=self.embed, view=self)

                if user.get_field("settings")["auto_deposit"]:
                    purse = user.get_field("purse")
                    await user.inc_purse(amount=-purse)
                    await user.inc_bank(amount=purse)
                    embed = Cembed(
                        colour=discord.Color.dark_blue(),
                        interaction=interaction,
                        activity="depositing",
                    )
                    embed.add_field(
                        name="Auto deposit made!",
                        value=f"You have automatically deposited **{purse:,}** bits",
                    )
                    embed.set_author(
                        name=f"{interaction.user.name} - deposit",
                        icon_url=interaction.user.display_avatar,
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)

            @discord.ui.button(label="Daily")
            async def daily_button(self, interaction: Interaction, button: discord.ui.Button):
                description = f"**:coin: +{1} tokens**"

                # Add bonus tokens if the user has an active pet
                active_pet, pet_data = user.get_active_pet()
                if active_pet:
                    pet_bonus = pet_data.daily_bonus
                    pet_emoji = pet_data.emoji
                    description += f"\n{pet_emoji} **+{int(pet_bonus)} tokens**"
                    await user.inc_tokens(tokens=1 + pet_bonus)
                else:
                    await user.inc_tokens(tokens=1)

                # Calculate and add bank interest rate
                interest = 0.003 + 0.027 * (math.e ** (-(user.get_field("bank") / 20_000_000)))
                bonus = user.get_field("bank") * interest
                description += f"\n**:bank: +{int(bonus):,} bits**"
                await user.inc_bank(amount=int(bonus))

                # Update the embed
                self.embed.set_field_at(1, name="Daily", value=description)
                self.embed.add_field(
                    name=f"Random Fact", value=f"{randfacts.get_fact()}", inline=False
                )

                # Put the command on cooldown!
                await user.set_cooldown("daily")
                self.prepare_buttons()
                await interaction.response.edit_message(embed=self.embed, view=self)

            @discord.ui.button(label="Weekly", disabled=True)
            async def weekly_button(self, interaction: Interaction, button: discord.ui.Button):
                pass

        menu = CheckInMenu()

        await interaction.response.send_message(embed=menu.embed, view=menu)
        return

    @app_commands.command(name="deposit")
    @app_commands.describe(amount="amount of bits to deposit | enter max for all")
    async def deposit(self, interaction: discord.Interaction, amount: int | None):
        """Deposit some money into the bank for safekeeping."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        if not amount:
            amount = user.get_field("purse")
        if int(amount) > user.get_field("purse"):
            await interaction.response.send_message(
                f"You don't have enough bits to deposit. "
                f"Balance: {user.get_field('purse'):,} bits",
                ephemeral=True,
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message(
                "You cannot deposit **0** bits...", ephemeral=True
            )
            return
        elif int(amount) < 0:
            await interaction.response.send_message(
                "You cannot deposit negative bits either!", ephemeral=True
            )
            return
        elif int(amount) < 250:
            await interaction.response.send_message(
                "Sorry, deposits must be over 250 bits.", ephemeral=True
            )
            return
        else:
            await user.inc_purse(amount=-amount)
            await user.inc_bank(amount=amount)
            embed = Cembed(
                colour=discord.Color.dark_blue(), interaction=interaction, activity="depositing"
            )
            embed.add_field(
                name="Deposit made!",
                value=f"You have deposited **{amount:,}** bits",
            )
            embed.set_author(
                name=f"{interaction.user.name} - deposit", icon_url=interaction.user.display_avatar
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="withdraw", description="Withdraw bits from the bank.")
    @app_commands.describe(amount="amount of bits you want to withdraw")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        bank = user.get_field("bank")
        if amount in ["all", "max"]:
            amount = bank
        amount = int(amount)

        # Validate the withdraw amount
        if int(amount) > bank:
            await interaction.response.send_message(
                f"You don't have that many bits in your account. " f"Bank Balance: {bank:,} bits",
                ephemeral=True,
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message(
                "You cannot withdraw **0** bits...", ephemeral=True
            )
            return
        elif int(amount) < 0:
            await interaction.response.send_message(
                "You cannot withdraw negative bits either!", ephemeral=True
            )
            return

        settings = user.get_field("settings")
        if settings["withdraw_warning"]:
            warning_embed = Cembed(
                title="Are you sure?",
                desc="Withdrawing just to gamble more might not be a good idea.",
                color=discord.Color.dark_red(),
                interaction=interaction,
                activity="withdrawing",
            )
            warning_embed.set_footer(text=f"User: {interaction.user.name}")

            class WithdrawButtons(discord.ui.View):
                def __init__(self, *, timeout=180):
                    super().__init__(timeout=timeout)

                @discord.ui.button(label="Yes, withdraw", style=discord.ButtonStyle.green)
                async def green_button(
                    self,
                    confirm_interaction: discord.Interaction,
                    button: discord.ui.Button,
                ):
                    if confirm_interaction.user != interaction.user:
                        return

                    await user.inc_bank(amount=-amount)
                    await user.inc_purse(amount=amount)
                    withdraw_embed = Cembed(
                        colour=discord.Color.dark_blue(),
                        interaction=confirm_interaction,
                        activity="withdrawing",
                    )
                    withdraw_embed.add_field(
                        name="Withdrawal made!",
                        value=f"You withdrew **{amount:,}** bits",
                    )
                    await confirm_interaction.response.edit_message(embed=withdraw_embed, view=None)
                    return

                @discord.ui.button(label="No", style=discord.ButtonStyle.red)
                async def red_button(
                    self, deny_interaction: discord.Interaction, button: discord.ui.Button
                ):
                    if deny_interaction.user != interaction.user:
                        return
                    cancel_embed = Cembed(
                        title="Withdraw cancelled",
                        desc="Withdraw was either cancelled or timed out.",
                        interaction=deny_interaction,
                        activity="cancelled withdraw",
                    )
                    await deny_interaction.response.edit_message(embed=cancel_embed, view=None)
                    await asyncio.sleep(3)
                    return

            await interaction.response.send_message(embed=warning_embed, view=WithdrawButtons())
        else:
            await user.inc_bank(amount=-amount)
            await user.inc_purse(amount=amount)
            withdraw_embed = Cembed(
                colour=discord.Color.dark_blue(), interaction=interaction, activity="withdrawing"
            )
            withdraw_embed.add_field(
                name="Withdrawal made!",
                value=f"You withdrew **{amount:,}** bits",
            )
            await interaction.response.send_message(embed=withdraw_embed)
            return

    @app_commands.command(name="pay")
    @app_commands.describe(recipient="discord user you want to pay", amount="amount")
    async def pay(self, interaction: discord.Interaction, recipient: discord.Member, amount: int):
        """Pay someone else some bits, if you're feeling nice!"""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        # If they try to bet more than they have in their account.
        if int(amount) < 100:
            titles = [
                "Pyramid schemes are not allowed",
                "Trying to break the system, are we?",
                "This is what we call pulling a *Botski*",
            ]
            embed = Cembed(
                title=random.choice(titles),
                desc="To avoid '*beg farming*' tactics, you can only send someone amounts over **100**",
                color=discord.Color.red(),
                interaction=interaction,
                activity="paying",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        elif int(amount) > user.get_field("purse"):
            await interaction.response.send_message(
                f"You don't have enough bits to send. Balance: "
                f"{user.get_field('purse'):,} bits",
                ephemeral=True,
            )
            return
        elif int(amount) == 0:
            await interaction.response.send_message(
                "You cannot send someone **0** bits...", ephemeral=True
            )
            return
        elif int(amount) < 0:
            await interaction.response.send_message(
                "You cannot send someone negative bits either!", ephemeral=True
            )
            return
        payee = User(recipient.id)
        await payee.load()
        await user.inc_purse(amount=int(-amount))
        await payee.inc_purse(amount=amount)

        embed = Cembed(colour=discord.Color.purple())
        embed.add_field(
            name="Payment sent!",
            value=f"You have sent {recipient.mention} **{int(amount):,}** bits",
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
