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
from dataclasses import dataclass, field

from cococap.errors import GameRuleError
from cococap.models.skills.farming import Farming, Plot
from cococap.registry import Registry, get_registry
from cococap.services import areas, pets, scrolls, stars
from cococap.services.equipment import EffectiveStats, equipped_stats
from cococap.services.loot import roll_drop
from cococap.services.party import xp_multiplier
from cococap.user import Cooldowns, User

PLOTS = 9  # how many plots exist right now (the farm model has room for 27: three pages)
PAGE_PLOTS = 9  # plots on one page of the farm screen
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


def _waters(user_id: int, plot: int, hour: int, chance: float) -> bool:
    return random.Random(f"water:{user_id}:{plot}:{hour}").random() < chance


@dataclass(frozen=True)
class RainReport:
    rains: int  # hours in which at least one of your plots grew
    blessings: int
    matured: tuple[int, ...]  # plot numbers that finished growing


def apply_rain(farming: Farming, user_id: int, now: float, registry: Registry, grow_bonus: float = 0.0) -> RainReport:
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
            if _grows(user_id, number, h, min(1.0, rules.grow_chance + grow_bonus)):
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
class Estimate:
    """How long `cycles` more cycles of growing take, in hours. Rain is luck, so this is a range: you are done by
    `early` in one try out of ten, and by `late` in nine out of ten."""

    typical: float
    early: int
    late: int

    def text(self) -> str:
        """e.g. "about 3h (1h to 7h)", "about 2.5 days (2 to 3.2 days)"."""
        return f"about {_span(self.typical)} ({_span(self.early)} to {_span(self.late)})"

    def short(self) -> str:
        """Just the typical time, for crowded places: "~3h", "~2.5 days"."""
        return f"~{_span(self.typical)}"


def _span(hours: float) -> str:
    if hours < 48:
        return f"{round(hours)}h" if hours >= 1 else "1h"
    days = hours / 24
    return f"{days:.1f} days" if days < 10 else f"{round(days)} days"


def hourly_chance(rules, watered: bool = False) -> float:
    """The chance a growing plot gains a cycle in one hour: the rain, and (if you water it that hour) the water on top."""
    rain = rules.grow_chance
    return 1 - (1 - rain) * (1 - rules.water_chance) if watered else rain


def estimate(cycles_left: int, rules, watered: bool = False) -> Estimate:
    """How long until a crop has grown `cycles_left` more cycles. `watered` means you water it EVERY hour; otherwise only the rain
    counts. The exact odds for short crops, the normal approximation for long ones (where it is very close)."""
    n, p = max(0, cycles_left), hourly_chance(rules, watered)
    if n == 0:
        return Estimate(0.0, 0, 0)
    typical = n / p
    if n <= 60:  # exact: the number of hours until the n-th success
        done, hours, early, late = [1.0] + [0.0] * n, 0, None, None  # done[k] = P(exactly k cycles so far)
        while late is None and hours < 100_000:
            hours += 1
            for k in range(n, 0, -1):
                done[k] = done[k] * (1 - p if k < n else 1) + done[k - 1] * p
            done[0] *= 1 - p
            if early is None and done[n] >= 0.1:
                early = hours
            if done[n] >= 0.9:
                late = hours
        return Estimate(typical, early or 1, late or hours)
    spread = 1.2816 * (n * (1 - p)) ** 0.5 / p  # 10% / 90% of a normal curve
    return Estimate(typical, max(1, round(typical - spread)), round(typical + spread))


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
    watered: bool = False  # you have watered it this hour

    def left(self, rules, watered: bool = False) -> Estimate:
        """How long until it is ready, from now (the rain after this one, then the next...)."""
        return estimate(max(0, self.needed - self.cycle), rules, watered)

    @property
    def empty(self) -> bool:
        return self.unlocked and self.seed_id is None

    @property
    def growing(self) -> bool:
        return self.seed_id is not None and not self.ready

    @property
    def progress(self) -> float:
        return min(1.0, self.cycle / self.needed) if self.needed else 0.0


def plot_views(farming: Farming, registry: Registry, now: float | None = None) -> list[PlotView]:
    views = []
    hour = hour_of(now) if now is not None else None
    for number in range(1, PLOTS + 1):
        plot = plot_of(farming, number)
        seed = registry.item(plot.crop_id).seed if plot.crop_id else None
        views.append(PlotView(
            number, is_unlocked(farming, number, registry.farming), plot.crop_id,
            seed.grows_into if seed else None, plot.cycle, seed.cycles if seed else 0, plot.can_harvest,
            hour is not None and plot.watered == hour,
        ))
    return views


def level_of(farming: Farming) -> int:
    return User.xp_to_level(farming.xp)


# ---- the Farmer's Market calendar --------------------------------------------------------------------
def _day(now: float) -> int:
    return int(now // DAY)


def market_window(now: float, registry: Registry) -> tuple[bool, int]:
    """(is it open, when does that change). The market opens every day at `open_hour` UTC for `open_hours` hours."""
    m = registry.farming.market
    length = m.open_hours * 3600
    start = (_day(now) - 1) * DAY + m.open_hour * 3600  # yesterday's opening (it may run past midnight)
    for _ in range(3):
        if start <= now < start + length:
            return True, start + length
        if now < start:
            return False, start
        start += DAY
    return False, start


# ---- operations on a player (these persist) ------------------------------------------------------------
async def sync(user: User, now: float | None = None, registry: Registry | None = None) -> tuple[Farming, RainReport]:
    """Catch the farm up on the rain and return it (plus what the rain did)."""
    reg, now = registry or get_registry(), now if now is not None else time.time()
    seen: list[RainReport] = []
    grow = (await pets.bonuses(user, reg)).get("grow_chance", 0.0)
    farming = await user.update_skill("farming", lambda m: seen.append(apply_rain(m, user.id, now, reg, grow)))
    return farming, seen[0]


async def locked_seeds(user: User, registry: Registry | None = None) -> dict[str, str]:
    """Seeds the shop will not sell you yet, as {seed id: the field that opens it}. Fields open by farming level and the farthest area reached."""
    reg = registry or get_registry()
    opened = await areas.reached_locations(user, "farming", reg)
    fields = reg.locations["farming"]
    return {seed: fields[n].name for n, seed in enumerate(reg.farming.field_seeds) if n >= opened}


async def starter_gift(user: User, registry: Registry | None = None) -> dict[str, int]:
    """The free seeds every farmer gets the first time they open their farm (once). Returns what was given."""
    reg = registry or get_registry()
    outcome: dict = {}

    def claim(m: Farming) -> None:
        if not m.starter_given:
            m.starter_given = True
            outcome["given"] = True

    await user.update_skill("farming", claim)
    if not outcome:
        return {}
    for seed_id, quantity in reg.farming.starter_seeds.items():
        await user.add_item(seed_id, quantity)
    return dict(reg.farming.starter_seeds)


@dataclass(frozen=True)
class WaterReport:
    watered: int  # plots that took a watering
    grew: int  # ...and how many of them grew a cycle
    matured: tuple[int, ...]  # plots that are ready now
    thirsty: int = 0  # growing plots the can could not reach this hour (it waters `power` plots an hour)
    capacity: int = 0  # how many plots the can waters an hour


async def can_stats(user: User, registry: Registry | None = None) -> EffectiveStats:
    stats = await equipped_stats(user, "farming", registry)
    if stats is None:
        raise FarmingError("You need a watering can. Buy a Tin Watering Can in the shop (it's equipped for you).")
    return stats


async def water(user: User, now: float | None = None, registry: Registry | None = None) -> WaterReport:
    """Water your growing plots with your can. Each plot can be watered once an hour and then ALWAYS grows a cycle; the can only waters
    `power` plots an hour (the plots you already watered this hour count), lowest plot number first. Which hour you watered in is kept, so
    looking again changes nothing. A way to grow faster than the rain alone, once an hour."""
    reg, now = registry or get_registry(), now if now is not None else time.time()
    can = await can_stats(user, reg)
    hour = hour_of(now)
    pet = (await pets.bonuses(user, reg)).get("grow_chance", 0.0)
    chance = min(1.0, reg.farming.water_chance + pet)
    sprinkle = can.stats.get("sprinkle", 0.0)  # (a Sprinkler can: a watered plot sometimes grows a second cycle)
    outcome: dict = {"watered": 0, "grew": 0, "matured": [], "thirsty": 0}

    def pour(m: Farming) -> None:
        apply_rain(m, user.id, now, reg, pet)
        plots = {n: plot_of(m, n) for n in range(1, PLOTS + 1)}
        room = can.power - sum(1 for p in plots.values() if p.crop_id and p.watered == hour)  # what the can can still do this hour
        for number, plot in plots.items():
            if not plot.crop_id or plot.can_harvest or plot.watered == hour:
                continue
            if room <= 0:
                outcome["thirsty"] += 1
                continue
            room -= 1
            plot.watered = hour
            outcome["watered"] += 1
            if _waters(user.id, number, hour, chance):
                plot.cycle += 1
                outcome["grew"] += 1
                if sprinkle and _waters(user.id, number, -hour - 1, sprinkle):
                    plot.cycle += 1
                if plot.cycle >= reg.item(plot.crop_id).seed.cycles:
                    plot.can_harvest = True
                    outcome["matured"].append(number)

    await user.update_skill("farming", pour)
    return WaterReport(outcome["watered"], outcome["grew"], tuple(outcome["matured"]), outcome["thirsty"], can.power)


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

    grow = (await pets.bonuses(user, reg)).get("grow_chance", 0.0)

    def sow(m: Farming) -> None:
        apply_rain(m, user.id, now, reg, grow)
        plot = plot_of(m, number)
        if not is_unlocked(m, number, reg.farming):
            raise FarmingError("You don't own that plot yet.")
        if plot.crop_id:
            raise FarmingError("Something is already growing there.")
        plot.crop_id, plot.cycle, plot.can_harvest, plot.since, plot.tended = seed_id, 0, False, hour_of(now), 0

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
    extras: Counter = field(default_factory=Counter)  # leftovers from the harvest (plant fiber...)
    replanted: bool = False  # Evergreen: the plot is growing the same crop again


# ---- Tend: byproducts of every growth cycle ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class TendReport:
    plots: int  # plots that had something to collect
    cycles: int  # growth cycles collected
    found: Counter = field(default_factory=Counter)


def _byproduct_rolls(seed_id: str, rules) -> int:
    """Rolls of the farming drop table per growth cycle of this crop: its field's number (a seed that opens no field uses the first)."""
    fields = rules.field_seeds
    return rules.byproduct_rolls[fields.index(seed_id)] if seed_id in fields else rules.byproduct_rolls[0]


def tend_waiting(farm: Farming, rules) -> int:
    """How many growth cycles of byproducts are waiting across all plots (never more than `byproduct_max_cycles` per plot)."""
    return sum(min(rules.byproduct_max_cycles, p.cycle - p.tended) for n in range(1, PLOTS + 1)
               if (p := plot_of(farm, n)).crop_id and is_unlocked(farm, n, rules) and p.cycle > p.tended)


async def tend(user: User, rng: random.Random, now: float | None = None, registry: Registry | None = None) -> TendReport:
    """Collect the byproducts every growing plot made since you last tended: per waiting cycle (up to `byproduct_max_cycles` per plot) the farming drop table is
    rolled `byproduct_rolls` times for that crop's field, a can's drop luck adds more, and later fields can roll starred materials. No xp: that is paid at harvest."""
    reg, now = registry or get_registry(), now if now is not None else time.time()
    rules = reg.farming
    can = await equipped_stats(user, "farming", reg)
    luck = can.stats.get("drop_luck", 0.0) if can else 0.0
    pet = (await pets.bonuses(user, reg)).get("grow_chance", 0.0)
    materials = [i for i in reg.items_for_skill("farming") if i.category == "material" and i.drop]
    waiting: list[tuple[str, int]] = []  # (seed, cycles) per plot with something to collect

    def collect(m: Farming) -> None:
        apply_rain(m, user.id, now, reg, pet)
        for number in range(1, PLOTS + 1):
            plot = plot_of(m, number)
            if not plot.crop_id or plot.cycle <= plot.tended:
                continue
            waiting.append((plot.crop_id, min(rules.byproduct_max_cycles, plot.cycle - plot.tended)))
            plot.tended = plot.cycle  # (cycles past the cap are lost: that is the price of not checking in)

    await user.update_skill("farming", collect)
    if not waiting:
        raise FarmingError("Nothing has grown since you last tended.")
    found: Counter = Counter()
    for seed_id, cycles in waiting:
        expected = cycles * _byproduct_rolls(seed_id, rules) * (1 + luck)
        rolls = int(expected) + (1 if rng.random() < expected - int(expected) else 0)
        part: Counter = Counter()
        for _ in range(rolls):
            for item in materials:
                if quantity := roll_drop(item, rng):
                    part[item.id] += quantity
        field_no = rules.field_seeds.index(seed_id) + 1 if seed_id in rules.field_seeds else 1
        found.update(stars.apply(part, stars.progress(field_no, len(rules.field_seeds)), rng, reg))
    for item_id, quantity in found.items():
        await user.add_item(item_id, quantity)
    return TendReport(len(waiting), sum(c for _, c in waiting), found)


def drop_rolls(cycles: int, rules, rng: random.Random, luck: float = 0.0) -> int:
    """How many times a harvest rolls the farming drop table: one per `drop_cycles_per_roll` growth cycles of the crop (a fraction
    is a chance of one more), a can's `drop_luck` makes it more, never over `max_drop_rolls`."""
    expected = cycles / rules.drop_cycles_per_roll * (1 + luck)
    whole = int(expected)
    return min(rules.max_drop_rolls, whole + (1 if rng.random() < expected - whole else 0))


def harvest_extras(rng: random.Random, registry: Registry, cycles: int = 4, luck: float = 0.0) -> Counter:
    """Materials that come along with a harvest (items of the farming skill that have a drop table): longer crops roll more."""
    found: Counter = Counter()
    materials = [i for i in registry.items_for_skill("farming") if i.category == "material" and i.drop]
    for _ in range(drop_rolls(cycles, registry.farming, rng, luck)):
        for item in materials:
            if quantity := roll_drop(item, rng):
                found[item.id] += quantity
    return found


async def harvest(
    user: User, number: int, rng: random.Random, now: float | None = None, registry: Registry | None = None
) -> Harvest:
    reg, now = registry or get_registry(), now if now is not None else time.time()
    rules = reg.farming
    taken: dict = {}
    party_bonus = await xp_multiplier(user.id, reg, "farming")
    pet = await pets.bonuses(user, reg)
    can = await equipped_stats(user, "farming", reg)  # (a can with better stats gives bigger harvests and more drops; no can: no bonus)
    crop_yield = can.stats.get("crop_yield", 0.0) if can else 0.0
    extra_harvest = pet.get("extra_harvest", 0.0)  # (a Bee: each harvested plot has this chance of a whole second harvest of the same crop, free)
    transmute = can.stats.get("transmute", 0.0) if can else 0.0  # (an Alchemist can: some harvests come up double)
    evergreen = can.stats.get("evergreen", 0.0) if can else 0.0  # (Mastery: a harvest sometimes replants itself, free)
    heirloom = can.stats.get("heirloom", 0.0) if can else 0.0  # (Mastery: some harvests come up 60% bigger)

    def pick(m: Farming) -> None:
        apply_rain(m, user.id, now, reg, pet.get("grow_chance", 0.0))
        plot = plot_of(m, number)
        if not (plot.crop_id and plot.can_harvest):
            raise FarmingError("Nothing is ready to harvest on that plot.")
        crop = reg.item(reg.item(plot.crop_id).seed.grows_into)
        amount = max(1, round(rng.randint(crop.crop.min_harvest, crop.crop.max_harvest) * (1 + crop_yield) * (2 if rng.random() < transmute else 1) * (1.6 if heirloom and rng.random() < heirloom else 1)))
        if extra_harvest and rng.random() < extra_harvest:
            amount += max(1, round(rng.randint(crop.crop.min_harvest, crop.crop.max_harvest) * (1 + crop_yield)))
        taken.update(seed=plot.crop_id, crop=crop.id, amount=amount,
                     xp=round(reg.item(plot.crop_id).seed.cycles * rules.xp_per_cycle * party_bonus))
        replant = bool(evergreen) and rng.random() < evergreen
        taken["replanted"] = replant
        if replant:  # Evergreen: the same crop is growing again, no seed spent
            plot.cycle, plot.can_harvest, plot.since, plot.tended = 0, False, hour_of(now), 0
        else:
            plot.crop_id, plot.cycle, plot.can_harvest, plot.tended = None, 0, False, 0  # the plot is empty from this moment: once only
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
    extras = harvest_extras(rng, reg, reg.item(taken["seed"]).seed.cycles, can.stats.get("drop_luck", 0.0) if can else 0.0)
    field_no = reg.farming.field_seeds.index(taken["seed"]) + 1 if taken["seed"] in reg.farming.field_seeds else 1
    extras = stars.apply(extras, stars.progress(field_no, len(reg.farming.field_seeds)), rng, reg)  # starred materials: the further the field, the better the star
    if scroll := scrolls.roll("farming", rng, reg, reg.item(taken["seed"]).seed.cycles):  # a rare scroll: one chance per growth cycle of what you harvest
        extras[scroll] += 1
    if can and rng.random() < can.stats.get("seed_back", 0.0):  # a good can lets a plant go to seed: the seed comes back
        extras[taken["seed"]] += 1
    for item_id, quantity in extras.items():
        await user.add_item(item_id, quantity)
    anomaly = rng.randint(1, rules.anomaly_odds) == 1
    if anomaly:
        await user.refresh_cooldowns(Cooldowns.WORK, Cooldowns.DAILY)
    return Harvest(number, taken["crop"], taken["amount"], taken["xp"], anomaly, extras, taken.get("replanted", False))


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
        raise FarmingError("The Farmer's Market is closed. It opens every day for a few hours.")


def market_price(item_id: str, quantity: int, registry: Registry) -> int:
    return int(registry.item(item_id).sell_price * quantity * (1 + registry.farming.market.price_bonus))


async def shop_haggle(user: User, item, reg: Registry) -> float:
    from cococap.services import shop  # (shop imports equipment, which this module also uses: import late to stay clear of a cycle)

    return await shop.haggle(user, item, reg)


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
        pay = round(market_price(item_id, quantity, reg) * (1 + await shop_haggle(user, item, reg)))
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

    grow = (await pets.bonuses(user, reg)).get("grow_chance", 0.0)

    def spend(m: Farming) -> None:
        apply_rain(m, user.id, now, reg, grow)
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
