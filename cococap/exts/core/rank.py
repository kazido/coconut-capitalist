import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from cococap.user import User
from cococap.item_models import Ranks
from cococap.utils.messages import Cembed


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

        embed = Cembed(
            title=f"Current Rank: *{user_rank.display_name}* {user_rank.emoji}",
            color=discord.Color.from_str("#" + user_rank.color),
            interaction=interaction,
            activity="checking rank",
        )
        # If the role has permissions, display them
        # if user_rank:
        #     perms = ", ".join(ranks[user.rank]["perks"])
        # else:
        #     perms = "This rank has no special perks."
        # embed.add_field(name="Perks", value=perms)

        embed.add_field(name="Wage", value=f"{user_rank.wage:,} bits")
        # Finds the next rank in the list and displays the price of the next rank in the embed
        if user_rank.next_rank_id:
            next_rank: Ranks = Ranks.get_by_id(user_rank.next_rank_id)
            embed.add_field(
                name="Next Rank",
                value=f"{next_rank.display_name} "
                f"{next_rank.emoji}"
                f" | Cost: **{next_rank.token_price}** tokens",
                inline=False,
            )
        else:
            embed.add_field(
                name="Max rank achieved",
                value="You've reached the max rank! Nice job!",
                inline=False,
            )
        embed.set_thumbnail(url=interaction.user.display_avatar)
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(856915776345866240, 977351545966432306)
    @app_commands.command(name="rankup")
    async def rankup(self, interaction: discord.Interaction):
        """Spend tokens to move on to the next rank!"""
        # Load the user
        user = User(interaction.user.id)
        user_rank: Ranks = await user.get_user_rank()
        await user.load()

        if user_rank.next_rank_id:
            next_rank: Ranks = Ranks.get_by_id(user_rank.next_rank_id)

            rankup_embed = discord.Embed(
                title=f"{next_rank.display_name} {next_rank.emoji}",
                description=next_rank.description,
                color=discord.Color.from_str(f"#{next_rank.color}"),
            )
            rankup_embed.add_field(name="Wage", value=f"{next_rank.wage:,} bits")
            rankup_embed.set_footer(text="You will also receive a new name color.")

        else:
            embed = discord.Embed(
                title="Max rank!",
                description="You are already at the max rank!",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(embed=embed)
            return

        class RolePurchaseButtons(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=180)
                if user.get_field("tokens") < next_rank.token_price:
                    self.purchase.style = discord.ButtonStyle.red
                    self.purchase.disabled = True

            @discord.ui.button(
                label=f"{next_rank.token_price:,} tokens", style=discord.ButtonStyle.green
            )
            async def purchase(self, p_interaction: discord.Interaction, button: discord.ui.Button):
                if p_interaction.user != interaction.user:
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

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel_button(
                self, cancel_interaction: discord.Interaction, button: discord.ui.Button
            ):
                for child in self.children:
                    child.label = ":("
                    child.disabled = True
                if cancel_interaction.user != interaction.user:
                    return
                cancel_embed = discord.Embed(
                    title=f"Cancelled rankup to {next_rank.display_name} " f"{next_rank.emoji}",
                    description="Unfortunate. Maybe you'll rank up later?",
                    color=discord.Color.red(),
                )
                cancel_embed.add_field(
                    name="Hypothetical Wage", value=f"{next_rank.wage:,} bits"
                )
                cancel_embed.set_footer(text="You WOULD have received a new name color.")
                await cancel_interaction.response.edit_message(embed=cancel_embed, view=self)
                await asyncio.sleep(2)
                await interaction.delete_original_response()

        await interaction.response.send_message(embed=rankup_embed, view=RolePurchaseButtons())


async def setup(bot):
    await bot.add_cog(RanksCog(bot))
