"""The Foraging stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.services.stats import StatPage
from cococap.user import User


async def page(user: User, stats: dict[str, int]) -> StatPage:
    return StatPage("foraging", "Foraging", emojis.icon("scroll", "📊"), [], note="")
