"""Pet sidekicks, the pure part: a pet's score out of 1000, its working strength, the sidekick bonus, the passive bonus and the idle haul.

No Discord and no DB writes. The numbers live in configs/pet_score.toml (`registry.pet_score`); the loadout in configs/pets.toml.
See docs/plans/pet-score-1000.md. State (fuel tank, food buff) is in the pethouse.

The SCORE (out of 1000) is fixed per species: 500 skills (100 each over 5 skills) + 200 mastery + 200 gear + 100 ability. Level and stars do not change it;
they set how much of it the pet brings to bear (`pets.strength`), which drives its haul and the sidekick bonus.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cococap.models.pethouse import OwnedPet
from cococap.registry import Pet, Registry, get_registry
from cococap.services import pets

SKILLS = ("mining", "fishing", "foraging", "farming", "combat")
MAX_SKILL, MAX_MASTERY, MAX_GEAR, MAX_ABILITY = 100, 200, 200, 100


@dataclass(frozen=True)
class Score:
    skills: dict[str, int]  # points per skill, 0-100 each
    mastery: int  # 0-200
    gear: int  # 0-200
    ability: int  # 0, 50 or 100

    @property
    def skills_total(self) -> int:
        return sum(self.skills.values())

    @property
    def total(self) -> int:
        return self.skills_total + self.mastery + self.gear + self.ability


def total(pet: Pet, registry: Registry | None = None) -> Score:
    """The pet's score and where its points come from. A specialist puts its rarity's skill points into its one skill; a global pet spreads its total evenly."""
    rules = (registry or get_registry()).pet_score
    if pet.skill == "global":
        each = min(MAX_SKILL, rules.skill_points["global_total"][pet.rarity] // len(SKILLS))
        skills = dict.fromkeys(SKILLS, each)
    else:
        skills = dict.fromkeys(SKILLS, 0)
        skills[pet.skill] = min(MAX_SKILL, rules.skill_points["specialist"][pet.rarity])
    lo = pet.loadout
    gear = lo.tool_tier * rules.gear_per_tier + sum(lo.enchants.values()) * rules.gear_per_enchant_level
    return Score(skills, min(MAX_MASTERY, round(lo.mastery_score * rules.mastery_per_point)), min(MAX_GEAR, round(gear)), rules.ability_points[pet.ability])


def strength(pet: Pet, owned: OwnedPet, registry: Registry | None = None) -> float:
    """How much of its score a pet brings to bear: its score share (0-1) times its level and star strength."""
    reg = registry or get_registry()
    return total(pet, reg).total / 1000 * pets.strength(owned, pet.rarity, reg)


def score(pet: Pet, owned: OwnedPet, registry: Registry | None = None) -> float:
    """The working score on a 0-100+ scale (strength x 100): rises with level and stars, and with the pet's own 1000-point score."""
    return strength(pet, owned, registry) * 100


def sidekick_bonus(inactive: Iterable[tuple[Pet, OwnedPet]], registry: Registry | None = None) -> float:
    """Share added to the active pet's output from every inactive pet's strength (score share x level and stars), capped."""
    reg = registry or get_registry()
    rules = reg.pet_score
    return min(rules.sidekick_cap, sum(strength(p, o, reg) for p, o in inactive) * rules.sidekick_per_strength)


def passive_bonus(pet_score: float, sidekick: float = 0.0, registry: Registry | None = None) -> float:
    """The small bonus while you play, as a share (0.05 = +5%). Stays when the fuel tank is empty. (Not applied in play yet.)"""
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
