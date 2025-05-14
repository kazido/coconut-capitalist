import discord
import random
import asyncio
from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice
from cococap.user import User
from utils.custom_embeds import CustomEmbed, FailureEmbed

# Difficulty settings for the sequence game
DIFFICULTIES = {
    0: {"options": ["😂", "😍"], "reward_multiplier": 100},
    1: {"options": ["🟥", "🟦", "🟧", "🟩"], "reward_multiplier": 200},
    2: {"options": ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"], "reward_multiplier": 400},
}


class SequenceButton(discord.ui.Button):
    def __init__(self, emoticon, button_number):
        self.emoticon = emoticon
        row = 2 if button_number > 4 else 1
        super().__init__(emoji=self.emoticon, style=discord.ButtonStyle.grey, row=row)

    async def callback(self, interaction: discord.Interaction):
        view: SequenceGame = self.view
        # Check if the pressed button matches the current pattern element
        if str(view.sequence[view.index]) != str(self.emoji):
            reward = view.total_score * (view.difficulty * view.total_score**2) + (
                300 if view.total_score > 0 else 0
            )
            embed = FailureEmbed(
                title="GAME OVER!",
                desc=f"You got the pattern wrong :sob:",
                interaction=view.interaction,
                activity="sequence",
            )
            embed.add_field(
                name="Final Score",
                value=f"**{view.total_score}** elements :white_check_mark:",
            )
            embed.add_field(name="Reward", value=f"**{reward:,}** bits :money_with_wings:")
            await view.user.inc_purse(amount=reward)
            await interaction.response.edit_message(embed=embed, view=None)
            await asyncio.sleep(0.7)
            # Show the pattern at the end
            for elem in view.sequence:
                embed.set_field_at(
                    index=0,
                    name="Final Score",
                    value=f"**{view.total_score}** elements {elem}",
                )
                await interaction.edit_original_response(embed=embed, view=None)
                await asyncio.sleep(0.7)
                embed.set_field_at(
                    index=0,
                    name="Final Score",
                    value=f"**{view.total_score}** elements :black_large_square:",
                )
                await interaction.edit_original_response(embed=embed, view=None)
                await asyncio.sleep(0.25)
            embed.set_field_at(
                index=0,
                name="Final Score",
                value=f"**{view.total_score}** elements :white_check_mark:",
            )
            return await interaction.edit_original_response(embed=embed, view=None)

        # Correct button pressed
        for child in view.children:
            child.disabled = True
        embed = CustomEmbed(
            title="Recall the order!",
            desc=f"{view.sequence[view.index]}" * 6,
            color=discord.Color.blue(),
            interaction=view.interaction,
            activity="sequence",
        )
        embed.set_footer(text=f"Element: {view.index + 1}")
        await interaction.response.edit_message(embed=embed, view=view)
        await asyncio.sleep(0.05)
        embed.description = ":black_large_square:" * 6
        if view.index + 1 == len(view.sequence):
            view.total_score += 1
            embed = CustomEmbed(
                title="Pattern Remembered!",
                desc=f"Current score: **{view.total_score}** elements :white_check_mark:\nNext round starting!",
                color=discord.Color.green(),
                interaction=view.interaction,
                activity="sequence",
            )
            view.sequence.append(random.choice(view.options))
            await asyncio.sleep(0.2)
            await interaction.edit_original_response(embed=embed, view=None)
            await asyncio.sleep(1)
            await view.show_pattern(interaction, view.sequence, view.total_score)
        else:
            view.index += 1
            await interaction.edit_original_response(
                embed=embed,
                view=SequenceGame(
                    view.interaction,
                    view.sequence,
                    view.index,
                    view.total_score,
                    view.selected_difficulty,
                    view.user,
                ),
            )


class SequenceGame(discord.ui.View):
    def __init__(self, interaction, sequence, index, total_score, selected_difficulty, user):
        super().__init__()
        self.interaction = interaction
        self.sequence = sequence
        self.index = index
        self.total_score = total_score
        self.selected_difficulty = selected_difficulty
        self.options = DIFFICULTIES[selected_difficulty]["options"]
        self.difficulty = DIFFICULTIES[selected_difficulty]["reward_multiplier"]
        self.user = user
        for emoji_number, emoji in enumerate(self.options, start=1):
            self.add_item(SequenceButton(emoji, emoji_number))

    async def interaction_check(self, interaction):
        return self.interaction.user == interaction.user

    async def show_pattern(self, interaction: discord.Interaction, seq: list, tot_score: int):
        pattern_interval = 0.4 if len(seq) < 5 else 0.2
        embed = CustomEmbed(
            title="Remember this!",
            color=discord.Color.blue(),
            interaction=self.interaction,
            activity="sequence",
        )
        for element in seq:
            embed.description = f"{element}" * 6
            await interaction.edit_original_response(embed=embed)
            embed.description = ":black_large_square:" * 6
            await asyncio.sleep(pattern_interval)
            await interaction.edit_original_response(embed=embed)
            await asyncio.sleep(0.05)
        user_ready_embed = CustomEmbed(
            title="Recall the order!",
            desc="Push the buttons in the order they are shown!\nMess up the order and the **game will end**.",
            color=discord.Color.blue(),
            interaction=self.interaction,
            activity="sequence",
        )
        await interaction.edit_original_response(
            embed=user_ready_embed,
            view=SequenceGame(
                self.interaction, seq, 0, tot_score, self.selected_difficulty, self.user
            ),
        )


class SpectrumCog(commands.Cog, name="Spectrum"):
    """Remember the pattern and try to get a high score."""

    @app_commands.command(name="sequence", description="Remember the pattern, win some bits!")
    @app_commands.choices(
        difficulty=[
            Choice(name="easy", value=0),
            Choice(name="medium", value=1),
            Choice(name="hard", value=2),
        ]
    )
    async def spectrum(self, interaction: discord.Interaction, difficulty: Choice[int]):
        # Load the user
        user = await User(interaction.user.id).load()
        options = DIFFICULTIES[difficulty.value]["options"]
        pattern = [random.choice(options)]
        embed = CustomEmbed(
            title="Welcome to Spectrum Sequence!",
            desc="Push the buttons in the order they are shown!\nMess up the order and the **game will end**.",
            color=discord.Color.blue(),
            interaction=interaction,
            activity="sequence",
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(1.5)
        view = SequenceGame(interaction, pattern, 0, 0, difficulty.value, user)
        await view.show_pattern(interaction, pattern, 0)


async def setup(bot):
    await bot.add_cog(SpectrumCog(bot))
