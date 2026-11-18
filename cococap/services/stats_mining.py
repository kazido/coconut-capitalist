"""The Mining stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.models.skills.mining import Mining
from cococap.registry import get_registry
from cococap.services import mastery
from cococap.services import mining as mine
from cococap.services.stats import StatPage, seen
from cococap.user import User

# Counters that only exist from this update on (no older source), so an existing player's count starts at 0 here.
NEW_COUNTERS = (
    "mines entered", "deepest row", "safe exits", "collapses", "vault floors", "wyrmholes found", "lifeline saves",
    "vents dug", "braces used", "bombs used", "magnet rows aimed", "implosion gems", "biggest haul", "ore counts",
)


async def page(user: User, stats: dict[str, int]) -> StatPage:
    skill: Mining = await user.skill("mining")
    level = User.xp_to_level(skill.xp)
    owned, _, free = await mastery.status(user, "mining")
    registry = get_registry()
    g = lambda name: seen(stats, name)  # (a new counter with no row reads as 0)

    ores = [
        (item.name, g(f"mining_ore_{item.id}"))
        for item in registry.items_for_skill("mining")
        if item.category == "material"
    ]
    groups = [
        ("Mining", [
            ("Level", level), ("Total xp", skill.xp),
            ("Lodes mined", skill.stats.lodes_mined), ("Lodes auto-mined", skill.stats.lodes_auto_mined),
            ("Reactor level", skill.reactor.level), ("Gems placed", f"{mine.gems_placed(skill)} of 4"),
            ("Mastery nodes owned", len(owned)), ("Mastery points free", free),
        ]),
        ("Descent", [
            ("Mines entered", g("mining_mines_entered")), ("Deepest row", g("mining_deepest_row")),
            ("Safe exits", g("mining_safe_exits")), ("Collapses", g("mining_collapses")),
            ("Lifeline saves", g("mining_lifeline_saves")), ("Vault floors", g("mining_vault_floors")),
            ("Wyrmholes found", g("mining_wyrmholes_found")), ("Implosion gems", g("mining_implosion_gems")),
        ]),
        ("Haul", [
            ("Biggest haul (bits)", g("mining_biggest_haul")), ("Vents dug", g("mining_vents_dug")),
            ("Braces used", g("mining_braces_used")), ("Bombs used", g("mining_bombs_used")),
            ("Magnet rows aimed", g("mining_magnet_rows")),
        ]),
        ("Ores mined", ores),
    ]
    return StatPage("mining", "Mining", emojis.icon("dig", "⛏️"), groups)
