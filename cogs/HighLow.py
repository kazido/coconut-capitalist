import typing
import asyncio
from cogs.ErrorHandler import registered
from ClassLibrary2 import RequestUser
import mymodels as mm
from mymodels import Users
from discord.ext import commands
from discord import app_commands
import discord
from random import randint


async def game_results(interaction: discord.Interaction, user: RequestUser, roll: int,
                       multiplier: int, bet: int, win: [0, 1]):
    embed = None
    if win == 0:
        user_balance_after_loss = user.instance.money
        losing_embed = discord.Embed(
            title=f"INCORRECT :x: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}",
            color=discord.Color.red()
        )
        losing_embed.add_field(name="Incorrect!", value=f"The number was **{roll}**", inline=True)
        losing_embed.add_field(name="Profit", value=f"**{'{:,}'.format(-bet)}** bits", inline=True)
        losing_embed.add_field(name="Bits", value=f"You have {'{:,}'.format(user_balance_after_loss)} bits",
                               inline=False)
        losing_embed.set_footer(text=f"XP: coming soon.")
        embed = losing_embed
        user.update_game_status(False)

        bot = RequestUser(956000805578768425, interaction)
        bot.instance.money += bet
        bot.instance.save()
    elif win == 1:
        success_embed = discord.Embed(
            title=f"CORRECT :white_check_mark: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}",
            color=discord.Color.green()
        )
        success_embed.add_field(name="Roll", value=f"The number was **{roll}**", inline=True)
        success_embed.add_field(name="Multiplier", value=f"**{multiplier}x**", inline=True)
        success_embed.add_field(name="Continue", value="Use the **high** and **low** buttons", inline=False)
        success_embed.set_footer(text=f"Click the stop button to cash out!")
        embed = success_embed
    return embed


class HighLow(commands.Cog, name="HighLow"):
    """Guess if the next number will be high (6-10) or low (1-5)"""

    def __init__(self, bot):
        self.bot = bot

    @registered()
    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="highlow", description="Guess if the number will be high (6-10) or low (1-5).")
    @app_commands.describe(bet='amount of bits you want to bet | use max for all bits in purse')
    async def high_low(self, interaction: discord.Interaction, bet: str):
        user = RequestUser(interaction.user.id, interaction=interaction)
        if user.instance.in_game:
            in_game_embed = discord.Embed(
                title="You are already in game!",
                description="Finish your other game before you start another.\n"
                            "If you believe this is an error, please contact the owner.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=in_game_embed)
            await asyncio.sleep(5)
            await interaction.delete_original_response()
            return

        if bet == 'max':
            bet = user.instance.money
        else:
            bet = int(bet)

        bet_checks_failed_message, passed = user.bet_checks(bet)

        if passed is False:
            bet_not_allowed_embed = discord.Embed(  # Embed for when a user bets more than they have in purse
                title=bet_checks_failed_message, description="Try again with a valid bet.",
                color=discord.Color.red())
            await interaction.response.send_message(embed=bet_not_allowed_embed)
            return

        user.update_balance(-bet)  # Subtract the bet from the users purse
        user.update_game_status(True)  # Set the users ingame status to True

        class HighLowButtons(discord.ui.View):
            def __init__(self, roll, *, multiplier=0, timeout=120):
                self.roll = roll
                self.multiplier = multiplier
                super().__init__(timeout=timeout)

            @discord.ui.button(label="High", style=discord.ButtonStyle.blurple, emoji='⬆️')
            async def high_button(self, high_interaction: discord.Interaction, button: discord.Button):
                if high_interaction.user != interaction.user:
                    return
                self.stop_button.disabled = False
                if self.roll in range(6, 11):
                    if self.multiplier == 0:
                        self.multiplier = 2
                    else:
                        self.multiplier *= 2

                    success_embed = await game_results(interaction, user, self.roll, self.multiplier, bet, 1)
                    self.roll = randint(1, 10)

                    await high_interaction.response.edit_message(embed=success_embed, view=self)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not

                    success_embed.title = f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}"
                    success_embed.color = discord.Color.from_str("0x666666")
                    await high_interaction.edit_original_response(embed=success_embed)

                else:
                    losing_embed = await game_results(interaction, user, self.roll, self.multiplier, bet, 0)
                    await high_interaction.response.edit_message(embed=losing_embed, view=None)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not
                    losing_embed.title = f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}"
                    await high_interaction.edit_original_response(embed=losing_embed)

            @discord.ui.button(label="Low", style=discord.ButtonStyle.blurple, emoji='⬇️')
            async def low_button(self, low_interaction: discord.Interaction, button: discord.Button):
                if low_interaction.user != interaction.user:
                    return
                self.stop_button.disabled = False
                if self.roll in range(1, 6):
                    if self.multiplier == 0:
                        self.multiplier = 2
                    else:
                        self.multiplier *= 2

                    success_embed = await game_results(interaction, user, self.roll, self.multiplier, bet, 1)
                    self.roll = randint(1, 10)

                    await low_interaction.response.edit_message(embed=success_embed, view=self)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not

                    success_embed.title = f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}"
                    success_embed.color = discord.Color.from_str("0x666666")
                    await low_interaction.edit_original_response(embed=success_embed)

                else:
                    losing_embed = await game_results(interaction, user, self.roll, self.multiplier, bet, 0)
                    await low_interaction.response.edit_message(embed=losing_embed, view=None)
                    await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not
                    losing_embed.title = f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}"
                    await low_interaction.edit_original_response(embed=losing_embed)

            @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.gray, emoji='💰', disabled=True)
            async def stop_button(self, stop_interaction: discord.Interaction, button: discord.Button):
                if stop_interaction.user != interaction.user:
                    return
                stop_embed = discord.Embed(
                    title=f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}",
                    color=discord.Color.blue()
                )
                stop_embed.add_field(name="Stopped at", value=f"**{'{:,}'.format(self.multiplier)}x**", inline=True)
                stop_embed.add_field(name="Profit", value=f"**{'{:,}'.format(bet * self.multiplier)}** bits",
                                     inline=True)
                stop_embed.add_field(name="Bits",
                                     value=f"You have {'{:,}'.format(user.instance.money + (bet * self.multiplier))} bits",
                                     inline=False)
                stop_embed.set_footer(text="XP: coming soon")
                user.update_balance(bet * self.multiplier)
                user.update_game_status(False)
                await stop_interaction.response.edit_message(embed=stop_embed, view=None)

        game_begin_embed = discord.Embed(
            title=f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {'{:,}'.format(bet)}",
            description="Guess high if you think the number will be 6-10\n"
                        "Guess low if you think the number will be 1-5\n"
                        "**Good luck.**",
            color=discord.Color.from_str("0x666666")
        )
        await interaction.response.send_message(embed=game_begin_embed, view=HighLowButtons(randint(1, 10)))


async def setup(bot):
    await bot.add_cog(HighLow(bot))
