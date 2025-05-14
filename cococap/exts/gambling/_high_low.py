import discord
from enum import Enum
from random import randint
from cococap.user import User
from utils.custom_embeds import SuccessEmbed, FailureEmbed, CustomEmbed


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


class HighLow(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=120)
        self.interaction = interaction
        self.user = interaction.extras.get("user")
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
            embed = FailureEmbed(
                title=f"INCORRECT :x: | Bet: {self.bet:,}",
                interaction=self.interaction,
                activity="highlow",
            )
            embed.add_field(
                name="Purse",
                value=f"{self.user.get_field('purse'):,} bits *({-self.bet:,})*",
                inline=False,
            )
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
            bot = await User(1016054559581413457).load()
            await bot.inc_purse(self.bet)
            self.clear_items()  # Remove buttons from embed
        await interaction.response.edit_message(embed=self.embed, view=self)

    async def process_cashout(self, interaction: discord.Interaction):
        profit = self.bet * self.multiplier
        await self.user.inc_purse(profit)
        embed = discord.Embed(
            title=f"HIGHLOW :arrows_clockwise: | Bet: {self.bet:,}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="Stopped at", value=f"**{self.multiplier:,}x**", inline=True)
        embed.add_field(
            name="Purse",
            value=f"{self.user.get_field('purse'):,} bits *(+{profit:,})*",
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
