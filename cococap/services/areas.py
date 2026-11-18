"""Areas and the ship (configs/areas.toml). No Discord here.

A player has a ship tier (0 = no ship yet), the highest area they have reached, and the area they are in now. An area caps how far
each skill's locations open (`open_locations`). Travelling to an area you have already reached is free; the first trip to the
next one burns its fuel and needs the ship tier. State is one small JSON document per player (services.community), so no migration.
"""

from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import LOCATIONS_PER_AREA, Area, Location, ShipTier
from cococap.services import community, payment
from cococap.user import User

SKILLS = ("mining", "fishing", "foraging", "farming")


class AreaError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


@dataclass(frozen=True)
class ShipState:
    tier: int  # 0 = no ship
    current: int  # index into the registry's areas
    highest: int


def _key(user_id: int) -> str:
    return f"ship:{user_id}"


_DEFAULT = {"tier": 0, "current": 0, "highest": 0}


def _clean(data: dict, reg: Registry) -> ShipState:
    last = len(reg.areas.areas) - 1
    highest = min(max(int(data.get("highest", 0)), 0), last)
    current = min(max(int(data.get("current", 0)), 0), highest)
    return ShipState(min(max(int(data.get("tier", 0)), 0), len(reg.areas.ship_tiers)), current, highest)


async def state(user: User, registry: Registry | None = None) -> ShipState:
    reg = registry or get_registry()
    return _clean(await community.read(_key(user.id), _DEFAULT), reg)


async def current_area(user: User, registry: Registry | None = None) -> Area:
    reg = registry or get_registry()
    return reg.areas.areas[(await state(user, reg)).current]


def area_of_location(n: int) -> int:
    """The index of the area that location `n` (1-based) lives in: two locations per area."""
    return (n - 1) // LOCATIONS_PER_AREA


async def skill_level(user: User, skill: str) -> int:
    return User.xp_to_level((await user.skill(skill)).xp)


async def open_locations(user: User, skill: str, registry: Registry | None = None) -> int:
    """How many of a skill's locations you can use right now (they open in order, so it is "the first N"). A location needs BOTH its skill
    level and for you to be in its area (or a later one): the area is a ceiling, so a maxed skill still waits on the ship."""
    reg = registry or get_registry()
    st = await state(user, reg)
    level = await skill_level(user, skill)
    count = 0
    for n, need in enumerate(reg.areas.location_levels, 1):
        if need > level or area_of_location(n) > st.current:
            break
        count = n
    return count


async def reached_locations(user: User, skill: str, registry: Registry | None = None) -> int:
    """Like `open_locations`, but by the farthest area you have EVER reached, not the one you are in: used for what stays buyable after
    you travel back (farming's seeds)."""
    reg = registry or get_registry()
    st = await state(user, reg)
    level = await skill_level(user, skill)
    count = 0
    for n, need in enumerate(reg.areas.location_levels, 1):
        if need > level or area_of_location(n) > st.highest:
            break
        count = n
    return count


async def open_location_list(user: User, skill: str, registry: Registry | None = None) -> list[Location]:
    """The named locations of a skill you can use right now, in unlock order (the first N of the skill's list)."""
    reg = registry or get_registry()
    return reg.locations.get(skill, [])[: await open_locations(user, skill, reg)]


def location(skill: str, location_id: str, registry: Registry | None = None) -> Location:
    """One named location by id (saved in player state). Raises AreaError for an unknown id."""
    reg = registry or get_registry()
    for loc in reg.locations.get(skill, []):
        if loc.id == location_id:
            return loc
    raise AreaError("There is no such location.")


async def next_location_hint(user: User, skill: str, registry: Registry | None = None) -> str | None:
    """Why the next location is still shut ("Reach the Rust Belt" / "Needs level 19"), or None when every location is open."""
    reg = registry or get_registry()
    opened = await open_locations(user, skill, reg)
    levels = reg.areas.location_levels
    if opened >= len(levels):
        return None
    n = opened + 1
    st = await state(user, reg)
    level = await skill_level(user, skill)
    problems = []
    if levels[n - 1] > level:
        problems.append(f"level {levels[n - 1]} {skill}")
    if area_of_location(n) > st.current:
        problems.append(f"be in {reg.areas.areas[area_of_location(n)].name}")
    return "Needs " + " and ".join(problems)


def next_tier(st: ShipState, reg: Registry) -> ShipTier | None:
    """The ship upgrade to buy next (tier 1 builds the ship), or None when the ship is fully upgraded."""
    tiers = reg.areas.ship_tiers
    return tiers[st.tier] if st.tier < len(tiers) else None


async def _levels(user: User) -> dict[str, int]:
    return {skill: await skill_level(user, skill) for skill in SKILLS}


async def upgrade_ship(user: User, registry: Registry | None = None) -> ShipTier:
    """Build the ship (first time) or upgrade it one tier: skill floors are checked, then bits and parts are taken together."""
    reg = registry or get_registry()
    st = await state(user, reg)
    tier = next_tier(st, reg)
    if tier is None:
        raise AreaError("Your ship is fully upgraded.")
    levels = await _levels(user)
    short = [f"{skill} {need} (you are {levels[skill]})" for skill, need in tier.skill_floors.items() if levels[skill] < need]
    if short:
        raise AreaError(f"The {tier.name} needs: " + ", ".join(short) + ".")
    await payment.pay(user, tier.bits, tier.parts, reg, AreaError)

    def bump(data: dict) -> None:
        data.update({"tier": st.tier + 1, "current": st.current, "highest": st.highest})

    try:
        await community.update(_key(user.id), _DEFAULT, bump)
    except Exception:
        await payment.refund(user, tier.bits, tier.parts)
        raise
    return tier


async def travel(user: User, area_id: str, registry: Registry | None = None) -> Area:
    """Sail to an area. Any area you have reached is free; the next new one needs the ship tier and burns its fuel."""
    reg = registry or get_registry()
    areas = reg.areas.areas
    target = next((i for i, a in enumerate(areas) if a.id == area_id), None)
    if target is None:
        raise AreaError("There is no such area.")
    st = await state(user, reg)
    if target == st.current:
        raise AreaError(f"You are already in {areas[target].name}.")
    if target > st.highest + 1:
        raise AreaError(f"You must reach {areas[st.highest + 1].name} first.")
    area = areas[target]
    burned = target > st.highest
    if burned:
        if st.tier < target:
            raise AreaError(f"You need ship tier {target} to sail to {area.name}.")
        await payment.pay(user, 0, area.fuel, reg, AreaError)

    def move(data: dict) -> None:
        latest = _clean(data, reg)
        data.update({"tier": latest.tier, "current": target, "highest": max(latest.highest, target)})

    try:
        await community.update(_key(user.id), _DEFAULT, move)
    except Exception:
        if burned:
            await payment.refund(user, 0, area.fuel)
        raise
    return area
