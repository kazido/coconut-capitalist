import discord
from discord.ext import commands
from discord import app_commands

from cococap.user import User
from utils.custom_embeds import CustomEmbed
from game_data.converters.data_converter import fetch


async def process_rank_purchase(interaction, rank):
    user: User = interaction.extras.get("user")
    embed = CustomEmbed(
        title="Purchased!",
        description=f"You are now rank: **{rank.display_name}** " f"{rank.emoji}!",
        color=discord.Color.green(),
        interaction=interaction,
        activity="ranking up",
    )
    user.update_field("rank", int(rank.rank_id))
    await user.inc_tokens(tokens=-int(rank.token_price))
    await interaction.edit_original_response(embed=embed, view=None)


class Rankup(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction
        self.user = interaction.extras.get("user")
        self.next_rank = interaction.extras.get("next_rank")
        self.rankup_button = RankupButton(next_rank=self.next_rank)
        self.add_item(self.rankup_button)

    def update_button_state(self):
        # Call this after the view is created and user data is available
        if self.user.get_field("tokens") < int(self.next_rank.token_price):
            self.rankup_button.disabled = True
            self.rankup_button.style = discord.ButtonStyle.red
        else:
            self.rankup_button.disabled = False
            self.rankup_button.style = discord.ButtonStyle.green

    async def interaction_check(self, interaction):
        return interaction.user == self.interaction.user


class RankupButton(discord.ui.Button):
    def __init__(self, next_rank):
        label = f"Rankup: {next_rank.token_price}"
        emoji = "🪙"
        style = discord.ButtonStyle.red
        disabled = True
        return super().__init__(label=label, style=style, emoji=emoji, disabled=disabled)

    def update_button(self):
        # Determine if the button can be pressed
        if self.view.user.get_field("tokens") > int(self.view.interaction.next_rank.token_price):
            self.style = discord.ButtonStyle.green
            self.disabled = False

    async def callback(self, interaction):
        await process_rank_purchase(self.view.interaction, self.view.next_rank)


class RanksCog(commands.Cog):
    """Rank up for a higher wage!"""

    async def interaction_check(self, interaction: discord.Interaction):
        user = await User(interaction.user.id).load()
        interaction.extras.update(user=user)
        rank = fetch("ranks." + str(user.get_field("rank")))
        next_rank = fetch("ranks." + str(int(rank.rank_id) + 1))
        interaction.extras.update(rank=rank)
        interaction.extras.update(next_rank=next_rank)
        return super().interaction_check(interaction)

    @app_commands.command(name="rank")
    async def rank(self, interaction: discord.Interaction):
        """Check your current rank and it's perks."""
        rank = interaction.extras.get("rank")
        next_rank = interaction.extras.get("next_rank")

        # Displays the user's current rank.
        embed = CustomEmbed(
            title=f"Current Rank: *{rank.display_name}* {rank.emoji}",
            desc=f"{rank.description}",
            color=discord.Color.from_str("#" + rank.color),
            interaction=interaction,
            activity="checking rank",
        )
        embed.add_field(name="Wage", value=f"{int(rank.wage):,} bits")

        # Finds the next rank in the list and displays the price of the next rank in the embed
        if fetch("ranks." + str(int(rank.rank_id) + 1)):
            embed.add_field(
                name="Next Rank",
                value=f"{next_rank.display_name} "
                f"{next_rank.emoji}\n"
                f"Wage: {int(next_rank.wage):,} bits",
                inline=False,
            )
        else:
            embed.add_field(
                name="Max rank achieved",
                value="You've reached the max rank! Nice job!",
                inline=False,
            )

        embed.set_thumbnail(url=interaction.user.display_avatar)
        view = Rankup(interaction)
        view.update_button_state()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(RanksCog(bot))
