import discord
import random
import asyncio
import logging

from discord.ext import commands
from discord import app_commands

from cococap.user import User
from utils.custom_embeds import CustomEmbed, FailureEmbed, SuccessEmbed

log = logging.getLogger(__name__)


class FlashcardCog(commands.Cog, name="Flashcard"):
    """Solve a math problem for some bits!"""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @app_commands.command(name="flashcard")
    async def flashcard(self, interaction: discord.Interaction):
        """Try to solve a math problem for some bits!"""
        user = await User.get(interaction.user.id)
        await user.inc_stat("flashcard_games")

        operator = random.choice(["+", "-", "*"])
        x = random.randint(10, 20)
        y = random.randint(10, 20)

        problem = f"{x} {operator} {y}"
        match operator:
            case "+":
                answer = x + y
                time_limit = 3
                reward = 5000
            case "-":
                answer = x - y
                time_limit = 5
                reward = 10000
            case "*":
                answer = x * y
                time_limit = 15
                reward = 20000

        embed = CustomEmbed(
            title="Flashcard!",
            desc=f"You will have {time_limit} seconds to solve the following problem!",
            color=0xA0A39D,
            interaction=interaction,
            activity="flashcarding",
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(2)
        embed.color = discord.Color.blue()
        embed.description += f"\n{problem} = ?"
        await interaction.edit_original_response(embed=embed)

        def check(m):
            return m.content.lower() == str(answer) and m.channel == interaction.channel

        try:  # Waits for a guess at the correct word
            guess = await self.bot.wait_for("message", timeout=time_limit.__round__(), check=check)
            helper = None
            if guess.author != interaction.user:
                helper = guess.author
            if guess.content.lower() == str(answer):
                embed = SuccessEmbed(
                    title="Flashcard!",
                    desc=f"Correct!\n" f"{problem} = **{answer}**",
                    interaction=interaction,
                    activity="flashcarding",
                )

                await user.inc_stat("flashcard_streak")

                streak = await user.get_stat("flashcard_streak")
                longest_streak = await user.get_stat("longest_flashcard_streak")

                if streak > longest_streak:
                    await user.set_stat("longest_flashcard_streak", streak)
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
            embed = FailureEmbed(
                title="Flashcard!",
                desc=f"Too slow!\n" f"{problem} = **{answer}**",
                interaction=interaction,
                activity="flashcarding",
            )
            streak = await user.get_stat("flashcard_streak")
            if streak > 0:
                embed.set_footer(text=f"You lost your streak of {streak}.")
            await user.set_stat("flashcard_streak")

        await interaction.edit_original_response(embed=embed)


async def setup(bot):
    await bot.add_cog(FlashcardCog(bot))
