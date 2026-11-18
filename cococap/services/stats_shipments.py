"""The Shipments stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.registry import get_registry
from cococap.services import shipments
from cococap.services.stats import StatPage, seen
from cococap.user import User


async def page(user: User, stats: dict[str, int]) -> StatPage:
    reg = get_registry()
    skills = list(dict.fromkeys(skill for skill, _tier in shipments.slot_ids(reg)))
    crates = await shipments.mine(user, reg)  # derived: the crates on your list right now
    ready = sum(1 for crate in crates if crate.done())
    return StatPage("shipments", "Shipments", emojis.icon("scroll", "📊"), [
        ("Shipped", [("Total crates", seen(stats, "shipments_shipped"))] + [
            (skill.capitalize(), seen(stats, f"shipped_{skill}")) for skill in skills
        ]),
        ("Bits", [("Total bits paid", seen(stats, "shipment_bits"))]),
        ("Right now", [("Ready to ship", ready), ("Still filling", len(crates) - ready)]),
    ])
