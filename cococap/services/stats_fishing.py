"""The Fishing stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.registry import get_registry
from cococap.services.stats import StatPage, seen
from cococap.user import User

RARITIES = range(1, 8)


async def page(user: User, stats: dict[str, int]) -> StatPage:
    reg = get_registry()
    skill = await user.skill("fishing")
    fishing = skill.stats

    # Derived from what the game already keeps: per-species counts and personal records (no new counters needed).
    by_rarity = {r: 0 for r in RARITIES}
    for fish_id, count in fishing.caught.items():
        item = reg.items.get(fish_id)
        if item is not None and item.rarity in by_rarity:
            by_rarity[item.rarity] += count
    best = max(skill.records.items(), key=lambda kv: kv[1], default=None)
    if best is None:
        biggest = "None yet"
    else:
        fish = reg.items.get(best[0])
        biggest = f"{best[1]:g} cm · {fish.name if fish else best[0]}"

    return StatPage(
        "fishing",
        "Fishing",
        emojis.icon("scroll", "📊"),
        [
            ("Catches", [
                ("Fish caught", fishing.fish_caught),
                ("Species caught", len(fishing.caught)),
                ("Biggest fish", biggest),
            ]),
            ("Fish by rarity", [(f"Rarity {r}", by_rarity[r]) for r in RARITIES]),
            ("Streaks", [
                # seeded from the run the player is on, so existing players see their current run until a longer one is caught
                ("Longest clean-reel streak", seen(stats, "longest_fishing_streak", seed=skill.streak)),
            ]),
            ("Bosses", [("Bosses beaten", fishing.bosses_beaten)] + [(name, count) for name, count in fishing.bosses.items()]),
            ("Treasure and quests", [
                ("Treasures found", fishing.treasures_found),
                ("Quests completed", fishing.quests_completed),
            ]),
            ("Pots and radar", [
                ("Crab pot hauls", seen(stats, "crab_pot_hauls")),
                ("Radar scans", seen(stats, "radar_scans")),
            ]),
            ("Level", [("Fishing level", User.xp_to_level(skill.xp)), ("Fishing xp", f"{skill.xp:,}")]),
        ],
    )
