import discord
import random
import pathlib
import asyncio
import logging
import copy

from discord.ext import commands
from discord import app_commands

from cococap.user import User
from utils.custom_embeds import Cembed

log = logging.getLogger(__name__)


class UnscrambleCog(commands.Cog, name="Unscramble"):
    """Unscramble a scrambled word for some bits."""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

        project_files = pathlib.Path.cwd() / "resources"
        with open(project_files / "unscramble_words.txt", "r") as f:
            self.words = f.readlines()

    @app_commands.command(name="unscramble")
    async def unscramble(self, interaction: discord.Interaction):
        """Try to unscramble a word for some bits. The longer the word, the more bits you get!"""
        user = User(interaction.user.id)
        await user.load()

        stats = user.document.gambling_statistics

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
        unscramble_prompt_embed = Cembed(
            title="Unscramble!",
            desc=f"You will have {time_limit.__round__()} seconds to unscramble the following word!",
            color=0xA0A39D,
            interaction=interaction,
            activity="unscrambling",
        )
        shuffled_word_embed = Cembed(
            title="Unscramble!",
            desc=f"You will have {time_limit.__round__()} seconds to unscramble the following word!\n"
            f"***{scrambled_word}***",
            color=0xA0A39D,
            interaction=interaction,
            activity="unscrambling",
        )
        await interaction.response.send_message(embed=unscramble_prompt_embed)
        await asyncio.sleep(2)
        await interaction.edit_original_response(embed=shuffled_word_embed)

        def check(m):
            return (
                m.content.lower() == word
                and m.author == interaction.user
                and m.channel == interaction.channel
            )

        try:  # Waits for a guess at the correct word
            guess = await self.bot.wait_for("message", timeout=time_limit.__round__(), check=check)
            embed = None
            if guess.content.lower() == word:
                # The user guessed the word correctly.
                log.debug(f"User guessed {word} correctly.")

                correct_word_embed = Cembed(
                    title="Unscramble!",
                    desc=f"Correct!\n" f"***{scrambled_word}*** - {word}",
                    color=0xA0F09C,
                    interaction=interaction,
                    activity="unscrambling",
                )

                stats["current_unscramble_streak"] += 1

                if stats["current_unscramble_streak"] > stats["longest_unscramble_streak"]:
                    stats["longest_unscramble_streak"] = stats["current_unscramble_streak"]
                    correct_word_embed.set_footer(
                        text=f"New streak record of {stats['current_unscramble_streak']}! Keep going!"
                    )
                else:
                    correct_word_embed.set_footer(
                        text=f"Current streak: {stats['current_unscramble_streak']}"
                    )
                reward = reward * (2 * stats["current_unscramble_streak"])
                correct_word_embed.add_field(name="Reward", value=f"**{reward:,}** bits")

                embed = correct_word_embed
                await user.inc_purse(reward)

        except asyncio.TimeoutError:
            # The user took too long to guess and loses.
            log.debug(f"User took too long to guess {word}.")

            too_slow_embed = Cembed(
                title="Unscramble!",
                desc=f"Too slow!\n" f"***{scrambled_word}*** - {word}",
                color=0xA8332F,
                interaction=interaction,
                activity="unscrambling",
            )
            if stats["current_unscramble_streak"] > 0:
                too_slow_embed.set_footer(
                    text=f"You lost your streak of {stats['current_unscramble_streak']}."
                )
            embed = too_slow_embed

            stats["current_unscramble_streak"] = 0
            await user.save()

        await interaction.edit_original_response(embed=embed)


async def setup(bot):
    await bot.add_cog(UnscrambleCog(bot))
