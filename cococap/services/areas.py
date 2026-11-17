"""Areas and the ship (configs/areas.toml). No Discord here.

A player has a ship tier (0 = no ship yet), the highest area they have reached, and the area they are in now. An area caps how far
each skill's zones open (`max_zone`, `max_water`). Travelling to an area you have already reached is free; the first trip to the
next one burns its fuel and needs the ship tier. State is one small JSON document per player (services.community), so no migration.
"""

from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import Area, ShipTier
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


async def max_zone(user: User, registry: Registry | None = None) -> int:
    """The deepest foraging zone the area you are in allows (the foraging level is still needed on top)."""
    return (await current_area(user, registry)).foraging_max_zone


async def max_water(user: User, registry: Registry | None = None) -> str:
    """The id of the deepest fishing water the area you are in allows."""
    return (await current_area(user, registry)).fishing_max_water


def next_tier(st: ShipState, reg: Registry) -> ShipTier | None:
    """The ship upgrade to buy next (tier 1 builds the ship), or None when the ship is fully upgraded."""
    tiers = reg.areas.ship_tiers
    return tiers[st.tier] if st.tier < len(tiers) else None


async def _levels(user: User) -> dict[str, int]:
    return {skill: User.xp_to_level((await user.skill(skill)).xp) for skill in SKILLS}


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
