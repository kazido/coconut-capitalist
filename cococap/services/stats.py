"""The /stats pages as plain data (no Discord), so the hub and any command can show them."""

from dataclasses import dataclass

from cococap import emojis
from cococap.user import User

SKILL_ICONS = {"farming": "🌽", "foraging": "🌳", "fishing": "🐟", "mining": "⛏️", "combat": "⚔️"}


@dataclass(frozen=True)
class StatPage:
    key: str
    title: str
    emoji: str
    groups: list[tuple[str, list[tuple[str, int | str]]]]  # [(group name, [(label, value)])]


def seen(stats: dict[str, int], name: str, seed: int = 0) -> int:
    """A counter's value: its row if it has one, else what the game already knew from another source (`seed`, 0 if nothing)."""
    return stats.get(name, seed)


# One page per skill, built by services/stats_<name>.py (`async def page(user, stats) -> StatPage`). A page reads numbers the game already stores
# directly (so existing players keep theirs) and counters that only exist from the update on (they start at 0, silently).
PAGE_MODULES = ("mining", "fishing", "foraging", "farming", "pets", "shipments")


class Money(int):
    """A luckbucks amount: a plain int to the code, shown with the luckbucks icon on the page."""


async def skill_pages(user: User, stats: dict[str, int]) -> list[StatPage]:
    import importlib

    pages = []
    for name in PAGE_MODULES:
        module = importlib.import_module(f"cococap.services.stats_{name}")
        pages.append(await module.page(user, stats))
    return pages


async def stat_pages(user: User) -> list[StatPage]:
    s = await user.stats()
    g = lambda name: s.get(name, 0)  # never recorded reads as 0
    skills = {name: await user.skill(name) for name in SKILL_ICONS}
    skill_lines = [
        ("Farming", f"Lv {User.xp_to_level(skills['farming'].xp)} · {skills['farming'].stats.crops_grown:,} crops grown"),
        ("Foraging", f"Lv {User.xp_to_level(skills['foraging'].xp)} · {skills['foraging'].stats.trees_chopped:,} trees chopped"),
        ("Fishing", f"Lv {User.xp_to_level(skills['fishing'].xp)} · {skills['fishing'].stats.fish_caught:,} fish caught"),
        ("Mining", f"Lv {User.xp_to_level(skills['mining'].xp)} · {skills['mining'].stats.lodes_mined:,} lodes mined"),
        ("Combat", f"Lv {User.xp_to_level(skills['combat'].xp)} · {skills['combat'].stats.monsters_slain:,} monsters slain"),
    ]
    return [
        StatPage("general", "General", emojis.icon('scroll', '🔢'), [("Economy", [
            ("Drops claimed", g("drops_claimed")), ("Tokens earned", g("tokens_earned")),
            ("Luckbucks earned", g("luckbucks_earned")), ("Times begged", g("times_begged")),
            ("Deposits", g("deposits")), ("Withdraws", g("withdraws")),
            ("Work claimed", g("claimed_work")), ("Daily claimed", g("claimed_daily")),
            ("Weekly claimed", g("claimed_weekly")),
        ])]),
        StatPage("minigames", "Minigames", emojis.icon('dice', '🎲'), [
            ("High-Low", [("Wins", g("hl_wins")), ("Longest win streak", g("longest_hl_streak")),
                          ("Longest loss streak", g("longest_hl_loss_streak")),
                          ("Biggest win", Money(g("biggest_hl_win"))), ("Biggest loss", Money(g("biggest_hl_loss")))]),
            ("Blackjack", [("Games", g("blackjack_games")), ("Blackjacks", g("blackjacks")),
                           ("Hits", g("blackjack_hits")), ("Stands", g("blackjack_stands")),
                           ("Folds", g("blackjack_folds"))]),
            ("Casino betting", [
                ("Games played", g("highlow_games") + g("blackjack_games")),
                ("Biggest bet", Money(g("biggest_bet"))), ("Total wagered", Money(g("casino_wagered")))]),
            ("Casino results", [
                ("Total won", Money(g("casino_won"))), ("Total lost", Money(g("casino_lost"))),
                ("Net", Money(g("casino_won") - g("casino_lost")))]),
            ("Unscramble", [("Current streak", g("unscramble_streak")), ("Longest streak", g("longest_unscramble_streak"))]),
            ("Flashcard", [("Current streak", g("flashcard_streak")), ("Longest streak", g("longest_flashcard_streak"))]),
            ("Other", [("Sequence best", g("longest_sq_streak")), ("Trivia wins", g("trivia_wins")), ("Trivia games", g("trivia_games"))]),
        ]),
        StatPage("skills", "Levels", emojis.icon('skills', '📈'), [("Levels", skill_lines)]),
        *await skill_pages(user, s),
    ]
