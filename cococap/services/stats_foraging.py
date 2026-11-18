"""The Foraging stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.registry import get_registry
from cococap.services.stats import StatPage, seen
from cococap.user import User


async def page(user: User, stats: dict[str, int]) -> StatPage:
    reg = get_registry()
    skill = await user.skill("foraging")
    rarest = seen(stats, "rarest_drop")  # the most 1-in-N drop you have had (from felled trees)
    groups = [
        ("Trees", [
            ("Trees felled", skill.stats.trees_chopped),
            ("Rarest drop found", f"1 in {rarest:,}" if rarest else "none yet"),
        ]),
        ("Species felled", [(sp.name, seen(stats, f"felled:{sp.id}")) for sp in reg.foraging.species]),
        ("Chopping", [
            ("Chops", skill.stats.chops),
            ("Best chop streak", seen(stats, "best_chop_streak")),
            ("Clean grains", skill.stats.grains),
            ("Wedges used", seen(stats, "wedges_used")),
        ]),
        ("Groves", [
            ("Community tree hits", seen(stats, "community_hits")),
            ("Party tree hits", seen(stats, "party_hits")),
        ]),
        ("Releaf", [("Releaf donations", skill.stats.releaf_donations)]),
        ("Level", [("Level", User.xp_to_level(skill.xp)), ("XP", f"{skill.xp:,}")]),
    ]
    return StatPage("foraging", "Foraging", emojis.icon("scroll", "📊"), groups)
