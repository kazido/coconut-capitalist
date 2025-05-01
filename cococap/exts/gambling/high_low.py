import asyncio
import discord

from cococap.user import User

from discord.ext import commands
from discord import app_commands
from utils.messages import Cembed
from utils.utils import validate_bet
from random import randint


async def game_results(
    interaction: discord.Interaction, user: User, roll: int, multiplier: int, bet: int, win: bool
):
    embed = None
    if not win:
        user_balance_after_loss = user.get_field("purse")
        losing_embed = Cembed(
            title=f"INCORRECT :x: | User: {interaction.user.name} - Bet: {bet:,}",
            color=discord.Color.red(),
            interaction=interaction,
            activity="high low",
        )
        losing_embed.add_field(name="Incorrect!", value=f"The number was **{roll}**", inline=True)
        losing_embed.add_field(name="Profit", value=f"**{-bet:,}** bits", inline=True)
        losing_embed.add_field(
            name="Bits",
            value=f"You have {user_balance_after_loss:,} bits",
            inline=False,
        )
        embed = losing_embed
        await user.update_game(in_game=False, interaction=interaction)

        # Give the lost money to the house
        bot = User(1016054559581413457)
        await bot.load()
        await bot.inc_purse(bet)

    elif win:
        success_embed = Cembed(
            title=f"CORRECT :white_check_mark: | User: {interaction.user.name} - Bet: {bet:,}",
            color=discord.Color.green(),
            interaction=interaction,
            activity="high low",
        )
        success_embed.add_field(name="Roll", value=f"The number was **{roll}**", inline=True)
        success_embed.add_field(name="Multiplier", value=f"**{multiplier}x**", inline=True)
        success_embed.add_field(
            name="Continue", value="Use the **high** and **low** buttons", inline=False
        )
        success_embed.set_footer(text=f"Click the stop button to cash out!")
        embed = success_embed
    return embed


class HighLow(commands.Cog, name="High Low"):
    """Guess if the next number will be high (6-10) or low (1-5)"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="highlow")
    @app_commands.describe(bet="amount of bits you want to bet | use max for all bits in purse")
    async def high_low(self, interaction: discord.Interaction, bet: str):
        """Guess if the number will be high (6-10) or low (1-5)."""
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        if user.get_field("in_game"):
            in_game_embed = Cembed(
                title="You are already in game!",
                desc="Finish your other game before you start another.\n"
                "If you believe this is an error, please contact the owner.",
                color=discord.Color.red(),
                interaction=interaction,
                activity="high low",
            )
            await interaction.response.send_message(embed=in_game_embed, ephemeral=True)
            await asyncio.sleep(5)
            await interaction.delete_original_response()
            return

        balance = user.get_field("purse")

        if bet == "max":
            if user.get_field("settings")["disable_max_bet"]:
                failed_embed = Cembed(
                    title="Max Bet Disabled",
                    desc="You have disabled betting your purse to protect yourself financially. I won't tell you how to reenable it.",
                    color=discord.Color.red(),
                    interaction=interaction,
                    activity="highlow",
                )
                await interaction.response.send_message(embed=failed_embed, ephemeral=True)
                return
            bet = balance
        try:
            bet = int(bet)
        except ValueError:
            if type(bet) == str:
                embed = Cembed(
                    title="Invalid input!",
                    desc="You can either input an integer or 'max' as your bet.",
                    color=discord.Color.red(),
                    interaction=interaction,
                    activity="high low",
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            await asyncio.sleep(4)
            await interaction.delete_original_response()
            return

        message = await validate_bet(balance=balance, bet=bet)

        if message:
            embed = Cembed(  # Embed for when a user bets more than they have in purse
                title=message,
                desc="Try again with a valid bet.",
                color=discord.Color.red(),
                interaction=interaction,
                activity="high low",
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await user.inc_purse(-bet)  # Subtract the bet from the users purse
        await user.update_game(
            in_game=True, interaction=interaction
        )  # Set the users ingame status to True

        class HighLowButtons(discord.ui.View):
            def __init__(self, roll, *, multiplier=0, timeout=120):
                self.roll = roll
                self.multiplier = multiplier
                self.high_interaction_at = None
                self.low_interaction_at = None
                super().__init__(timeout=timeout)

            @discord.ui.button(label="High", style=discord.ButtonStyle.blurple, emoji="⬆️")
            async def high_button(
                self, high_interaction: discord.Interaction, button: discord.Button
            ):
                if high_interaction.user != interaction.user:
                    return
                self.high_interaction_at = high_interaction.created_at
                try:
                    if self.high_interaction_at.second == self.low_interaction_at.second:
                        return
                except AttributeError:
                    pass
                self.stop_button.disabled = False
                if self.roll in range(6, 11):
                    if self.multiplier == 0:
                        self.multiplier = 2
                    else:
                        self.multiplier *= 2

                    success_embed = await game_results(
                        interaction, user, self.roll, self.multiplier, bet, 1
                    )
                    self.roll = randint(1, 10)

                    await high_interaction.response.edit_message(embed=success_embed, view=None)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not

                    success_embed.title = (
                        f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}"
                    )
                    success_embed.color = discord.Color.from_str("0x666666")
                    await high_interaction.edit_original_response(embed=success_embed, view=self)

                else:
                    losing_embed = await game_results(
                        interaction, user, self.roll, self.multiplier, bet, 0
                    )
                    await high_interaction.response.edit_message(embed=losing_embed, view=None)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not
                    losing_embed.title = (
                        f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}"
                    )
                    await high_interaction.edit_original_response(embed=losing_embed)

            @discord.ui.button(label="Low", style=discord.ButtonStyle.blurple, emoji="⬇️")
            async def low_button(
                self, low_interaction: discord.Interaction, button: discord.Button
            ):
                if low_interaction.user != interaction.user:
                    return
                self.low_interaction_at = low_interaction.created_at
                try:
                    if self.high_interaction_at.second == self.low_interaction_at.second:
                        await low_interaction.response.send_message(
                            "Stop trying to cheat!", ephemeral=True
                        )
                        return
                except AttributeError:
                    pass
                self.stop_button.disabled = False
                if self.roll in range(1, 6):
                    if self.multiplier == 0:
                        self.multiplier = 2
                    else:
                        self.multiplier *= 2

                    success_embed = await game_results(
                        interaction, user, self.roll, self.multiplier, bet, 1
                    )
                    self.roll = randint(1, 10)

                    await low_interaction.response.edit_message(embed=success_embed, view=None)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not

                    success_embed.title = (
                        f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}"
                    )
                    success_embed.color = discord.Color.from_str("0x666666")
                    await low_interaction.edit_original_response(embed=success_embed, view=self)

                else:
                    losing_embed = await game_results(
                        interaction, user, self.roll, self.multiplier, bet, 0
                    )
                    await low_interaction.response.edit_message(embed=losing_embed, view=None)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not
                    losing_embed.title = (
                        f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}"
                    )
                    await low_interaction.edit_original_response(embed=losing_embed)

            @discord.ui.button(
                label="Cash Out", style=discord.ButtonStyle.gray, emoji="💰", disabled=True
            )
            async def stop_button(
                self, stop_interaction: discord.Interaction, button: discord.Button
            ):
                if stop_interaction.user != interaction.user:
                    return
                stop_embed = discord.Embed(
                    title=f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}",
                    color=discord.Color.blue(),
                )
                stop_embed.add_field(
                    name="Stopped at", value=f"**{self.multiplier:,}x**", inline=True
                )
                stop_embed.add_field(
                    name="Profit",
                    value=f"**{bet*self.multiplier:,}** bits",
                    inline=True,
                )
                stop_embed.add_field(
                    name="Bits",
                    value=f"You have {(user.get_field('purse') + (bet * self.multiplier)):,} bits",
                    inline=False,
                )
                await user.inc_purse(bet * self.multiplier)
                await user.update_game(in_game=False, interaction=interaction)
                await stop_interaction.response.edit_message(embed=stop_embed, view=None)
                return

        game_begin_embed = Cembed(
            title=f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}",
            desc="Guess high if you think the number will be 6-10\n"
            "Guess low if you think the number will be 1-5\n"
            "**Good luck.**",
            color=discord.Color.from_str("0x666666"),
            interaction=interaction,
            activity="high low",
        )
        await interaction.response.send_message(
            embed=game_begin_embed, view=HighLowButtons(randint(1, 10))
        )


async def setup(bot):
    await bot.add_cog(HighLow(bot))
