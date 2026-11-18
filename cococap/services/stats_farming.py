"""The Farming stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.registry import get_registry
from cococap.services.stats import StatPage, seen
from cococap.user import User


async def page(user: User, stats: dict[str, int]) -> StatPage:
    reg = get_registry()
    skill = await user.skill("farming")
    crops = [i for i in reg.items_for_skill("farming") if i.category == "crop"]
    groups = [
        ("Harvest", [
            ("Crops harvested", skill.stats.crops_grown),
            ("Anomalies", seen(stats, "anomalies")),
        ]),
        ("Crops harvested by crop", [(c.name, seen(stats, f"harvested:{c.id}")) for c in crops]),
        ("Tending", [
            ("Tends", seen(stats, "tends")),
            ("Cycles tended", seen(stats, "cycles_tended")),
        ]),
        ("Watering", [("Plots watered", seen(stats, "plots_watered"))]),
        ("Land", [
            ("Most plots ready at once", seen(stats, "most_ready_at_once")),
            ("Deeds bought", seen(stats, "deeds_bought")),
            ("Blessings waiting", skill.rain_god_blessings),
            ("Blessings deposited", seen(stats, "blessings_deposited")),
            ("Deeds from blessings", seen(stats, "deeds_from_blessings")),
        ]),
        ("Market", [("Bits from crops sold", seen(stats, "crop_bits_sold"))]),
        ("Level", [("Level", User.xp_to_level(skill.xp)), ("XP", f"{skill.xp:,}")]),
    ]
    return StatPage("farming", "Farming", emojis.icon("scroll", "📊"), groups)
