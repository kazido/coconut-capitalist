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
        StatPage("gambling", "Gambling", emojis.icon('money', '🎰'), [
            ("High-Low", [("Wins", g("hl_wins")), ("Longest win streak", g("longest_hl_streak")),
                          ("Longest loss streak", g("longest_hl_loss_streak")),
                          ("Biggest win", g("biggest_hl_win")), ("Biggest loss", g("biggest_hl_loss"))]),
            ("Blackjack", [("Games", g("blackjack_games")), ("Blackjacks", g("blackjacks")),
                           ("Hits", g("blackjack_hits")), ("Stands", g("blackjack_stands")),
                           ("Folds", g("blackjack_folds"))]),
        ]),
        StatPage("minigames", "Minigames", emojis.icon('dice', '🎲'), [
            ("Unscramble", [("Current streak", g("unscramble_streak")), ("Longest streak", g("longest_unscramble_streak"))]),
            ("Flashcard", [("Current streak", g("flashcard_streak")), ("Longest streak", g("longest_flashcard_streak"))]),
            ("Other", [("Sequence best", g("longest_sq_streak")), ("Trivia wins", g("trivia_wins")), ("Trivia games", g("trivia_games"))]),
        ]),
        StatPage("skills", "Skills", emojis.icon('milestone', '📈'), [("Levels", skill_lines)]),
    ]
