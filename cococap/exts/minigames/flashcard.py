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
        user = await User(interaction.user.id).load()

        stats = user._document.gambling_statistics

        operator = random.choice(["+", "-", "*"])
        x = random.randint(1, 10)
        y = random.randint(1, 20)

        problem = f"{x} {operator} {y}"
        match operator:
            case "+":
                answer = x + y
                time_limit = 3
                reward = 10000
            case "-":
                answer = x - y
                time_limit = 5
                reward = 20000
            case "*":
                answer = x * y
                time_limit = 10
                reward = 30000

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

                stats["current_flashcard_streak"] += 1

                if stats["current_flashcard_streak"] > stats["longest_flashcard_streak"]:
                    stats["longest_flashcard_streak"] = stats["current_flashcard_streak"]
                    embed.set_footer(
                        text=f"New streak record of {stats['current_flashcard_streak']}! Keep going!"
                    )
                else:
                    embed.set_footer(text=f"Current streak: {stats['current_flashcard_streak']}")
                reward = reward * stats["current_flashcard_streak"]
                if helper:
                    embed.add_field(name="Reward", value=f"**{reward:,}** bits (shared)")
                    embed.add_field(name="Helper", value=f"Helper: {helper.mention}")
                    helper_user = await User(helper.id).load()
                    await helper_user.inc_purse(reward / 2)
                    await user.inc_purse(reward / 2)
                else:
                    embed.add_field(name="Reward", value=f"**{reward:,}** bits")
                    await user.inc_purse(reward)

        except asyncio.TimeoutError:
            embed = FailureEmbed(
                title="Flashcard!",
                desc=f"Too slow!\n" f"{problem} = **{answer}**",
                interaction=interaction,
                activity="flashcarding",
            )
            if stats["current_flashcard_streak"] > 0:
                embed.set_footer(
                    text=f"You lost your streak of {stats['current_flashcard_streak']}."
                )
            stats["current_flashcard_streak"] = 0
            await user.save()

        await interaction.edit_original_response(embed=embed)


async def setup(bot):
    await bot.add_cog(FlashcardCog(bot))
