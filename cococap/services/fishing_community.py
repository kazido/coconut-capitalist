"""Fishing together: the server's collection book and the month's community goals.

* The **community book** holds a few rare fish. Anyone who can fish well enough donates fish from their bag; a donor
  is paid at once. When every page is full the book is finished *exactly once* (inside the transaction that took the
  last fish), it levels up, and every player is owed a reward, which each of them collects from their own panel.
* The **monthly goals** are three community-wide counters ("catch 1,500 fish between you"). Every landed fish adds to
  whichever goals it fits. A finished goal pays everyone who did at least ``min_share`` of it, once, on their claim.

Nothing here is scheduled: which month it is comes from the clock, and rewards are claimed lazily by the players.
"""

import datetime
import random
import time
from dataclasses import dataclass

from cococap.registry import Item, Registry, get_registry
from cococap.registry.models import FishingRules, MonthlySlot
from cococap.services import community
from cococap.services.fishing import FishingError, fish_pool
from cococap.services.party import xp_multiplier
from cococap.user import User

BOOK_KEY = "fishing_book"
BOOK_DEFAULT = {"level": 1, "given": {}, "donors": {}}


class CommunityError(FishingError):
    """A rule was broken; the message is safe to show the player."""


async def _fishing_level(user: User) -> int:
    return User.xp_to_level((await user.skill("fishing")).xp)


# ---- the community book -----------------------------------------------------------------------------------
def book_need(level: int, fish: Item, rules: FishingRules) -> int:
    book = rules.community.book
    return book.need_base[fish.rarity] + int((level - 1) * book.need_step[fish.rarity])


def book_fish(registry: Registry) -> list[Item]:
    return [registry.item(i) for i in registry.fishing.community.book.fish]


@dataclass(frozen=True)
class BookPage:
    fish: Item
    given: int
    need: int

    @property
    def done(self) -> bool:
        return self.given >= self.need


@dataclass(frozen=True)
class CommunityBook:
    level: int
    pages: tuple[BookPage, ...]
    donated_by_you: int
    completed: int  # how many times the server has finished the book


async def book(user: User, registry: Registry | None = None) -> CommunityBook:
    reg = registry or get_registry()
    state = await community.read(BOOK_KEY, BOOK_DEFAULT)
    level = state["level"]
    pages = tuple(BookPage(i, state["given"].get(i.id, 0), book_need(level, i, reg.fishing)) for i in book_fish(reg))
    return CommunityBook(level, pages, state["donors"].get(str(user.id), 0), level - 1)


@dataclass(frozen=True)
class Donation:
    fish: Item
    quantity: int
    bits: int
    xp: int
    finished_level: int | None = None  # set if this donation completed the book


async def donate(user: User, fish_id: str, registry: Registry | None = None) -> Donation:
    """Give the book as many of this fish as it still needs (and you have). The donor is paid straight away."""
    reg = registry or get_registry()
    rules = reg.fishing
    if await _fishing_level(user) < rules.book.min_level:
        raise CommunityError(f"The community book opens to anglers of fishing level {rules.book.min_level}.")
    fish = next((i for i in book_fish(reg) if i.id == fish_id), None)
    if fish is None:
        raise CommunityError("The community book has no page for that.")
    view = await book(user, reg)
    page = next(p for p in view.pages if p.fish.id == fish_id)
    if page.done:
        raise CommunityError(f"The community book already has all the {fish.name} it needs.")
    take = min(await user.item_quantity(fish_id), page.need - page.given)
    if take <= 0:
        raise CommunityError(f"You don't have any {fish.name}.")
    try:
        await user.remove_item(fish_id, take)
    except ValueError:
        raise CommunityError(f"You don't have any {fish.name}.") from None

    outcome: dict = {"credited": 0, "finished": None}

    def give(state: dict) -> None:
        level = state["level"]
        have = state["given"].get(fish_id, 0)
        credited = max(0, min(take, book_need(level, fish, rules) - have))  # someone else may have filled it
        outcome["credited"] = credited
        if credited == 0:
            return
        state["given"][fish_id] = have + credited
        donors = state["donors"]
        donors[str(user.id)] = donors.get(str(user.id), 0) + credited
        if level < rules.community.book.max_level and all(
            state["given"].get(i.id, 0) >= book_need(level, i, rules) for i in book_fish(reg)
        ):
            state["level"], state["given"], state["donors"] = level + 1, {}, {}  # finished: exactly once, right here
            outcome["finished"] = level

    await community.update(BOOK_KEY, BOOK_DEFAULT, give)
    credited = outcome["credited"]
    if credited < take:
        await user.add_item(fish_id, take - credited)  # the book didn't need them after all
    if credited == 0:
        raise CommunityError(f"The community book already has all the {fish.name} it needs.")
    xp = round(credited * fish.rarity * rules.community.book.donor_xp_per_rarity * await xp_multiplier(user.id, reg))
    bits = round(fish.sell_price * rules.community.book.donor_bits_per_sell * credited)
    await user.update_skill("fishing", lambda s: setattr(s, "xp", s.xp + xp))
    if bits:
        await user.add_bits(bits)
    return Donation(fish, credited, bits, xp, outcome["finished"])


@dataclass(frozen=True)
class BookReward:
    levels: tuple[int, ...]  # the book levels you are being paid for
    bits: int
    xp: int


async def claim_book_rewards(user: User, registry: Registry | None = None) -> BookReward | None:
    """Collect your share of every time the server finished the book since you last looked (once each)."""
    reg = registry or get_registry()
    rules = reg.fishing
    if await _fishing_level(user) < rules.book.min_level:
        return None
    done = (await community.read(BOOK_KEY, BOOK_DEFAULT))["level"] - 1
    paid: dict = {}

    def collect(skill) -> None:
        previous = skill.community_claimed
        if done > previous:
            paid["levels"] = tuple(range(previous + 1, done + 1))
            skill.community_claimed = done

    await user.update_skill("fishing", collect)
    if not paid:
        return None
    b = rules.community.book
    bits = sum(b.completion_bits * level for level in paid["levels"])
    xp = round(sum(b.completion_xp * level for level in paid["levels"]) * await xp_multiplier(user.id, reg))
    await user.update_skill("fishing", lambda s: setattr(s, "xp", s.xp + xp))
    await user.add_bits(bits)
    return BookReward(paid["levels"], bits, xp)


# ---- the month's community goals ----------------------------------------------------------------------------
def month_of(now: float) -> int:
    d = datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
    return (d.year - 1970) * 12 + d.month - 1


def month_ends_at(period: int) -> float:
    year, month = divmod(period + 1, 12)
    return datetime.datetime(1970 + year, month + 1, 1, tzinfo=datetime.timezone.utc).timestamp()


@dataclass(frozen=True)
class Goal:
    index: int
    slot: MonthlySlot
    fish: Item | None  # the specific fish, for a "fish" goal

    @property
    def text(self) -> str:
        if self.slot.kind == "any":
            return f"Catch {self.slot.count:,} fish"
        if self.slot.kind == "rarity":
            from cococap.constants import Rarities

            return f"Catch {self.slot.count:,} {Rarities.from_value(self.slot.rarity).rarity_name} or better fish"
        return f"Catch {self.slot.count:,} {self.fish.display}"

    def counts(self, fish: Item) -> bool:
        if self.slot.kind == "any":
            return True
        if self.slot.kind == "rarity":
            return fish.rarity >= self.slot.rarity
        return fish.id == self.fish.id


def goals(period: int, registry: Registry) -> list[Goal]:
    """The month's goals: the same for everyone (picked from the month alone)."""
    rng = random.Random(f"fishing-monthly:{period}")
    pool = sorted(fish_pool(registry), key=lambda i: i.id)
    out = []
    for i, slot in enumerate(registry.fishing.community.monthly):
        fish = rng.choice([f for f in pool if f.rarity == slot.rarity]) if slot.kind == "fish" else None
        out.append(Goal(i, slot, fish))
    return out


def _key(period: int) -> str:
    return f"fishing_monthly:{period}"


def _default(reg: Registry) -> dict:
    n = len(reg.fishing.community.monthly)
    return {"progress": [0] * n, "mine": {}}


async def record_catch(user: User, fish: Item, now: float | None = None, registry: Registry | None = None) -> None:
    """Add a landed fish to every community goal it fits (and to your own share of it)."""
    reg = registry or get_registry()
    now = time.time() if now is None else now
    period = month_of(now)
    matching = [g.index for g in goals(period, reg) if g.counts(fish)]
    if not matching:
        return

    def add(state: dict) -> None:
        mine = state["mine"].setdefault(str(user.id), [0] * len(state["progress"]))
        for i in matching:
            state["progress"][i] += 1
            mine[i] += 1

    await community.update(_key(period), _default(reg), add)


@dataclass(frozen=True)
class GoalView:
    goal: Goal
    progress: int
    yours: int

    @property
    def done(self) -> bool:
        return self.progress >= self.goal.slot.count


def qualifies(yours: int, slot: MonthlySlot, rules: FishingRules) -> bool:
    """Did you do enough of this goal to be paid for it?"""
    return yours >= max(1, round(slot.count * rules.community.min_share))


async def monthly(user: User, now: float | None = None, registry: Registry | None = None) -> list[GoalView]:
    reg = registry or get_registry()
    now = time.time() if now is None else now
    period = month_of(now)
    state = await community.read(_key(period), _default(reg))
    mine = state["mine"].get(str(user.id), [0] * len(state["progress"]))
    return [GoalView(g, state["progress"][g.index], mine[g.index]) for g in goals(period, reg)]


@dataclass(frozen=True)
class MonthlyReward:
    goals: tuple[Goal, ...]
    bits: int
    xp: int


async def claim_monthly(user: User, now: float | None = None, registry: Registry | None = None) -> MonthlyReward | None:
    """Collect what you are owed for finished goals of this month and last (once each)."""
    reg = registry or get_registry()
    rules = reg.fishing
    now = time.time() if now is None else now
    if await _fishing_level(user) < rules.quests.min_level:
        return None
    this = month_of(now)
    won: list[Goal] = []
    for period in (this - 1, this):
        state = await community.read(_key(period), _default(reg))
        mine = state["mine"].get(str(user.id))
        if not mine:
            continue
        owed = [g for g in goals(period, reg)
                if state["progress"][g.index] >= g.slot.count and qualifies(mine[g.index], g.slot, rules)]
        if not owed:
            continue

        def mark(skill, period=period, owed=owed) -> None:
            flags = skill.monthly_claimed.setdefault(str(period), [False] * len(rules.community.monthly))
            for g in owed:
                if not flags[g.index]:
                    flags[g.index] = True
                    won.append(g)
            for old in [p for p in skill.monthly_claimed if int(p) < this - 2]:
                del skill.monthly_claimed[old]  # keep the record short

        await user.update_skill("fishing", mark)
    if not won:
        return None
    bits = sum(g.slot.bits for g in won)
    xp = round(sum(g.slot.xp for g in won) * await xp_multiplier(user.id, reg))
    await user.update_skill("fishing", lambda s: setattr(s, "xp", s.xp + xp))
    await user.add_bits(bits)
    return MonthlyReward(tuple(won), bits, xp)
