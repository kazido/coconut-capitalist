from random import Random

from discord import Interaction, app_commands
from discord.ext import commands

from cococap import constants
from cococap.screens import open_screen
from cococap.services import highlow
from cococap.user import User


class Highlow(commands.Cog, name="Highlow"):
    """Good old heads or tails, just more fun?"""

    @app_commands.command(name="highlow", description="Guess high (6-10) or low (1-5); double up or cash out.")
    @app_commands.describe(bet="amount to bet: 500, 2k, 25% or max")
    async def highlow(self, interaction: Interaction, bet: str):
        user = await User.get(interaction.user.id)
        game = await highlow.start(user, bet, Random(), constants.CASINO_CURRENCY)
        try:
            await open_screen(interaction, "games", tab="highlow", game=game, bet_text=bet)
        except Exception:
            await highlow.abandon(user, game)  # the game never showed: pay the bet straight back
            raise


async def setup(bot):
    await bot.add_cog(Highlow())
