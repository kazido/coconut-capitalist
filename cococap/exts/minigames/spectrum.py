import discord

import random
import asyncio

from discord import app_commands
from discord.ext import commands
from discord.app_commands import Choice

from cococap.user import User
from utils.custom_embeds import Cembed


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
        difficulties = {
            0: {"options": ["😂", "😍"], "reward_multiplier": 5},
            1: {"options": ["🟥", "🟦", "🟧", "🟩"], "reward_multiplier": 10},
            2: {"options": ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"], "reward_multiplier": 40},
        }
        # Load the user
        user = User(interaction.user.id)
        await user.load()

        options = difficulties[difficulty.value]["options"]
        pattern = [random.choice(options)]
        difficulty_multiplier = difficulties[difficulty.value]["reward_multiplier"]

        async def button_callback(
            view, button_interaction: discord.Interaction, button: discord.ui.Button
        ):
            if button_interaction.user != interaction.user:
                await button_interaction.response.send_message(
                    "This is not your game!", ephemeral=True
                )
                return view.total_score

            if str(view.sequence[view.index]) != str(
                button.emoji
            ):  # If the user picks the wrong button
                played = (
                    1 if view.total_score > 0 else 0
                )  # Adds no reward if they didn't even get 1 right
                reward = view.total_score * (difficulty_multiplier * view.total_score**2) + (
                    300 * played
                )  # Score calculation
                wrong_embed = Cembed(
                    title="GAME OVER!",
                    desc=f"You got the pattern wrong :sob:",
                    colour=discord.Color.blurple(),
                    interaction=interaction,
                    activity="sequence",
                )
                wrong_embed.add_field(
                    name="Final Score", value=f"**{view.total_score}** elements :white_check_mark:"
                )
                wrong_embed.add_field(
                    name="Reward", value=f"**{reward:,}** bits :money_with_wings:"
                )
                await user.inc_purse(amount=reward)
                await button_interaction.response.edit_message(embed=wrong_embed, view=None)
                await asyncio.sleep(0.7)

                wrong_embed.set_field_at(
                    index=0,
                    name="Final Score",
                    value=f"**{view.total_score}** elements :black_large_square:",
                )
                await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                await asyncio.sleep(0.25)

                for elem in view.sequence:  # Show pattern at the end
                    wrong_embed.set_field_at(
                        index=0, name="Final Score", value=f"**{view.total_score}** elements {elem}"
                    )
                    await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                    await asyncio.sleep(0.7)

                    wrong_embed.set_field_at(
                        index=0,
                        name="Final Score",
                        value=f"**{view.total_score}** elements :black_large_square:",
                    )
                    await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                    await asyncio.sleep(0.25)

                wrong_embed.set_field_at(
                    index=0,
                    name="Final Score",
                    value=f"**{view.total_score}** elements :white_check_mark:",
                )
                await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                return view.total_score

            for child in view.children:
                child.disabled = True

            embed = Cembed(
                title="Recall the order!",
                desc="" + f"{view.sequence[view.index]}" * 6,
                color=discord.Color.blue(),
                interaction=interaction,
                activity="sequence",
            )
            embed.set_footer(text=f"Element: {view.index + 1}")
            await button_interaction.response.edit_message(embed=embed, view=view)
            await asyncio.sleep(0.05)
            embed.description = "" + (":black_large_square:" * 6)
            if view.index + 1 == len(view.sequence):  # If element is last element in the list
                view.total_score += 1
                embed = Cembed(
                    title="Pattern Remembered!",
                    desc=f"Current score: **{view.total_score}** elements :white_check_mark:\n"
                    f"Next round starting!",
                    color=discord.Color.green(),
                    interaction=interaction,
                    activity="sequence",
                )
                view.sequence.append(random.choice(options))
                await asyncio.sleep(0.2)
                await button_interaction.edit_original_response(embed=embed, view=None)
                await asyncio.sleep(1)
                await show_pattern(button_interaction, view.sequence, view.total_score)
            else:
                view.index += 1
                await button_interaction.edit_original_response(
                    embed=embed,
                    view=SequenceGame(
                        view.sequence, view.index, view.total_score, difficulty.value
                    ),
                )

        class SequenceGame(discord.ui.View):
            def __init__(self, sequence, index, total_score, selected_difficulty: int):
                super().__init__()
                self.sequence: list = sequence
                self.index = index
                self.total_score = total_score
                for emoji_number, emoji in enumerate(
                    difficulties[selected_difficulty]["options"], start=1
                ):
                    self.add_item(SequenceButton(emoji, emoji_number))

        class SequenceButton(discord.ui.Button):
            def __init__(self, emoticon, buttonno):
                self.emoticon = emoticon
                if buttonno > 4:
                    self.row = 2
                else:
                    self.row = 1
                super().__init__(emoji=self.emoticon, style=discord.ButtonStyle.grey, row=self.row)

            async def callback(self, button_interaction: discord.Interaction):
                self.view.total_score = await button_callback(
                    self.view, button_interaction, button=self
                )

        # When game is ready to begin, send the initial embed and show the pattern
        async def show_pattern(inter: discord.Interaction, seq: list, tot_score: int):
            pattern_interval = 0.4 if len(seq) < 15 else 0.2
            for element in seq:  # show each element in the pattern
                embed = Cembed(
                    title="Remember this!",
                    desc="" + (f"{element}" * 6),
                    color=discord.Color.blue(),
                    interaction=interaction,
                    activity="sequence",
                )
                await inter.edit_original_response(embed=embed)
                embed.description = "" + (":black_large_square:" * 6)
                await asyncio.sleep(pattern_interval)

                await inter.edit_original_response(embed=embed)
                await asyncio.sleep(0.05)
            user_ready_embed = Cembed(
                title="Recall the order!",
                desc="Push the buttons in the order they are shown!\n"
                "Mess up the order and the **game will end**.",
                color=discord.Color.blue(),
                interaction=interaction,
                activity="sequence",
            )
            await inter.edit_original_response(
                embed=user_ready_embed, view=SequenceGame(seq, 0, tot_score, difficulty.value)
            )

        initial_ready_embed = Cembed(
            title="Welcome to Spectrum Sequence!",
            desc="Push the buttons in the order they are shown!\n"
            "Mess up the order and the **game will end**.",
            color=discord.Color.blue(),
            interaction=interaction,
            activity="sequence",
        )
        await interaction.response.send_message(embed=initial_ready_embed)
        await asyncio.sleep(1.5)
        await show_pattern(interaction, pattern, 0)
