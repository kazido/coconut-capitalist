import discord
import asyncio
import random

from discord.ext import commands
from discord import app_commands, Interaction
from the_trivia_api_library import TriviaAPIClient
from utils.custom_embeds import CustomEmbed
from cococap.constants import AlphabetEmojis as AE
from cococap.constants import AlphabetUnicode as AU
from cococap.user import User
from utils.base_cog import BaseCog


def get_color(difficulty: str):
    if difficulty == "easy":
        return discord.Color.green()
    if difficulty == "medium":
        return discord.Color.yellow()
    if difficulty == "hard":
        return discord.Color.red()


def get_profit(difficulty: str):
    if difficulty == "easy":
        return 10000
    if difficulty == "medium":
        return 25000
    if difficulty == "hard":
        return 50000


class AnswerButton(discord.ui.Button):
    def __init__(self, emoji: str, is_correct: bool):
        self.is_correct = is_correct
        super().__init__(emoji=emoji, style=discord.ButtonStyle.gray)

    async def callback(self, interaction):
        embed: CustomEmbed
        user: User = self.view.user
        if self.is_correct:
            await self.view.interaction.extras.get("user").inc_stat("trivia_wins")
            embed = self.view.generate_embed(True)
            embed.change_to_success()
            await user.add_bits(self.view.profit)
            embed.add_field(
                name="Purse",
                value=f"{await user.get_bits():,} bits *(+{self.view.profit:,})*",
                inline=False,
            )
        else:
            embed = self.view.generate_embed(False)
            embed.change_to_failure()
        self.view.clear_items()
        self.view.stop()
        await interaction.response.edit_message(embed=embed, view=self.view)


class TriviaGame(discord.ui.View):

    letters = (AE.LETTER_A.value, AE.LETTER_B.value, AE.LETTER_C.value, AE.LETTER_D.value)
    letters_unicode = (AU.LETTER_A.value, AU.LETTER_B.value, AU.LETTER_C.value, AU.LETTER_D.value)

    def __init__(self, interaction, client: TriviaAPIClient):
        super().__init__()
        self.interaction = interaction
        self.user: User = interaction.extras.get("user")
        self.client = client
        self.timer = 10
        self.question = self.client.get_random_question(limit=1)[0]
        self.profit = get_profit(self.question["difficulty"])
        self.answers = [self.correct_answer] + self.incorrect_answers
        random.shuffle(self.answers)
        self.embed = None

    async def interaction_check(self, interaction):
        return interaction.user == self.interaction.user

    def generate_embed(self, correct: bool = None):
        title = f"Trivia! {self.timer}"
        if correct is True:
            title = "Trivia! | CORRECT"
        elif correct is False:
            title = "Trivia! | INCORRECT"

        embed = CustomEmbed(
            title=title,
            desc=f"*{self.text}*",
            color=get_color(self.question["difficulty"]),
            interaction=self.interaction,
            activity="quizbowling",
        )
        category: str = self.question["category"]
        embed.add_field(name="Category", value=category.replace("_", " ").title())
        embed.add_field(name="Difficulty", value=self.question["difficulty"].capitalize())

        # Add the answers
        for i, answer in enumerate(self.answers):
            right_answer = answer == self.question["correctAnswer"]
            if correct is not None and right_answer:
                embed.description += f"\n> **{self.letters[i]} {answer}**"
            elif correct is not None:
                embed.description += f"\n> {self.letters[i]} ~~{answer}~~"
            else:
                embed.description += f"\n> {self.letters[i]} {answer}"
        return embed

    def add_buttons(self):
        for i, answer in enumerate(self.answers):
            is_correct = answer == self.question["correctAnswer"]
            self.add_item(AnswerButton(emoji=self.letters_unicode[i], is_correct=is_correct))

    @property
    def text(self) -> str:
        return self.question["question"]["text"]

    @property
    def correct_answer(self) -> str:
        return self.question["correctAnswer"]

    @property
    def incorrect_answers(self) -> list:
        return self.question["incorrectAnswers"]

    async def tick(self):
        # Tick down the timer and update the embed every second
        for _ in range(0, 10):
            await asyncio.sleep(1)
            self.timer -= 1
            if self.is_finished():
                return
            await self.interaction.edit_original_response(embed=self.generate_embed(), view=self)

        embed = self.generate_embed(False)
        embed.change_to_failure()
        embed.title = "Trivia! TIMES UP."
        self.clear_items()
        self.stop()
        await self.interaction.edit_original_response(embed=embed, view=self)


class Trivia(BaseCog, name="Trivia"):
    """Answer trivia questions for bits."""

    def __init__(self):
        super().__init__()
        self.client = TriviaAPIClient()

    @app_commands.command(name="trivia")
    async def trivia(self, interaction: Interaction):
        game = TriviaGame(interaction, self.client)
        game.add_buttons()
        await interaction.response.send_message(embed=game.generate_embed(), view=game)
        await interaction.extras.get("user").inc_stat("trivia_games")
        await game.tick()


async def setup(bot):
    await bot.add_cog(Trivia())
