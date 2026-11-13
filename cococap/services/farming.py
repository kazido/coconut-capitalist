"""Farming rules: plots, seeds, the hourly rain, harvesting and the Farmer's Market.

Rain is **computed, not scheduled**. Every hour it rains; each growing plot grows one cycle with
``grow_chance``. Instead of a background job touching every player each hour, a farm catches up on the rains it
missed whenever it is looked at or changed. Each roll is seeded by (player, plot, hour), so

* looking at the farm twice never changes the outcome (no re-rolling by reopening it),
* rain keeps falling while the bot is offline,
* tests can say "three hours later" without a clock or a scheduler.

Everything that changes a farm catches up first, inside the same transaction. All randomness other than the rain
comes from an injected ``random.Random``.
"""

import datetime
import random
import time
from collections import Counter
from dataclasses import dataclass

from cococap.errors import GameRuleError
from cococap.models.skills.farming import Farming, Plot
from cococap.registry import Registry, get_registry
from cococap.services.party import xp_multiplier
from cococap.user import Cooldowns, User

PLOTS = 9
MAX_CATCH_UP_HOURS = 24 * 400  # a farm left alone for over a year stops counting (and the loop stays bounded)
DAY = 86400


class FarmingError(GameRuleError):
    """A rule was broken; the message is safe to show the player."""


# ---- pure rules --------------------------------------------------------------------------------------
def hour_of(now: float) -> int:
    """The hour number a moment belongs to; the rain of hour h falls at its start."""
    return int(now // 3600)


def next_rain(now: float) -> int:
    """When it next rains (a unix time)."""
    return (hour_of(now) + 1) * 3600


def plot_of(farming: Farming, number: int) -> Plot:
    return getattr(farming.farm, f"plot_{number}")


def is_unlocked(farming: Farming, number: int, rules) -> bool:
    return number <= rules.free_plots or plot_of(farming, number).unlocked


def _grows(user_id: int, plot: int, hour: int, chance: float) -> bool:
    return random.Random(f"rain:{user_id}:{plot}:{hour}").random() < chance


def _blessed(user_id: int, hour: int, chance: float) -> bool:
    return random.Random(f"blessing:{user_id}:{hour}").random() < chance


@dataclass(frozen=True)
class RainReport:
    rains: int  # hours in which at least one of your plots grew
    blessings: int
    matured: tuple[int, ...]  # plot numbers that finished growing


def apply_rain(farming: Farming, user_id: int, now: float, registry: Registry) -> RainReport:
    """Catch the farm up on the rains since it was last looked at. Mutates `farming`; safe to repeat."""
    rules, hour = registry.farming, hour_of(now)
    grew_in: set[int] = set()
    matured: list[int] = []
    for number in range(1, PLOTS + 1):
        plot = plot_of(farming, number)
        if not plot.crop_id or plot.can_harvest:
            continue
        needed = registry.item(plot.crop_id).seed.cycles
        for h in range(max(plot.since, hour - MAX_CATCH_UP_HOURS) + 1, hour + 1):
            if _grows(user_id, number, h, rules.grow_chance):
                plot.cycle += 1
                grew_in.add(h)
                if plot.cycle >= needed:
                    plot.can_harvest = True
                    matured.append(number)
                    break
        plot.since = max(plot.since, hour)
    blessings = sum(_blessed(user_id, h, rules.blessing_chance) for h in sorted(grew_in))
    farming.rain_god_blessings += blessings
    return RainReport(len(grew_in), blessings, tuple(matured))


@dataclass(frozen=True)
class PlotView:
    """One plot as the screen needs it."""

    number: int
    unlocked: bool
    seed_id: str | None
    crop_id: str | None  # what it will give
    cycle: int
    needed: int
    ready: bool

    @property
    def empty(self) -> bool:
        return self.unlocked and self.seed_id is None

    @property
    def growing(self) -> bool:
        return self.seed_id is not None and not self.ready

    @property
    def progress(self) -> float:
        return min(1.0, self.cycle / self.needed) if self.needed else 0.0


def plot_views(farming: Farming, registry: Registry) -> list[PlotView]:
    views = []
    for number in range(1, PLOTS + 1):
        plot = plot_of(farming, number)
        seed = registry.item(plot.crop_id).seed if plot.crop_id else None
        views.append(PlotView(
            number, is_unlocked(farming, number, registry.farming), plot.crop_id,
            seed.grows_into if seed else None, plot.cycle, seed.cycles if seed else 0, plot.can_harvest,
        ))
    return views


def level_of(farming: Farming) -> int:
    return User.xp_to_level(farming.xp)


# ---- the Farmer's Market calendar --------------------------------------------------------------------
def _day(now: float) -> int:
    return int(now // DAY)


def _weekday(day: int) -> int:
    return datetime.datetime.fromtimestamp(day * DAY, datetime.UTC).weekday()


def market_window(now: float, registry: Registry) -> tuple[bool, int]:
    """(is it open, when does that change). Days are UTC; consecutive open days count as one opening."""
    days = registry.farming.market.days
    today = _day(now)
    is_open = _weekday(today) in days
    day = today
    for _ in range(8):
        day += 1
        if (_weekday(day) in days) != is_open:
            return is_open, day * DAY
    return is_open, (today + 1) * DAY  # every day is a market day (or none): "changes" at midnight


# ---- operations on a player (these persist) ------------------------------------------------------------
async def sync(user: User, now: float | None = None, registry: Registry | None = None) -> tuple[Farming, RainReport]:
    """Catch the farm up on the rain and return it (plus what the rain did)."""
    reg, now = registry or get_registry(), now if now is not None else time.time()
    seen: list[RainReport] = []
    farming = await user.update_skill("farming", lambda m: seen.append(apply_rain(m, user.id, now, reg)))
    return farming, seen[0]


async def buy_plot(user: User, number: int, registry: Registry | None = None) -> None:
    reg = registry or get_registry()
    rules = reg.farming
    if not rules.free_plots < number <= PLOTS:
        raise FarmingError("That plot can't be bought.")
    farming = await user.skill("farming")
    if is_unlocked(farming, number, rules):
        raise FarmingError("You already own that plot.")
    try:
        await user.remove_item(rules.deed_item, 1)
    except ValueError:
        raise FarmingError(f"You need a {reg.item(rules.deed_item).name} to buy a plot.") from None

    def unlock(m: Farming) -> None:
        plot_of(m, number).unlocked = True

    try:
        await user.update_skill("farming", unlock)
    except Exception:
        await user.add_item(rules.deed_item, 1)  # never swallow the deed
        raise


async def plant(
    user: User, number: int, seed_id: str, now: float | None = None, registry: Registry | None = None
) -> None:
    reg, now = registry or get_registry(), now if now is not None else time.time()
    seed = reg.find_item(seed_id)
    if seed is None or seed.seed is None:
        raise FarmingError("That isn't a seed.")
    if not 1 <= number <= PLOTS:
        raise FarmingError("There is no such plot.")
    try:
        await user.remove_item(seed_id, 1)
    except ValueError:
        raise FarmingError(f"You don't have any {seed.name}.") from None

    def sow(m: Farming) -> None:
        apply_rain(m, user.id, now, reg)
        plot = plot_of(m, number)
        if not is_unlocked(m, number, reg.farming):
            raise FarmingError("You don't own that plot yet.")
        if plot.crop_id:
            raise FarmingError("Something is already growing there.")
        plot.crop_id, plot.cycle, plot.can_harvest, plot.since = seed_id, 0, False, hour_of(now)

    try:
        await user.update_skill("farming", sow)
    except Exception:
        await user.add_item(seed_id, 1)  # the seed goes back in your pocket
        raise


@dataclass(frozen=True)
class Harvest:
    plot: int
    crop_id: str
    amount: int
    xp: int
    anomaly: bool


async def harvest(
    user: User, number: int, rng: random.Random, now: float | None = None, registry: Registry | None = None
) -> Harvest:
    reg, now = registry or get_registry(), now if now is not None else time.time()
    rules = reg.farming
    taken: dict = {}
    party_bonus = await xp_multiplier(user.id, reg)

    def pick(m: Farming) -> None:
        apply_rain(m, user.id, now, reg)
        plot = plot_of(m, number)
        if not (plot.crop_id and plot.can_harvest):
            raise FarmingError("Nothing is ready to harvest on that plot.")
        crop = reg.item(reg.item(plot.crop_id).seed.grows_into)
        taken.update(seed=plot.crop_id, crop=crop.id, amount=rng.randint(crop.crop.min_harvest, crop.crop.max_harvest),
                     xp=round(crop.rarity * rules.xp_per_rarity * party_bonus))
        plot.crop_id, plot.cycle, plot.can_harvest = None, 0, False  # the plot is empty from this moment: once only
        m.xp += taken["xp"]
        m.stats.crops_grown += taken["amount"]

    await user.update_skill("farming", pick)
    try:
        await user.add_item(taken["crop"], taken["amount"])
    except Exception:
        def restore(m: Farming) -> None:
            plot = plot_of(m, number)
            plot.crop_id, plot.can_harvest = taken["seed"], True

        await user.update_skill("farming", restore)  # the crop never arrived: the plot is still ripe
        raise
    anomaly = rng.randint(1, rules.anomaly_odds) == 1
    if anomaly:
        await user.refresh_cooldowns(Cooldowns.WORK, Cooldowns.DAILY)
    return Harvest(number, taken["crop"], taken["amount"], taken["xp"], anomaly)


async def harvest_all(
    user: User, rng: random.Random, now: float | None = None, registry: Registry | None = None
) -> list[Harvest]:
    farming, _ = await sync(user, now, registry)
    return [await harvest(user, v.number, rng, now, registry) for v in plot_views(farming, registry or get_registry()) if v.ready]


# ---- the Farmer's Market -----------------------------------------------------------------------------
async def _require_market(user: User, now: float, reg: Registry) -> None:
    farming = await user.skill("farming")
    if level_of(farming) < reg.farming.market.min_level:
        raise FarmingError(f"The Farmer's Market opens to farmers of level {reg.farming.market.min_level}.")
    if not market_window(now, reg)[0]:
        raise FarmingError("The Farmer's Market is closed. It opens on Fridays and Saturdays.")


def market_price(item_id: str, quantity: int, registry: Registry) -> int:
    return int(registry.item(item_id).sell_price * quantity * (1 + registry.farming.market.price_bonus))


async def sell_crops(user: User, now: float | None = None, registry: Registry | None = None) -> tuple[int, Counter[str]]:
    """Sell every crop you carry at the market price. Returns (bits earned, what was sold)."""
    reg, now = registry or get_registry(), now if now is not None else time.time()
    await _require_market(user, now, reg)
    sold: Counter[str] = Counter()
    earned = 0
    for item_id, quantity in (await user.items()).items():
        item = reg.find_item(item_id)
        if item is None or item.category != "crop" or not item.sellable or quantity < 1:
            continue
        try:
            await user.remove_item(item_id, quantity)
        except ValueError:
            continue  # sold or used elsewhere in the meantime
        pay = market_price(item_id, quantity, reg)
        try:
            await user.add_bits(pay)
        except Exception:
            await user.add_item(item_id, quantity)
            raise
        sold[item_id] += quantity
        earned += pay
    if not sold:
        raise FarmingError("You have no crops to sell.")
    await user.inc_stat("items_sold", sum(sold.values()))
    return earned, sold


async def deposit_blessings(
    user: User, rng: random.Random, now: float | None = None, registry: Registry | None = None
) -> tuple[int, int]:
    """Deposit every rain god's blessing you have. Each has a chance to become a land deed.
    Returns (blessings deposited, deeds received)."""
    reg, now = registry or get_registry(), now if now is not None else time.time()
    rules = reg.farming
    await _require_market(user, now, reg)
    taken = {"n": 0}

    def spend(m: Farming) -> None:
        apply_rain(m, user.id, now, reg)
        taken["n"], m.rain_god_blessings = m.rain_god_blessings, 0
        if not taken["n"]:
            raise FarmingError("You have no rain god's blessings to deposit.")

    await user.update_skill("farming", spend)
    deeds = sum(rng.random() < rules.market.deed_chance for _ in range(taken["n"]))
    if deeds:
        try:
            await user.add_item(rules.deed_item, deeds)
        except Exception:
            await user.update_skill("farming", lambda m: setattr(m, "rain_god_blessings", m.rain_god_blessings + taken["n"]))
            raise
    return taken["n"], deeds
