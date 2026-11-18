from random import Random

from discord import Interaction, app_commands
from discord.ext import commands

from cococap import constants
from cococap.screens import open_screen
from cococap.services import blackjack
from cococap.user import User


class Blackjack(commands.Cog, name="Blackjack"):
    """Blackjack! Remember, the house always wins..."""

    @app_commands.command(name="blackjack", description="Beat the dealer to 21.")
    @app_commands.describe(bet="amount to bet: 500, 2k, 25% or max")
    async def blackjack(self, interaction: Interaction, bet: str):
        user = await User.get(interaction.user.id)
        game = await blackjack.start(user, bet, Random(), constants.CASINO_CURRENCY)
        try:
            await open_screen(interaction, "games", tab="blackjack", game=game, bet_text=bet)
        except Exception:
            if not game.settled:  # the hand never showed: give the bet back instead of forfeiting it
                game.settled = True
                await user.credit(game.currency, game.bet)
            raise


async def setup(bot):
    await bot.add_cog(Blackjack())
