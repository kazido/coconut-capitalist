import discord
from discord.ext import commands
from discord import app_commands

from cococap.errors import CustomError
from cococap.user import User
from utils.custom_embeds import CustomEmbed
from cococap.registry import get_registry


async def process_rank_purchase(interaction: discord.Interaction, user: User, rank):
    """Charge the tokens and promote the user, atomically. Raises if they can't afford it."""
    if not await user.rank_up(rank.rank_id, rank.token_price):
        raise CustomError(
            "You can't rank up right now.",
            footer="You need enough tokens, and this must be your next rank.",
        )
    embed = CustomEmbed(
        title="Purchased!",
        description=f"You are now rank: **{rank.display_name}** {rank.emoji}!",
        color=discord.Color.green(),
        interaction=interaction,
        activity="ranking up",
    )
    await interaction.response.edit_message(embed=embed, view=None)


class RankupButton(discord.ui.Button):
    def __init__(self, next_rank, affordable: bool):
        super().__init__(
            label=f"Rankup: {next_rank.token_price}",
            emoji="🪙",
            style=discord.ButtonStyle.green if affordable else discord.ButtonStyle.red,
            disabled=not affordable,
        )

    async def callback(self, interaction: discord.Interaction):
        view: "Rankup" = self.view
        await process_rank_purchase(interaction, view.user, view.next_rank)


class Rankup(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, next_rank):
        super().__init__()
        self.interaction = interaction
        self.user: User = interaction.extras.get("user")
        self.next_rank = next_rank
        affordable = self.user.tokens >= next_rank.token_price
        self.add_item(RankupButton(next_rank, affordable))

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.interaction.user


class RanksCog(commands.Cog):
    """Rank up for a higher wage!"""

    async def interaction_check(self, interaction: discord.Interaction):
        user = await User.get(interaction.user.id)
        interaction.extras.update(user=user)
        registry = get_registry()
        rank = registry.rank(user.rank)
        interaction.extras.update(rank=rank)
        interaction.extras.update(next_rank=registry.next_rank(rank.rank_id))  # None at max rank
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
        embed.add_field(name="Wage", value=f"{rank.wage:,} bits")

        view = None
        if next_rank:
            embed.add_field(
                name="Next Rank",
                value=f"{next_rank.display_name} "
                f"{next_rank.emoji}\n"
                f"Wage: {next_rank.wage:,} bits",
                inline=False,
            )
            view = Rankup(interaction, next_rank)
        else:
            embed.add_field(
                name="Max rank achieved",
                value="You've reached the max rank! Nice job!",
                inline=False,
            )

        embed.set_thumbnail(url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=embed, view=view or discord.utils.MISSING)


async def setup(bot):
    await bot.add_cog(RanksCog(bot))
