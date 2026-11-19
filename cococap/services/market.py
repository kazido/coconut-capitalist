"""Part market: the Travelling Merchant and the Black Market sell smithing parts for bits (plan: docs/plans/part-market.md).

Stock is per player and needs no table: it is rolled from a seed of (player, shop, window), where the window is the hour (or day)
number, so it is the same every time you look inside one window. A bought slot is remembered with a stat.
Rules only (no Discord). Numbers live in configs/market.toml.
"""

import math
import random
import time
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.registry import Registry, get_registry
from cococap.registry.models import PART_TIERS, MarketShop
from cococap.services import areas, smithing
from cococap.user import InsufficientFunds, User

SHOPS = ("merchant", "black_market")


@dataclass(frozen=True)
class Offer:
    slot: int  # 0-based position in this window's stock
    part_type: str
    tier: int
    traits: tuple[str, ...]
    price: int
    bought: bool


def config(shop: str, registry: Registry | None = None) -> MarketShop:
    reg = registry or get_registry()
    if reg.market is None:
        raise RuntimeError("configs/market.toml is missing")
    if shop not in SHOPS:
        raise GameRuleError("Unknown shop.")
    return getattr(reg.market, shop)


def _window(cfg: MarketShop, now: float) -> int:
    return int(now // cfg.refresh_seconds)


def _bought_key(shop: str, window: int, slot: int) -> str:
    return f"market_{shop}_{window}_{slot}"


async def unlocked(user: User, shop: str, registry: Registry | None = None) -> bool:
    reg = registry or get_registry()
    cfg = config(shop, reg)
    index = next((i for i, a in enumerate(reg.areas.areas) if a.id == cfg.unlock_area), None)
    if index is None:
        raise RuntimeError(f"market.toml: unknown unlock_area '{cfg.unlock_area}'")
    return (await areas.state(user, reg)).highest >= index


def unlock_text(shop: str, registry: Registry | None = None) -> str:
    reg = registry or get_registry()
    cfg = config(shop, reg)
    area = next(a for a in reg.areas.areas if a.id == cfg.unlock_area)
    return f"The {cfg.name} is closed until you reach {area.name}."


def seconds_until_restock(shop: str, now: float | None = None, registry: Registry | None = None) -> int:
    cfg = config(shop, registry)
    now = time.time() if now is None else now
    return math.ceil((_window(cfg, now) + 1) * cfg.refresh_seconds - now)


async def stock(user: User, shop: str, now: float | None = None, registry: Registry | None = None) -> list[Offer]:
    """This window's offers for this player, with which of them they have already bought."""
    reg = registry or get_registry()
    cfg = config(shop, reg)
    now = time.time() if now is None else now
    window = _window(cfg, now)
    rules = smithing._rules(reg)
    pool = [t.id for t in rules.trait_pool]
    rng = random.Random(f"{user.id}:{shop}:{window}")
    offers = []
    for slot in range(cfg.slots):
        part_type = rng.choice(smithing.PART_TYPES)
        tier = rng.choices(range(1, PART_TIERS + 1), weights=cfg.tier_weights)[0]
        count = min(rules.fresh_trait_count(tier) + cfg.extra_traits, len(pool))
        traits = tuple(rng.sample(pool, count))
        price = round(cfg.tier_price[tier - 1] * (1 + cfg.trait_premium * len(traits)))
        bought = await user.get_stat(_bought_key(shop, window, slot)) > 0
        offers.append(Offer(slot, part_type, tier, traits, price, bought))
    return offers


async def buy(user: User, shop: str, slot: int, now: float | None = None, registry: Registry | None = None) -> Offer:
    """Charge the listed price and give the part exactly as it was rolled (same tier and traits)."""
    reg = registry or get_registry()
    cfg = config(shop, reg)
    now = time.time() if now is None else now
    if not await unlocked(user, shop, reg):
        raise GameRuleError(unlock_text(shop, reg))
    offers = await stock(user, shop, now, reg)
    if not 0 <= slot < len(offers):
        raise GameRuleError("That offer is gone.")
    offer = offers[slot]
    if offer.bought:
        raise GameRuleError("You already bought that one this restock.")
    try:
        await user.remove_bits(offer.price)
    except InsufficientFunds:
        raise GameRuleError(f"You need {offer.price:,} bits for that.") from None
    try:
        await user.give_instance(f"part_{offer.part_type}", rolled={"tier": offer.tier}, traits=list(offer.traits))
    except Exception:
        await user.add_bits(offer.price)  # the part never arrived: give the money back
        raise
    await user.set_stat(_bought_key(shop, _window(cfg, now), slot), 1)
    return Offer(slot, offer.part_type, offer.tier, offer.traits, offer.price, True)
