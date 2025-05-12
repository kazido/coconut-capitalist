import asyncio
import functools
import discord

from discord import Interaction
from utils.custom_embeds import CustomEmbed
from random import randint

from enum import Enum

from cococap.user import User


class GameStates(Enum):
    CORRECT = ("CORRECT :white_check_mark:", discord.Color.green(), "Good guess!")
    INCORRECT = ("INCORRECT :x:", discord.Color.red(), "Unlucky...")
    GUESSING = ("Will it be High or Low?", discord.Color.gray(), "It's definitely the other one...")
    CASHED_OUT = ("Quitting while you're ahead, huh?", discord.Color.purple(), "Come again soon!")

    def __new__(cls, title: str, color: discord.Color, footer: str):
        obj = object.__new__(cls)
        obj._value_ = title.lower()
        obj.title = title
        obj.color = color
        obj.footer = footer
        return obj

    @classmethod
    def from_state(cls, state: str):
        return cls(state)


class Player:
    def __init__(self, bet: int = None):
        self.bet = bet
        self.winnings: int = 0


def guess_high(**kwargs) -> GameStates:
    if kwargs["roll"] in range(6, 11):
        return GameStates.CORRECT
    return GameStates.INCORRECT


def guess_low(**kwargs) -> GameStates:
    if kwargs["roll"] in range(1, 6):
        return GameStates.CORRECT
    return GameStates.INCORRECT


class Actions(Enum):
    GUESS_HIGH = functools.partial(guess_high)
    GUESS_LOW = functools.partial(guess_low)


async def game_results(
    interaction: discord.Interaction, user: User, roll: int, multiplier: int, bet: int, win: bool
):
    embed = None
    if not win:
        user_balance_after_loss = user.get_field("purse")
        losing_embed = CustomEmbed(
            title=f"INCORRECT :x: | Bet: {bet:,}",
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
        await user.in_game(in_game=False)

        # Give the lost money to the house
        bot = User(1016054559581413457)
        await bot.load()
        await bot.inc_purse(bet)

    elif win:
        success_embed = CustomEmbed(
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


class HighButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="High", style=discord.ButtonStyle.primary, emoji="⬆️")

    async def callback(self, interaction: discord.Interaction):
        view: Highlow = self.view

        embed = view.update(Actions.HIT)

        if view.state == GameStates.LOSE:
            embed.add_field(name="Profit", value=f"{-view.player.bet:,} bits", inline=False)
            embed.add_field(name="Bits", value=f"{view.user.get_field('purse'):,} bits")
            # Pay the bot
            view.dealer.winnings += view.player.bet

        await interaction.response.edit_message(embed=embed, view=view)


class Highlow(discord.ui.View):
    def __init__(self, interaction: Interaction):
        super().__init__(timeout=120)
        self.interaction: Interaction = interaction
        self.multiplier: int = 1
        self.roll: int

    def interaction_check(self, interaction):
        # Will verify that whenever a button is pressed, it can only be done by the command caller.
        if interaction.user != self.interaction.user:
            print("someone else try to clicky button in high low!!!")
            return False
        return super().interaction_check(interaction)

    def roll_number(self):
        self.roll = randint(1, 10)

    def multiplier_up(self):
        self.multiplier *= 2

    def update(self):
        """Generate an game state themed embed with the rolled number and the player guess."""

        if self.state != GameStates.READY:
            self.clear_items()

        embed = CustomEmbed(
            title=f"{self.state.title} | User: {str(self.user)} - Bet: {self.player.bet:,}",
            color=self.state.color,
            interaction=self.interaction,
        )
        embed.add_field(
            name=self.state.hand_titles[0],
            value=f"{str(self.player)}\nTotal: {self.player.total_hand()}",
            inline=True,
        )
        embed.add_field(
            name=self.state.hand_titles[1],
            value=f"{str(self.dealer)}\nTotal: {self.dealer.total_hand()}",
            inline=True,
        )
        embed.set_footer(text=self.state.footer)
        return embed

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
            losing_embed = await game_results(interaction, user, self.roll, self.multiplier, bet, 0)
            await high_interaction.response.edit_message(embed=losing_embed, view=None)
            await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not
            losing_embed.title = (
                f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}"
            )
            await high_interaction.edit_original_response(embed=losing_embed)

    @discord.ui.button(label="Low", style=discord.ButtonStyle.blurple, emoji="⬇️")
    async def low_button(self, low_interaction: discord.Interaction, button: discord.Button):
        if low_interaction.user != interaction.user:
            return
        self.low_interaction_at = low_interaction.created_at
        try:
            if self.high_interaction_at.second == self.low_interaction_at.second:
                await low_interaction.response.send_message("Stop trying to cheat!", ephemeral=True)
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
            losing_embed = await game_results(interaction, user, self.roll, self.multiplier, bet, 0)
            await low_interaction.response.edit_message(embed=losing_embed, view=None)
            await asyncio.sleep(1)  # Add a delay so the user can tell if they won or not
            losing_embed.title = (
                f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}"
            )
            await low_interaction.edit_original_response(embed=losing_embed)

    @discord.ui.button(label="Cash Out", style=discord.ButtonStyle.gray, emoji="💰", disabled=True)
    async def stop_button(self, stop_interaction: discord.Interaction, button: discord.Button):
        if stop_interaction.user != interaction.user:
            return
        stop_embed = discord.Embed(
            title=f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}",
            color=discord.Color.blue(),
        )
        stop_embed.add_field(name="Stopped at", value=f"**{self.multiplier:,}x**", inline=True)
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
        await user.in_game(in_game=False)
        await stop_interaction.response.edit_message(embed=stop_embed, view=None)
        return


game_begin_embed = CustomEmbed(
    title=f"HIGHLOW :arrows_clockwise: | User: {interaction.user.name} - Bet: {bet:,}",
    desc="Guess high if you think the number will be 6-10\n"
    "Guess low if you think the number will be 1-5\n"
    "**Good luck.**",
    color=discord.Color.from_str("0x666666"),
    interaction=interaction,
    activity="high low",
)
await interaction.response.send_message(embed=game_begin_embed, view=Highlow(randint(1, 10)))
