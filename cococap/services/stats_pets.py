"""The Pets stat page (Player > Stats): built from numbers the game already stores plus counters recorded from the update on."""

from cococap import emojis
from cococap.registry import get_registry
from cococap.services.pets import pet_level
from cococap.services.stats import StatPage, seen
from cococap.user import User


async def page(user: User, stats: dict[str, int]) -> StatPage:
    reg = get_registry()
    house = user.pethouse  # derived: what the pethouse already holds, so existing players see it at once
    levels = [
        pet_level(owned.xp, reg.pets[pid].rarity, reg) for pid, owned in house.pets.items() if pid in reg.pets
    ]
    active = reg.pets[house.active].name if house.active in reg.pets else "None"
    return StatPage("pets", "Pets", emojis.icon("scroll", "📊"), [
        ("Collection", [
            ("Pets owned", len(house.pets)),
            ("Highest pet level", max(levels, default=0)),
            ("Active pet", active),
        ]),
        ("Care", [
            ("Orbs opened", seen(stats, "orbs_opened")),
            ("Pet foods fed", seen(stats, "pet_foods_fed")),
        ]),
    ])
