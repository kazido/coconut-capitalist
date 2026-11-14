"""Coconut Level: one number for how far along a player is, worked out from their current progress.

Every source is a milestone reached once (a skill level, a rank, a pet, the Nth kill of an enemy): nothing pays for repeating
something, so the level cannot be ground forever. It is calculated, not stored: it needs no history and old players get it at once.
The numbers are in `configs/progress.toml`.
"""

from dataclasses import dataclass, field

from cococap.registry import Registry, get_registry
from cococap.registry.models import ProgressRules, Tier
from cococap.services import pets as pet_service
from cococap.user import User

SKILLS = ("mining", "farming", "foraging", "fishing", "combat")
SKILL_EMOJI = {"mining": "⛏️", "farming": "🌽", "foraging": "🌳", "fishing": "🐟", "combat": "⚔️"}


@dataclass(frozen=True)
class Entry:
    label: str
    points: int  # earned so far
    max_points: int
    detail: str = ""
    # For a counter: how far you are (current, next step, points it pays), so the page can show what is closest.
    next_step: tuple[int, int, int] | None = None


@dataclass(frozen=True)
class Category:
    key: str
    name: str
    emoji: str
    entries: tuple[Entry, ...]

    @property
    def points(self) -> int:
        return sum(e.points for e in self.entries)

    @property
    def max_points(self) -> int:
        return sum(e.max_points for e in self.entries)


@dataclass(frozen=True)
class Progress:
    points: int
    level: int
    into: int  # points into the current level
    needed: int  # points a level takes
    tier: Tier
    categories: tuple[Category, ...]
    max_points: int = 0

    def next_up(self, count: int = 3) -> list[tuple[str, int, int, int]]:
        """The counters closest to their next payout: (label, current, target, points)."""
        found = [(e.label, *e.next_step) for c in self.categories for e in c.entries if e.next_step]
        found.sort(key=lambda f: f[1] / f[2], reverse=True)
        return found[:count]


def tier_of(level: int, rules: ProgressRules) -> Tier:
    return [t for t in rules.tiers if t.from_level <= level][-1]


def level_of(points: int, rules: ProgressRules) -> tuple[int, int]:
    """(level, points into it)."""
    return divmod(points, rules.points_per_level)


# ---- the milestone arithmetic (pure) ------------------------------------------------------------------------------------
def skill_points(level: int, rules: ProgressRules) -> int:
    """Points for reaching `level` in one skill: every level from 2 up, a bit more each above `after_level`."""
    s = rules.skills
    top = min(max(level, 1), s.max_level)
    low = max(0, min(top, s.after_level) - 1)
    high = max(0, top - s.after_level)
    return low * s.per_level + high * s.per_level_after


def steps_reached(count: int, steps: list[int]) -> int:
    return sum(1 for step in steps if count >= step)


def next_step(count: int, steps: list[int]) -> int | None:
    return next((s for s in steps if count < s), None)


def tool_levels(registry: Registry) -> dict[str, tuple[str, int]]:
    """template id -> (kind, level) for every tool, level 1 being the first tool of its upgrade chain."""
    tools = [i for i in registry.items.values() if i.tool]
    upgraded_to = {i.tool.upgrade.to for i in tools if i.tool.upgrade}
    levels: dict[str, tuple[str, int]] = {}
    for root in (i for i in tools if i.id not in upgraded_to):
        current, level = root, 1
        while True:
            levels[current.id] = (current.tool.kind, level)
            if not current.tool.upgrade:
                break
            current, level = registry.item(current.tool.upgrade.to), level + 1
    return levels


def stat_value(skills: dict, stat: str) -> int:
    """`stat` is "skill.counter", e.g. "fishing.fish_caught"."""
    skill, name = stat.split(".")
    return int(getattr(skills[skill].stats, name))


@dataclass
class Snapshot:
    """Everything the level is made from, loaded once."""

    skills: dict
    rank: int
    pethouse: object
    owned_templates: set[str] = field(default_factory=set)


async def snapshot(user: User) -> Snapshot:
    return Snapshot(
        skills={name: await user.skill(name) for name in SKILLS},
        rank=user.rank,
        pethouse=user.pethouse,
        owned_templates={i.template_id for i in await user.instances()},
    )


def build(snap: Snapshot, registry: Registry) -> Progress:
    """Pure: the level of a snapshot."""
    rules = registry.progress
    cats: list[Category] = []

    # skills
    entries = []
    for name in SKILLS:
        level = User.xp_to_level(snap.skills[name].xp)
        top = skill_points(rules.skills.max_level, rules)
        entries.append(Entry(f"{name.title()} level", skill_points(level, rules), top, f"Level {level}"))
    cats.append(Category("skills", "Skills", "📈", tuple(entries)))

    # ranks
    max_rank = len(registry.ranks) - 1
    rank = min(snap.rank, max_rank)
    cats.append(Category("ranks", "Ranks", "🏅", (Entry("Rank", rank * rules.ranks.per_rank, max_rank * rules.ranks.per_rank,
                                                         registry.rank(rank).display_name),)))

    # pets
    house, p = snap.pethouse, rules.pets
    max_stars = registry.economy.pets.max_stars
    species = len(house.pets)
    extra = sum(max(0, min(o.stars, max_stars) - 1) for o in house.pets.values())  # (never more than the star cap)
    maxed = sum(1 for o in house.pets.values() if pet_service.pet_level(o.xp, registry) >= registry.economy.pets.max_level)
    total = len(registry.pets)
    cats.append(Category("pets", "Pets", "🐾", (
        Entry("Pets found", species * p.per_pet, total * p.per_pet, f"{species}/{total}"),
        Entry("Extra stars", extra * p.per_extra_star, total * (max_stars - 1) * p.per_extra_star, f"{extra}/{total * (max_stars - 1)}"),
        Entry("Max-level pets", maxed * p.maxed_level, total * p.maxed_level, f"{maxed}/{total}"),
    )))

    # gear and land
    levels = tool_levels(registry)
    best: dict[str, int] = {}
    for template in snap.owned_templates:
        if template in levels:
            kind, level = levels[template]
            best[kind] = max(best.get(kind, 1), level)
    kinds = {kind for kind, _ in levels.values()}
    tool_entries = []
    for kind in sorted(kinds):
        longest = max(level for k, level in levels.values() if k == kind)
        tool_entries.append(Entry(f"Best {kind}", (best.get(kind, 1) - 1) * rules.tools.per_level, (longest - 1) * rules.tools.per_level,
                                  f"Level {best.get(kind, 1)}/{longest}"))
    farm = snap.skills["farming"].farm
    free = registry.farming.free_plots
    plots = sum(1 for n in range(free + 1, 10) if getattr(farm, f"plot_{n}").unlocked)
    tool_entries.append(Entry("Farm plots", plots * rules.farming.per_plot, (9 - free) * rules.farming.per_plot, f"{free + plots}/9"))
    cats.append(Category("gear", "Gear and land", "🧰", tuple(tool_entries)))

    # counters
    ladder_entries = []
    for ladder in rules.ladders:
        count = stat_value(snap.skills, ladder.stat)
        nxt = next_step(count, ladder.steps)
        ladder_entries.append(Entry(ladder.name, steps_reached(count, ladder.steps) * ladder.points, len(ladder.steps) * ladder.points,
                                    f"{count:,}", (count, nxt, ladder.points) if nxt else None))
    cats.append(Category("milestones", "Milestones", "🎯", tuple(ladder_entries)))

    # bestiary
    kills = snap.skills["combat"].kills
    beasts = []
    for enemy in registry.enemies.values():
        steps, each = (rules.bestiary.boss_steps, rules.bestiary.boss_points) if enemy.boss else (rules.bestiary.steps, rules.bestiary.points)
        count = kills.get(enemy.id, 0)
        nxt = next_step(count, steps)
        beasts.append(Entry(enemy.name, steps_reached(count, steps) * each, len(steps) * each, f"{count:,} slain",
                            (count, nxt, each) if nxt else None))
    cats.append(Category("bestiary", "Bestiary", "📖", tuple(beasts)))

    points = sum(c.points for c in cats)
    level, into = level_of(points, rules)
    return Progress(points, level, into, rules.points_per_level, tier_of(level, rules), tuple(cats), sum(c.max_points for c in cats))


async def progress_of(user: User, registry: Registry | None = None) -> Progress:
    reg = registry or get_registry()
    return build(await snapshot(user), reg)
