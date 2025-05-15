from discord import app_commands, Interaction
from discord.ext import commands

from cococap.user import User
from cococap.exts.utils.error import InvalidAmount
from utils.utils import validate_bits
from ._blackjack import Blackjack, Actions
from ._high_low import HighLow


class Casino(commands.Cog, name="Casino"):
    """Casino games. The house always wins..."""

    def __init__(self):
        super().__init__()

    async def interaction_check(self, interaction: Interaction):
        # Load user data before each command
        user = await User(interaction.user.id).load()
        interaction.extras.update(user=user)

        # Validate the user's bet so they can't bet more than they have
        args = {opt["name"]: opt["value"] for opt in interaction.data.get("options", [])}
        bet = validate_bits(user=user, amount=args["bet"])

        # Collect their bet immediately
        await user.inc_purse(-bet)
        interaction.extras.update(bet=bet)

        return super().interaction_check(interaction)

    @app_commands.command(name="blackjack")
    @app_commands.describe(bet="the amount of bits you want to bet")
    async def _blackjack(self, interaction: Interaction, bet: str):
        """Classic blackjack. Get as close to 21 as possible, but not over."""
        view = Blackjack(interaction=interaction)
        await interaction.response.send_message(embed=await view.update(Actions.DEAL), view=view)

        # Deal out starting hands for dealer and player
        await view.deal_card(view.player)
        await view.deal_card(view.player)
        await view.deal_card(view.dealer)

        for item in view.children:
            item.disabled = False

        await interaction.edit_original_response(view=view)

    @app_commands.command(name="highlow")
    @app_commands.describe(bet="amount of bits you want to bet")
    async def highlow(self, interaction: Interaction, bet: str):
        """Guess if the number will be high (6-10) or low (1-5)."""
        view = HighLow(interaction=interaction)
        await interaction.response.send_message(embed=view.get_embed(), view=view)


async def setup(bot):
    await bot.add_cog(Casino())
