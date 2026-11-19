"""Pet sidekicks, the pure part: a pet's score from its simulated loadout, the sidekick bonus, the passive bonus and the idle haul.

No Discord and no DB writes. The numbers live in configs/pet_score.toml (`registry.pet_score`); the loadout in configs/pets.toml.
See docs/plans/pet-sidekicks.md. State (fuel tank, lent tool, food buff) is a later step.
"""
from __future__ import annotations

from collections.abc import Iterable

from cococap.models.pethouse import OwnedPet
from cococap.registry import Pet, Registry, get_registry
from cococap.services import pets


def loadout_points(pet: Pet, lent_tool_power: float = 0.0, registry: Registry | None = None) -> float:
    """What the pet's simulated kit is worth: tool tier, enchant levels, mastery points, plus a real lent tool's power."""
    rules = (registry or get_registry()).pet_score
    lo = pet.loadout
    return (lo.tool_tier * rules.tool_tier_weight
            + sum(lo.enchants.values()) * rules.enchant_level_weight
            + lo.mastery_score * rules.mastery_weight
            + max(0.0, lent_tool_power) * rules.lent_tool_weight)


def score(pet: Pet, owned: OwnedPet, lent_tool_power: float = 0.0, registry: Registry | None = None) -> float:
    """Loadout x proficiency x (level and stars), with a rarity bump. Rises with level, stars, rarity and the lent tool."""
    reg = registry or get_registry()
    rules = reg.pet_score
    proficiency = rules.global_proficiency if pet.skill == "global" else 1.0
    kit = loadout_points(pet, lent_tool_power, reg) * proficiency * pets.strength(owned, pet.rarity, reg)
    return kit * (1 + rules.rarity_weight * (pet.rarity - 1))


def sidekick_bonus(inactive: Iterable[tuple[Pet, OwnedPet]], registry: Registry | None = None) -> float:
    """Share added to the active pet's output from every inactive pet's combined levels and stars (capped)."""
    reg = registry or get_registry()
    rules = reg.pet_score
    points = sum(pets.pet_level(o.xp, p.rarity, reg) + o.stars * rules.sidekick_star_weight for p, o in inactive)
    return min(rules.sidekick_cap, points / rules.sidekick_per_points / 100)


def passive_bonus(pet_score: float, sidekick: float = 0.0, registry: Registry | None = None) -> float:
    """The small bonus while you play, as a share (0.05 = +5%). Stays when the fuel tank is empty."""
    rules = (registry or get_registry()).pet_score
    return min(rules.passive_cap, pet_score * rules.passive_per_score * (1 + sidekick))


def haul_xp_per_hour(pet_score: float, sidekick: float = 0.0, active_xp_per_hour: float | None = None,
                     fueled: bool = True, registry: Registry | None = None) -> float:
    """Idle skill xp per hour: zero with an empty tank, and never above `haul_active_share` of an active player's hour (when given)."""
    if not fueled:
        return 0.0
    rules = (registry or get_registry()).pet_score
    xp = pet_score * (1 + sidekick) * rules.haul_xp_per_score_hour
    if active_xp_per_hour is not None:
        xp = min(xp, active_xp_per_hour * rules.haul_active_share)
    return xp
