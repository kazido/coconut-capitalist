import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from cococap.user import User
from cococap.item_models import Ranks
from cococap.utils.messages import Cembed, button_check


class RanksCog(commands.Cog):
    """Rank up for a higher wage!"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="rank")
    async def rank(self, interaction: discord.Interaction):
        """Check your current rank and it's perks."""
        # Grabs the ranks from the class library and determines which discord role the user has
        user = User(interaction.user.id)
        user_rank = await user.get_user_rank()
        await user.load()

        # Displays the user's current rank.
        embed = Cembed(
            title=f"Current Rank: *{user_rank.display_name}* {user_rank.emoji}",
            desc=f"{user_rank.description}",
            color=discord.Color.from_str("#" + user_rank.color),
            interaction=interaction,
            activity="checking rank",
        )

        embed.add_field(name="Wage", value=f"{user_rank.wage:,} bits")
        # Finds the next rank in the list and displays the price of the next rank in the embed
        if user_rank.next_rank_id:
            next_rank: Ranks = Ranks.get_by_id(user_rank.next_rank_id)
            embed.add_field(
                name="Next Rank",
                value=f"{next_rank.display_name} "
                f"{next_rank.emoji}\n"
                f"Wage: {next_rank.wage:,} bits",
                inline=False,
            )
        else:
            embed.add_field(
                name="Max rank achieved",
                value="You've reached the max rank! Nice job!",
                inline=False,
            )

        class RolePurchaseButton(discord.ui.View):
            def __init__(self):
                super().__init__()
                if user.get_field("tokens") < next_rank.token_price:
                    self.purchase.style = discord.ButtonStyle.red
                    self.purchase.disabled = True

            @discord.ui.button(
                label=f"Rankup: {next_rank.token_price:,}", style=discord.ButtonStyle.green, emoji="🪙"
            )
            async def purchase(self, p_interaction: discord.Interaction, button: discord.ui.Button):
                if not await button_check(p_interaction, [interaction.user.id]):
                    return
                role_to_add = discord.utils.get(
                    p_interaction.guild.roles, id=self.next_rank.rank_id
                )
                role_to_remove = discord.utils.get(
                    p_interaction.guild.roles, id=self.user_rank.rank_id
                )
                purchased_embed = Cembed(
                    title="Purchased!",
                    description=f"You are now rank: **{self.next_rank.display_name}** "
                    f"{self.next_rank.emoji}!",
                    color=discord.Color.green(),
                    interaction=p_interaction,
                    activity="ranking up",
                )
                await interaction.edit_original_response(embed=purchased_embed, view=None)
                await p_interaction.user.add_roles(role_to_add)
                await p_interaction.user.remove_roles(role_to_remove)
                await user.inc_tokens(tokens=-next_rank.token_price)

        embed.set_thumbnail(url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=embed, view=RolePurchaseButton())

async def setup(bot):
    await bot.add_cog(RanksCog(bot))
