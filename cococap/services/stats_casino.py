"""The Casino stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.services.stats import StatPage, seen
from cococap.user import User


async def page(user: User, stats: dict[str, int]) -> StatPage:
    won, lost = seen(stats, "casino_won"), seen(stats, "casino_lost")
    # Games played comes from the per-game counters the Gambling page already shows, so existing players keep theirs.
    games = seen(stats, "highlow_games") + seen(stats, "blackjack_games")
    return StatPage("casino", "Casino", emojis.icon("scroll", "📊"), [
        ("Betting", [
            ("Games played", games),
            ("Biggest bet", seen(stats, "biggest_bet")),
            ("Total wagered", seen(stats, "casino_wagered")),
        ]),
        ("Results", [
            ("Total won", won),
            ("Total lost", lost),
            ("Net", won - lost),
        ]),
    ])
