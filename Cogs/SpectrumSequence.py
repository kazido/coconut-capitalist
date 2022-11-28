from discord import app_commands
from discord.ext import commands
import discord

import random
import asyncio

from classLibrary import RequestUser


class SpectrumCog(commands.Cog, name='Spectrum'):
    """Remember the pattern and try to get a high score."""

    def __init__(self, bot):
        self.bot = bot
        self.tree = self.bot.tree

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name='spectrum', description="Remember the pattern, win some bits!")
    async def spectrum(self, interaction: discord.Interaction):
        user = RequestUser(interaction.user.id, interaction=interaction)
        options = ['🟥', '🟦', '🟧', '🟩']
        pattern = [random.choice(options)]

        async def button_callback(this, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user != interaction.user:
                await button_interaction.response.send_message("This is not your game!", ephemeral=True)
                return this.total_score
            if str(this.sequence[this.index]) != str(button.emoji):
                played = 1 if this.total_score > 0 else 0  # Adds no reward if they didn't even get 1 right
                reward = this.total_score * (10 * this.total_score ** 2) + (300 * played)
                wrong_embed = discord.Embed(title="GAME OVER!",
                                            description=f"You got the pattern wrong :sob:",
                                            colour=discord.Color.blurple())
                wrong_embed.add_field(name="Final Score", value=f"**{this.total_score}** colors :white_check_mark:")
                wrong_embed.add_field(name="Reward", value=f"**{reward:,}** bits :money_with_wings:")
                user.update_balance(reward)
                wrong_embed.set_author(name=f"{interaction.user.name} - SPECTRUM SEQUENCE",
                                       icon_url=interaction.user.display_avatar)
                await button_interaction.response.edit_message(embed=wrong_embed, view=None)
                await asyncio.sleep(0.7)

                wrong_embed.set_field_at(index=0, name="Final Score",
                                         value=f"**{this.total_score}** colors :black_large_square:")
                await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                await asyncio.sleep(0.25)

                for elem in this.sequence:  # Show pattern at the end
                    wrong_embed.set_field_at(index=0, name="Final Score",
                                             value=f"**{this.total_score}** colors {elem}")
                    await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                    await asyncio.sleep(0.7)

                    wrong_embed.set_field_at(index=0, name="Final Score",
                                             value=f"**{this.total_score}** colors :black_large_square:")
                    await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                    await asyncio.sleep(0.25)

                wrong_embed.set_field_at(index=0, name="Final Score",
                                         value=f"**{this.total_score}** colors :white_check_mark:")
                await button_interaction.edit_original_response(embed=wrong_embed, view=None)
                return this.total_score

            this.option1.disabled = True
            this.option2.disabled = True
            this.option3.disabled = True
            this.option4.disabled = True
            embed = discord.Embed(title="Recall the order!",
                                  description="" + f"{this.sequence[this.index]}" * 6,
                                  color=discord.Color.blue())
            embed.set_author(name=f"{interaction.user.name} - SPECTRUM SEQUENCE",
                             icon_url=interaction.user.display_avatar)
            embed.set_footer(text=f"Color: {this.index + 1}")
            await button_interaction.response.edit_message(embed=embed, view=this)
            await asyncio.sleep(0.05)
            embed.description = "" + (":black_large_square:" * 6)
            if this.index + 1 == len(this.sequence):  # If element is last element in the list
                this.total_score += 1
                embed = discord.Embed(title="Pattern Remembered!",
                                      description=f"Current score: **{this.total_score}** colors :white_check_mark:\n"
                                                  f"Next round starting!",
                                      color=discord.Color.green())
                embed.set_author(name=f"{interaction.user.name} - SPECTRUM SEQUENCE",
                                 icon_url=interaction.user.display_avatar)
                this.sequence.append(random.choice(options))
                await asyncio.sleep(0.2)
                await button_interaction.edit_original_response(embed=embed, view=None)
                await asyncio.sleep(1)
                await show_pattern(button_interaction, this.sequence, this.total_score)
            else:
                this.index += 1
                await button_interaction.edit_original_response(embed=embed,
                                                                view=TestButtons(this.sequence, this.index,
                                                                                 this.total_score))

        class TestButtons(discord.ui.View):
            def __init__(self, sequence, index, total_score):
                self.sequence: list[options] = sequence
                self.index = index
                self.total_score = total_score
                super().__init__()

            @discord.ui.button(emoji='🟥', style=discord.ButtonStyle.grey)
            async def option1(self, option1_interaction: discord.Interaction, button: discord.ui.Button):
                self.total_score = await button_callback(self, option1_interaction, button)

            @discord.ui.button(emoji='🟦', style=discord.ButtonStyle.grey)
            async def option2(self, option2_interaction: discord.Interaction, button: discord.ui.Button):
                self.total_score = await button_callback(self, option2_interaction, button)

            @discord.ui.button(emoji='🟧', style=discord.ButtonStyle.grey)
            async def option3(self, option3_interaction: discord.Interaction, button: discord.ui.Button):
                self.total_score = await button_callback(self, option3_interaction, button)

            @discord.ui.button(emoji='🟩', style=discord.ButtonStyle.grey)
            async def option4(self, option4_interaction: discord.Interaction, button: discord.ui.Button):
                self.total_score = await button_callback(self, option4_interaction, button)

        async def show_pattern(inter: discord.Interaction, seq: list[options], tot_score: int):
            for element in seq:  # show each element in the pattern
                embed = discord.Embed(title="Remember this!",
                                      description="" + (f"{element}" * 6),
                                      color=discord.Color.blue())
                embed.set_author(name=f"{interaction.user.name} - SPECTRUM SEQUENCE",
                                 icon_url=interaction.user.display_avatar)
                await inter.edit_original_response(embed=embed)
                embed.description = "" + (":black_large_square:" * 6)
                await asyncio.sleep(0.4)

                await inter.edit_original_response(embed=embed)
                await asyncio.sleep(0.05)
            user_ready_embed = discord.Embed(title="Recall the order!",
                                             description="Push the buttons in the order they are shown!\n"
                                                         "Mess up the order and the **game will end**.",
                                             color=discord.Color.blue())
            user_ready_embed.set_author(name=f"{interaction.user.name} - SPECTRUM SEQUENCE",
                                        icon_url=interaction.user.display_avatar)
            await inter.edit_original_response(embed=user_ready_embed, view=TestButtons(seq, 0, tot_score))

        initial_ready_embed = discord.Embed(title="Welcome to Spectrum Sequence!",
                                            description="Push the buttons in the order they are shown!\n"
                                                        "Mess up the order and the **game will end**.",
                                            color=discord.Color.blue())
        initial_ready_embed.set_author(name=f"{interaction.user.name} - SPECTRUM SEQUENCE",
                                       icon_url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=initial_ready_embed)
        await asyncio.sleep(1.5)
        await show_pattern(interaction, pattern, 0)


async def setup(bot):
    await bot.add_cog(SpectrumCog(bot))
