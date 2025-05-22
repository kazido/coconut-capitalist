import discord
import random
import pathlib
import asyncio
import logging

from discord.ext import commands
from discord import app_commands

from cococap.user import User
from utils.custom_embeds import CustomEmbed, FailureEmbed, SuccessEmbed

log = logging.getLogger(__name__)

with open(pathlib.Path.cwd() / "resources" / "unscramble_words.txt", "r") as f:
    WORDS = [w.strip() for w in f if w.strip().islower() and len(w.strip()) >= 4]


def get_word():
    """Gets a valid word from the list (lowercase, 4+ letters)"""
    return random.choice(WORDS)


def scramble_word(word: str):
    """Scrambles a word and returns it as a string (not equal to original)"""
    shuffled_word = list(word)
    while True:
        random.shuffle(shuffled_word)
        scrambled = "".join(shuffled_word)
        if scrambled != word:
            return scrambled


class UnscrambleGame:
    def __init__(self, user, bot, interaction):
        self.user = user
        self.bot = bot
        self.interaction = interaction
        self.word = get_word()
        self.scrambled = scramble_word(word=self.word)
        self.time_limit = 1.4 ** len(self.word)
        self.reward = len(self.word) * (10 * len(self.word) ** 2) + 300
        self.streak = None
        self.longest_streak = None
        self.helper = None
        self.guess = None
        self.success = False

    async def play(self):
        embed = CustomEmbed(
            title="Unscramble!",
            desc=f"You will have {round(self.time_limit)} seconds to unscramble the following word!",
            color=0xA0A39D,
            interaction=self.interaction,
            activity="unscrambling",
        )
        await self.interaction.response.send_message(embed=embed)
        await asyncio.sleep(2)
        embed.color = discord.Color.blue()
        embed.description += f"\n***{self.scrambled}***"
        await self.interaction.edit_original_response(embed=embed)

        def check(m):
            return m.content.lower() == self.word and m.channel == self.interaction.channel

        try:
            self.guess = await self.bot.wait_for(
                "message", timeout=round(self.time_limit), check=check
            )
            if self.guess.author != self.interaction.user:
                self.helper = self.guess.author
            self.success = True
        except asyncio.TimeoutError:
            self.success = False

    async def process_result(self):
        embed = CustomEmbed(
            title="Unscramble!",
            color=discord.Color.blue() if self.success else discord.Color.red(),
            interaction=self.interaction,
            activity="unscrambling",
        )
        if self.success:
            embed.description = f"Correct!\n***{self.scrambled}*** - {self.word}"
            embed.color = 0xA0F09C
            await self.user.inc_stat("unscramble_streak")
            self.streak = await self.user.get_stat("unscramble_streak")
            self.longest_streak = await self.user.get_stat("longest_unscramble_streak")
            if self.streak > self.longest_streak:
                await self.user.set_stat("longest_unscramble_streak", self.streak)
                embed.set_footer(text=f"New streak record of {self.streak}! Keep going!")
            else:
                embed.set_footer(text=f"Current streak: {self.streak}")
            reward = self.reward * self.streak
            if self.helper:
                embed.add_field(name="Reward", value=f"**{reward:,}** bits (shared)")
                embed.add_field(name="Helper", value=f"Helper: {self.helper.mention}")
                helper_user = await User.get(self.helper.id)
                await helper_user.add_bits(reward / 2)
                await self.user.add_bits(reward / 2)
            else:
                embed.add_field(name="Reward", value=f"**{reward:,}** bits")
                await self.user.add_bits(reward)
        else:
            embed.description = f"Too slow!\n***{self.scrambled}*** - {self.word}"
            self.streak = await self.user.get_stat("unscramble_streak")
            if self.streak > 0:
                embed.set_footer(text=f"You lost your streak of {self.streak}.")
            await self.user.set_stat("unscramble_streak")
        await self.interaction.edit_original_response(embed=embed)


class UnscrambleCog(commands.Cog, name="Unscramble"):
    """Unscramble a scrambled word for some bits."""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @app_commands.command(name="unscramble")
    async def unscramble(self, interaction: discord.Interaction):
        """Try to unscramble a word for some bits. The longer the word, the more bits you get!"""
        user = await User.get(interaction.user.id)
        await user.inc_stat("unscramble_games")
        game = UnscrambleGame(user, self.bot, interaction)
        await game.play()
        await game.process_result()


async def setup(bot):
    await bot.add_cog(UnscrambleCog(bot))
