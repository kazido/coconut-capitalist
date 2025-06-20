import discord

from enum import Enum
from random import randint
from discord import app_commands, Interaction
from discord.ext import commands
from cococap.user import User
from utils.custom_embeds import SuccessEmbed, FailureEmbed, CustomEmbed
from utils.utils import validate_bits


class GameStates(Enum):
    CORRECT = ("CORRECT :white_check_mark:", discord.Color.green(), "Good guess!")
    INCORRECT = ("INCORRECT :x:", discord.Color.red(), "Unlucky...")
    GUESSING = ("Will it be High or Low?", 0x111111, "It's definitely the other one...")
    CASHED_OUT = ("Smart choice, my friend.", discord.Color.purple(), "Come again soon!")

    def __new__(cls, title, color, footer):
        obj = object.__new__(cls)
        obj._value_ = title.lower()
        obj.title = title
        obj.color = color
        obj.footer = footer
        return obj


class Actions(Enum):
    GUESS_HIGH = "guess_high"
    GUESS_LOW = "guess_low"


def _guess_high(roll: int) -> bool:
    return roll in range(6, 11)


def _guess_low(roll: int) -> bool:
    return roll in range(1, 6)


def _get_action_func(action: Actions):
    return _guess_high if action == Actions.GUESS_HIGH else _guess_low


class HighlowGame(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.user: User = interaction.extras.get("user")
        self.bet = interaction.extras.get("bet")
        self.multiplier = 1
        self.roll = randint(1, 10)
        self.add_item(HighButton())
        self.add_item(LowButton())
        self.add_item(CashOutButton())
        self.embed = CustomEmbed(
            title=f"HIGHLOW :arrows_clockwise: | Bet: {self.bet:,}",
            color=discord.Color.from_str("0x666666"),
            desc="Guess high if you think the number will be 6-10\nGuess low if you think the number will be 1-5\n**Good luck.**",
            interaction=self.interaction,
            activity="highlow",
        )

    async def interaction_check(self, interaction):
        return interaction.user == self.interaction.user

    def get_embed(self):
        return self.embed

    async def _update_embed(self, win: bool):
        if win:
            await self.user.set_stat("hl_loss_streak")
            await self.user.inc_stat("hl_win_streak")
            win_streak = await self.user.get_stat("hl_win_streak")
            longest_win_streak = await self.user.get_stat("longest_hl_streak")
            if win_streak > longest_win_streak:
                await self.user.set_stat("longest_hl_streak", win_streak)
            await self.user.inc_stat("hl_wins")
            embed = SuccessEmbed(
                title=f"CORRECT :white_check_mark: | Bet: {self.bet:,}",
                interaction=self.interaction,
                activity="highlow",
            )
            embed.add_field(name="Multiplier", value=f"**{self.multiplier}x**", inline=True)
            embed.add_field(
                name="Continue", value="Use the **High** and **Low** buttons", inline=False
            )
            embed.set_footer(text="Quit while you're ahead!")
        else:
            await self.user.inc_stat("hl_loss_streak")
            await self.user.set_stat("hl_win_streak")
            loss_streak = await self.user.get_stat("hl_loss_streak")
            longest_loss_streak = await self.user.get_stat("longest_hl_loss_streak")
            if loss_streak > longest_loss_streak:
                await self.user.set_stat("longest_hl_loss_streak", loss_streak)
            embed = FailureEmbed(
                title=f"INCORRECT :x: | Bet: {self.bet:,}",
                interaction=self.interaction,
                activity="highlow",
            )
            embed.add_field(
                name="Purse",
                value=f"{await self.user.get_bits():,} bits *({-self.bet:,})*",
                inline=False,
            )
            if -self.bet < await self.user.get_stat("biggest_hl_loss"):
                await self.user.set_stat("biggest_hl_loss", -self.bet)
            embed.set_footer(text="Better luck next time!")
        embed.add_field(name="Roll", value=f"The number was **{self.roll}**", inline=True)
        self.embed = embed
        return self.embed

    async def process_guess(self, action: Actions, interaction: discord.Interaction):
        guess = _get_action_func(action)
        if guess(self.roll):
            self.multiplier *= 2
            await self._update_embed(win=True)
            self.roll = randint(1, 10)
        else:
            self.multiplier = 0
            await self._update_embed(win=False)
            # Give the lost money to the house
            bot = await User.get(1016054559581413457)
            await bot.add_bits(self.bet)
            self.clear_items()  # Remove buttons from embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def process_cashout(self, interaction: discord.Interaction):
        profit = self.bet * self.multiplier
        await self.user.add_bits(profit)
        if profit > await self.user.get_stat("biggest_hl_win"):
            await self.user.set_stat("biggest_hl_win", profit)
        embed = discord.Embed(
            title=f"HIGHLOW :arrows_clockwise: | Bet: {self.bet:,}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Stopped at", value=f"**{self.multiplier:,}x**", inline=True)
        embed.add_field(
            name="Purse",
            value=f"{await self.user.get_bits():,} bits *(+{profit:,})*",
            inline=False,
        )
        await interaction.response.edit_message(embed=embed, view=None)


class HighButton(discord.ui.Button):
    def __init__(self):
        label = "High"
        style = discord.ButtonStyle.primary
        emoji = "⬆️"
        super().__init__(label=label, style=style, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        await self.view.process_guess(Actions.GUESS_HIGH, interaction)


class LowButton(discord.ui.Button):
    def __init__(self):
        label = "Low"
        style = discord.ButtonStyle.blurple
        emoji = "⬇️"
        super().__init__(label=label, style=style, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        await self.view.process_guess(Actions.GUESS_LOW, interaction)


class CashOutButton(discord.ui.Button):
    def __init__(self):
        label = "Cash Out"
        style = discord.ButtonStyle.gray
        emoji = "💰"
        super().__init__(label=label, style=style, emoji=emoji)

    async def callback(self, interaction: discord.Interaction):
        await self.view.process_cashout(interaction)


class Highlow(commands.Cog, name="Highlow"):
    """Good old heads or tails, just more fun?"""

    def __init__(self):
        super().__init__()

    async def interaction_check(self, interaction: Interaction):
        # Load user data before each command
        user = await User.get(interaction.user.id)
        interaction.extras.update(user=user)

        # Validate the user's bet so they can't bet more than they have
        args = {opt["name"]: opt["value"] for opt in interaction.data.get("options", [])}
        bet = await validate_bits(user=user, amount=args["bet"])

        # Collect their bet immediately
        await user.remove_bits(bet)
        interaction.extras.update(bet=bet)

        await user.inc_stat("highlow_games")

        return super().interaction_check(interaction)

    @app_commands.command(name="highlow")
    @app_commands.describe(bet="amount of bits you want to bet")
    async def highlow(self, interaction: Interaction, bet: str):
        """Guess if the number will be high (6-10) or low (1-5)."""
        view = HighlowGame(interaction=interaction)
        await interaction.response.send_message(embed=view.get_embed(), view=view)


async def setup(bot):
    await bot.add_cog(Highlow())
