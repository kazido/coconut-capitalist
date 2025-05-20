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


class UnscrambleCog(commands.Cog, name="Unscramble"):
    """Unscramble a scrambled word for some bits."""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

        with open(pathlib.Path.cwd() / "resources" / "unscramble_words.txt", "r") as f:
            self.words = f.readlines()

    @app_commands.command(name="unscramble")
    async def unscramble(self, interaction: discord.Interaction):
        """Try to unscramble a word for some bits. The longer the word, the more bits you get!"""
        user = await User.get(interaction.user.id)
        await user.inc_stat("unscramble_games")

        # Picks a random word from the file resources.unscramble_words.txt
        def get_word():
            random_word = random.choice(self.words)
            # If any letter in the word is uppercase, rerun the function.
            for letter in random_word:
                if letter.isupper():
                    return get_word()
            # If the word is shorter than 4 letters, rerun the function
            while len(random_word) < 4:
                return get_word()
            random_word = list(random_word)
            random_word.remove("\n")
            random_word = "".join(letter for letter in random_word)
            shuffled_word = "".join(random.sample(random_word, len(random_word)))
            while shuffled_word == random_word:
                shuffled_word = "".join(random.sample(random_word, len(random_word)))
            return random_word, shuffled_word

        word, scrambled_word = get_word()
        time_limit = 1.4 ** len(word)
        reward = len(word) * (10 * len(word) ** 2) + 300
        embed = CustomEmbed(
            title="Unscramble!",
            desc=f"You will have {time_limit.__round__()} seconds to unscramble the following word!",
            color=0xA0A39D,
            interaction=interaction,
            activity="unscrambling",
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(2)
        embed.color = discord.Color.blue()
        embed.description += f"\n***{scrambled_word}***"
        await interaction.edit_original_response(embed=embed)

        def check(m):
            return m.content.lower() == word and m.channel == interaction.channel

        try:  # Waits for a guess at the correct word
            guess: discord.Message = await self.bot.wait_for(
                "message", timeout=time_limit.__round__(), check=check
            )
            helper = None
            if guess.author != interaction.user:
                helper = guess.author
            if guess.content.lower() == word:
                # The user guessed the word correctly.
                embed = SuccessEmbed(
                    title="Unscramble!",
                    desc=f"Correct!\n" f"***{scrambled_word}*** - {word}",
                    interaction=interaction,
                    activity="unscrambling",
                )

                await user.inc_stat("unscramble_streak")

                streak = await user.get_stat("unscramble_streak")
                longest_streak = await user.get_stat("longest_unscramble_streak")

                if streak > longest_streak:
                    await user.set_stat("longest_unscramble_streak", streak)
                    embed.set_footer(text=f"New streak record of {streak}! Keep going!")
                else:
                    embed.set_footer(text=f"Current streak: {streak}")
                reward = reward * streak
                if helper:
                    embed.add_field(name="Reward", value=f"**{reward:,}** bits (shared)")
                    embed.add_field(name="Helper", value=f"Helper: {helper.mention}")
                    helper_user = await User.get(helper.id)
                    await helper_user.add_bits(reward / 2)
                    await user.add_bits(reward / 2)
                else:
                    embed.add_field(name="Reward", value=f"**{reward:,}** bits")
                    await user.add_bits(reward)

        except asyncio.TimeoutError:
            # The user took too long to guess and loses.
            embed = FailureEmbed(
                title="Unscramble!",
                desc=f"Too slow!\n" f"***{scrambled_word}*** - {word}",
                interaction=interaction,
                activity="unscrambling",
            )
            streak = await user.get_stat("unscramble_streak")
            if streak > 0:
                embed.set_footer(text=f"You lost your streak of {streak}.")
            await user.set_stat("unscramble_streak")

        await interaction.edit_original_response(embed=embed)


async def setup(bot):
    await bot.add_cog(UnscrambleCog(bot))
