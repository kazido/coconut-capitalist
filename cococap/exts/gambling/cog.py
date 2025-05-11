import discord

from discord import app_commands, Interaction
from discord.ext import commands

from cococap.user import User
from cococap.exts.utils.error import InvalidBet
from .blackjack import Blackjack, Actions


class Casino(commands.Cog, name="Casino"):
    """Casino games. The house always wins..."""

    async def cog_before_invoke(self, ctx):
        # Load user data before each command
        user = await User(ctx.author.id).load()
        ctx.interaction.extras.update(user=user)
        return await super().cog_before_invoke(ctx)

    @app_commands.command(name="blackjack")
    @app_commands.describe(bet="amount of bits you want to bet")
    async def blackjack(self, interaction: Interaction, bet: int):
        """Classic blackjack. Get as close to 21 as possible, but not over."""
        user: User = interaction.extras.get("user")
        purse = user.get_field("purse")

        # Bet validation
        if bet <= 0 or bet > purse:
            raise InvalidBet(f"Invalid bet. You have {purse:,} bits in your purse.")

        # Collect their bet immediately
        await user.inc_purse(-bet)

        view = Blackjack(interaction=interaction, bet=bet)
        await interaction.response.send_message(embed=view.update(Actions.DEAL), view=view)

        # Deal out starting hands for dealer and player
        await view.deal_card_animated(view.player)
        await view.deal_card_animated(view.player)
        await view.deal_card_animated(view.dealer)

        for item in view.children:
            item.disabled = False

        await interaction.edit_original_response(view=view)

    @app_commands.command(name="highlow")
    @app_commands.describe(bet="amount of bits you want to bet")
    async def highlow(self, interaction: Interaction, bet: int):
        user: User = interaction.extras.get("user")
        purse = user.get_field("purse")
